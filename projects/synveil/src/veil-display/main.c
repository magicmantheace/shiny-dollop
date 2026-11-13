// SPDX-License-Identifier: MPL-2.0
// A source-built framebuffer diagnostic. Not a desktop or a privileged agent.
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <dirent.h>
#include <errno.h>
#include <linux/input.h>
#include <limits.h>
#include <linux/vt.h>
#include <net/if.h>
#include <netinet/in.h>
#include <poll.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>
#include "preferences.h"
#include "core_health.h"
#include "network_diag.h"
#include "pressure_diag.h"
#include "lifetime.h"
#include "mapping.h"
#include "seat_privacy.h"
#include "login_keyboard.h"
#include "enroll.h"
#include "files.h"

struct surface {
    unsigned char *mapped;
    size_t length;
    struct fb_var_screeninfo variable;
    struct fb_fix_screeninfo fixed;
};

static uint32_t channel(uint8_t input, struct fb_bitfield field) {
    uint64_t maximum = ((uint64_t)1u << field.length) - 1u;
    return (uint32_t)(((uint64_t)input * maximum + 127u) / 255u) << field.offset;
}

static uint32_t rgb(const struct surface *screen, uint8_t red, uint8_t green, uint8_t blue) {
    return channel(red, screen->variable.red) |
           channel(green, screen->variable.green) |
           channel(blue, screen->variable.blue);
}

static int valid_layout(const struct surface *screen) {
    const struct fb_var_screeninfo *v = &screen->variable;
    const struct fb_fix_screeninfo *f = &screen->fixed;
    if (v->bits_per_pixel != 32 || !v->xres || !v->yres || !f->smem_len ||
        (f->visual != FB_VISUAL_TRUECOLOR && f->visual != FB_VISUAL_DIRECTCOLOR)) {
        return 0;
    }
    const struct fb_bitfield channels[] = {v->red, v->green, v->blue};
    for (size_t i = 0; i < sizeof(channels) / sizeof(channels[0]); i++) {
        if (!channels[i].length || channels[i].length > 16 ||
            channels[i].offset >= 32 ||
            channels[i].length > 32 - channels[i].offset) {
            return 0;
        }
    }
    const uint64_t last_pixel = (uint64_t)(v->yoffset + (uint64_t)v->yres - 1u) * f->line_length +
                                ((uint64_t)v->xoffset + v->xres) * 4u;
    return last_pixel <= f->smem_len;
}

static void rectangle(const struct surface *screen, unsigned x, unsigned y,
                      unsigned width, unsigned height, uint32_t color) {
    const unsigned max_x = screen->variable.xres;
    const unsigned max_y = screen->variable.yres;
    if (x >= max_x || y >= max_y) return;
    if (width > max_x - x) width = max_x - x;
    if (height > max_y - y) height = max_y - y;
    for (unsigned row = 0; row < height; row++) {
        uint64_t start = (uint64_t)(screen->variable.yoffset + y + row) * screen->fixed.line_length +
                         (uint64_t)(screen->variable.xoffset + x) * 4u;
        for (unsigned col = 0; col < width; col++) {
            memcpy(screen->mapped + start + (uint64_t)col * 4u, &color, sizeof(color));
        }
    }
}

// Purposefully small glyph set for diagnostic headings. A real desktop will
// use a source-built font renderer and compositor instead.
static const uint8_t letters[26][7] = {
    {14,17,17,31,17,17,17}, {30,17,17,30,17,17,30},
    {14,17,16,16,16,17,14}, {30,17,17,17,17,17,30},
    {31,16,16,30,16,16,31}, {31,16,16,30,16,16,16},
    {14,17,16,23,17,17,14}, {17,17,17,31,17,17,17},
    {31,4,4,4,4,4,31}, {7,2,2,2,18,18,12},
    {17,18,20,24,20,18,17}, {16,16,16,16,16,16,31},
    {17,27,21,21,17,17,17}, {17,25,21,19,17,17,17},
    {14,17,17,17,17,17,14}, {30,17,17,30,16,16,16},
    {14,17,17,17,21,18,13}, {30,17,17,30,20,18,17},
    {15,16,16,14,1,1,30}, {31,4,4,4,4,4,4},
    {17,17,17,17,17,17,14}, {17,17,17,17,17,10,4},
    {17,17,17,21,21,21,10}, {17,17,10,4,10,17,17},
    {17,17,10,4,4,4,4}, {31,1,2,4,8,16,31}
};

static const uint8_t digits[10][7] = {
    {14,17,19,21,25,17,14}, {4,12,4,4,4,4,14},
    {14,17,1,2,4,8,31}, {30,1,1,14,1,1,30},
    {2,6,10,18,31,2,2}, {31,16,30,1,1,17,14},
    {6,8,16,30,17,17,14}, {31,1,2,4,8,8,8},
    {14,17,17,14,17,17,14}, {14,17,17,15,1,2,12}
};
static const uint8_t dot_glyph[7] = {0,0,0,0,0,6,6};
static const uint8_t colon_glyph[7] = {0,4,4,0,4,4,0};

static const uint8_t *glyph_for(unsigned char c) {
    if (c >= 'A' && c <= 'Z') return letters[c - 'A'];
    if (c >= '0' && c <= '9') return digits[c - '0'];
    if (c == '.') return dot_glyph;
    if (c == ':') return colon_glyph;
    return NULL;
}

static void heading(const struct surface *screen, const char *message,
                    unsigned x, unsigned y, unsigned scale, uint32_t color) {
    for (const unsigned char *cursor = (const unsigned char *)message; *cursor; cursor++) {
        const uint8_t *glyph = glyph_for(*cursor);
        if (glyph != NULL) {
            for (unsigned gy = 0; gy < 7; gy++) {
                for (unsigned gx = 0; gx < 5; gx++) {
                    if ((glyph[gy] & (1u << (4u - gx))) != 0u) {
                        rectangle(screen, x + gx * scale, y + gy * scale,
                                  scale, scale, color);
                    }
                }
            }
        }
        x += 6u * scale;
    }
}

static void paint(const struct surface *screen) {
    unsigned w = screen->variable.xres;
    unsigned h = screen->variable.yres;
    uint32_t base = rgb(screen, 13, 20, 36);
    rectangle(screen, 0, 0, w, h, base);
    rectangle(screen, 0, 0, w, h / 10u, rgb(screen, 19, 51, 79));
    rectangle(screen, 0, h / 10u, w, 3, rgb(screen, 80, 169, 215));
    unsigned scale = w >= 800u ? 5u : (w >= 480u ? 3u : 2u);
    heading(screen, "SYNVEIL", w / 16u, h / 5u, scale, rgb(screen, 220, 242, 250));
    heading(screen, "BOOTSTRAP", w / 16u, h / 5u + 11u * scale,
            2u, rgb(screen, 114, 194, 227));
    heading(screen, "GRAPHICS READY", w / 16u, h / 2u + 18u, 2u,
            rgb(screen, 190, 216, 224));
    rectangle(screen, w / 16u, h * 4u / 5u, w * 7u / 8u, 4u,
              rgb(screen, 74, 157, 196));
}

/* ------------------------------------------------------------------ */
/* Windows 11 presentation layer (ADR 0024, docs/UI_DESIGN.md).        */
/* Rendering only: no authentication, policy, credential or session    */
/* logic lives here. Text uses an embedded bitmap atlas generated      */
/* from the Buildroot-pinned DejaVu faces by tools/generate_ui_font.py */
/* (the spec's DejaVu fallback; the Selawik deviation is recorded in   */
/* docs/validation/). Integer math only: this binary is statically     */
/* linked without libm.                                                */
/* ------------------------------------------------------------------ */
#include "ui_font_data.h"

#ifndef UI_MOTION
#define UI_MOTION 1
#endif

struct ui_rgb { uint8_t r; uint8_t g; uint8_t b; };

struct ui_palette {
    struct ui_rgb ink, dim, faint, shell, surface, surface_hi, stroke;
    struct ui_rgb accent, accent_pressed, danger, field;
    struct ui_rgb grad_near, grad_far, on_accent, select;
};

/* UI_DESIGN.md tokens. select is the spec's selection blend: the accent
 * at 25 percent over the surface token. */
static const struct ui_palette UI_DARK = {
    {255, 255, 255}, {200, 200, 200}, {138, 138, 138}, {32, 32, 32},
    {44, 44, 44}, {56, 56, 56}, {69, 69, 69}, {76, 194, 255},
    {56, 168, 232}, {232, 17, 35}, {44, 44, 44}, {15, 43, 91},
    {27, 75, 143}, {32, 32, 32}, {52, 81, 96}
};

/* The pre-existing high-contrast preference keeps its light scheme; only
 * the token roles are mapped onto it. */
static const struct ui_palette UI_HC = {
    {9, 22, 31}, {29, 53, 67}, {80, 96, 104}, {245, 248, 250},
    {255, 255, 255}, {232, 238, 242}, {150, 164, 172}, {0, 95, 184},
    {0, 80, 158}, {200, 16, 32}, {255, 255, 255}, {200, 220, 240},
    {150, 190, 230}, {255, 255, 255}, {229, 186, 84}
};

static uint32_t ui_px(const struct surface *screen, struct ui_rgb color) {
    return rgb(screen, color.r, color.g, color.b);
}

static void ui_fill(const struct surface *screen, unsigned x, unsigned y,
                    unsigned width, unsigned height, struct ui_rgb color) {
    rectangle(screen, x, y, width, height, ui_px(screen, color));
}

static void ui_unpack(const struct surface *screen, uint32_t value,
                      unsigned out[3]) {
    const struct fb_bitfield fields[3] = {
        screen->variable.red, screen->variable.green, screen->variable.blue
    };
    for (unsigned i = 0; i < 3u; i++) {
        unsigned length = fields[i].length;
        unsigned max = length ? ((1u << length) - 1u) : 0u;
        unsigned raw = length ? ((value >> fields[i].offset) & max) : 0u;
        out[i] = max ? (raw * 255u + max / 2u) / max : 0u;
    }
}

/* Alpha-blend one pixel: cover 0 is invisible, 255 is the solid color. */
static void ui_blend(const struct surface *screen, unsigned x, unsigned y,
                     struct ui_rgb color, unsigned cover) {
    if (!cover || x >= screen->variable.xres || y >= screen->variable.yres)
        return;
    if (cover >= 255u) {
        rectangle(screen, x, y, 1u, 1u, ui_px(screen, color));
        return;
    }
    size_t offset = (size_t)y * screen->fixed.line_length + (size_t)x * 4u;
    uint32_t old;
    memcpy(&old, (const unsigned char *)screen->mapped + offset, 4u);
    unsigned bg[3];
    ui_unpack(screen, old, bg);
    unsigned inv = 255u - cover;
    struct ui_rgb mixed = {
        (uint8_t)((color.r * cover + bg[0] * inv + 127u) / 255u),
        (uint8_t)((color.g * cover + bg[1] * inv + 127u) / 255u),
        (uint8_t)((color.b * cover + bg[2] * inv + 127u) / 255u)
    };
    uint32_t value = ui_px(screen, mixed);
    memcpy((unsigned char *)screen->mapped + offset, &value, 4u);
}

/* Coverage of one pixel of a circle of radius r whose centre is at a
 * pixel-corner grid point; coordinates are doubled to stay integral. */
static unsigned ui_circle_cover(int dx2, int dy2, unsigned r) {
    int d2 = dx2 * dx2 + dy2 * dy2;
    int rr = (int)(2u * r);
    int inner = (rr - 1) * (rr - 1);
    int outer = (rr + 1) * (rr + 1);
    if (d2 <= inner) return 255u;
    if (d2 >= outer) return 0u;
    return (unsigned)((outer - d2) * 255 / (outer - inner));
}

static void ui_circle(const struct surface *screen, unsigned cx, unsigned cy,
                      unsigned r, struct ui_rgb color) {
    if (!r) return;
    for (unsigned y = cy > r ? cy - r : 0u; y < cy + r && y < screen->variable.yres; y++) {
        for (unsigned x = cx > r ? cx - r : 0u; x < cx + r && x < screen->variable.xres; x++) {
            int dx2 = (int)(2u * x + 1u) - (int)(2u * cx);
            int dy2 = (int)(2u * y + 1u) - (int)(2u * cy);
            unsigned cover = ui_circle_cover(dx2, dy2, r);
            if (cover) ui_blend(screen, x, y, color, cover);
        }
    }
}

static void ui_ring(const struct surface *screen, unsigned cx, unsigned cy,
                    unsigned r, unsigned width, struct ui_rgb color,
                    struct ui_rgb inside) {
    ui_circle(screen, cx, cy, r, color);
    if (r > width) ui_circle(screen, cx, cy, r - width, inside);
}

/* Filled rounded rectangle with antialiased corners. */
static void ui_rrect(const struct surface *screen, unsigned x, unsigned y,
                     unsigned width, unsigned height, unsigned radius,
                     struct ui_rgb color) {
    if (!width || !height) return;
    if (radius * 2u > width) radius = width / 2u;
    if (radius * 2u > height) radius = height / 2u;
    if (!radius) {
        ui_fill(screen, x, y, width, height, color);
        return;
    }
    ui_fill(screen, x, y + radius, width, height - 2u * radius, color);
    ui_fill(screen, x + radius, y, width - 2u * radius, radius, color);
    ui_fill(screen, x + radius, y + height - radius,
            width - 2u * radius, radius, color);
    for (unsigned q = 0; q < 4u; q++) {
        unsigned left = (q & 1u) ? x + width - radius : x;
        unsigned top = (q & 2u) ? y + height - radius : y;
        unsigned ccx = (q & 1u) ? x + width - radius : x + radius;
        unsigned ccy = (q & 2u) ? y + height - radius : y + radius;
        for (unsigned py = top; py < top + radius; py++) {
            for (unsigned px = left; px < left + radius; px++) {
                int dx2 = (int)(2u * px + 1u) - (int)(2u * ccx);
                int dy2 = (int)(2u * py + 1u) - (int)(2u * ccy);
                unsigned cover = ui_circle_cover(dx2, dy2, radius);
                if (cover) ui_blend(screen, px, py, color, cover);
            }
        }
    }
}

/* Rounded rectangle with a 1 px outline in stroke and a filled interior. */
static void ui_rrect_outline(const struct surface *screen, unsigned x,
                             unsigned y, unsigned width, unsigned height,
                             unsigned radius, struct ui_rgb stroke,
                             struct ui_rgb fill) {
    ui_rrect(screen, x, y, width, height, radius, stroke);
    if (width > 2u && height > 2u)
        ui_rrect(screen, x + 1u, y + 1u, width - 2u, height - 2u,
                 radius ? radius - 1u : 0u, fill);
}

static void ui_gradient(const struct surface *screen, struct ui_rgb top,
                        struct ui_rgb bottom) {
    unsigned w = screen->variable.xres;
    unsigned h = screen->variable.yres;
    for (unsigned y = 0; y < h; y++) {
        unsigned span = h > 1u ? h - 1u : 1u;
        struct ui_rgb row = {
            (uint8_t)((top.r * (span - y) + bottom.r * y) / span),
            (uint8_t)((top.g * (span - y) + bottom.g * y) / span),
            (uint8_t)((top.b * (span - y) + bottom.b * y) / span)
        };
        rectangle(screen, 0u, y, w, 1u, ui_px(screen, row));
    }
}

static const struct ui_font *ui_font_for(unsigned size, int bold) {
    for (unsigned i = 0; i < sizeof(ui_fonts) / sizeof(ui_fonts[0]); i++) {
        if (ui_fonts[i].size == size && ui_fonts[i].bold == (bold ? 1 : 0))
            return &ui_fonts[i];
    }
    return &ui_fonts[0];
}

/* PackBits-decode one glyph into out (width*height coverage bytes). */
static unsigned ui_glyph_decode(const struct ui_font *font,
                                const struct ui_glyph *glyph,
                                unsigned char *out) {
    const unsigned char *p = font->data + glyph->data_offset;
    unsigned total = (unsigned)glyph->width * glyph->height;
    unsigned produced = 0;
    while (produced < total) {
        unsigned char tag = *p++;
        if (tag >= 128) {
            unsigned run = 257u - tag;
            unsigned char value = *p++;
            while (run-- && produced < total) out[produced++] = value;
        } else {
            unsigned count = (unsigned)tag + 1u;
            while (count-- && produced < total) out[produced++] = *p++;
        }
    }
    return produced;
}

static const struct ui_glyph *ui_glyph(const struct ui_font *font,
                                       unsigned char c) {
    if (c < 32 || c > 126) c = '?';
    return &font->glyphs[c - 32];
}

static unsigned ui_text_width(unsigned size, int bold, const char *text) {
    const struct ui_font *font = ui_font_for(size, bold);
    unsigned width = 0;
    for (const unsigned char *p = (const unsigned char *)text; *p; p++)
        width += ui_glyph(font, *p)->advance;
    return width;
}

static void ui_text(const struct surface *screen, unsigned x,
                    unsigned baseline, unsigned size, int bold,
                    struct ui_rgb color, const char *text) {
    const struct ui_font *font = ui_font_for(size, bold);
    static unsigned char bitmap[64 * 64];
    unsigned pen = x;
    for (const unsigned char *p = (const unsigned char *)text; *p; p++) {
        const struct ui_glyph *glyph = ui_glyph(font, *p);
        if (glyph->width && glyph->height) {
            ui_glyph_decode(font, glyph, bitmap);
            int gx = (int)pen + glyph->left;
            int gy = (int)baseline - glyph->top;
            for (unsigned row = 0; row < glyph->height; row++) {
                for (unsigned col = 0; col < glyph->width; col++) {
                    unsigned cover = bitmap[row * glyph->width + col];
                    if (!cover) continue;
                    int sx = gx + (int)col;
                    int sy = gy + (int)row;
                    if (sx < 0 || sy < 0) continue;
                    ui_blend(screen, (unsigned)sx, (unsigned)sy, color, cover);
                }
            }
        }
        pen += glyph->advance;
    }
}

/* Draw text, stopping before the first glyph that would cross max_x. */
static void ui_text_clipped(const struct surface *screen, unsigned x,
                            unsigned baseline, unsigned size, int bold,
                            struct ui_rgb color, const char *text,
                            unsigned max_x) {
    char buffer[256];
    size_t length = 0;
    unsigned pen = x;
    const struct ui_font *font = ui_font_for(size, bold);
    for (const unsigned char *p = (const unsigned char *)text;
         *p && length + 1u < sizeof(buffer); p++) {
        unsigned advance = ui_glyph(font, *p)->advance;
        if (pen + advance > max_x) break;
        buffer[length++] = (char)*p;
        pen += advance;
    }
    buffer[length] = '\0';
    ui_text(screen, x, baseline, size, bold, color, buffer);
}

static void ui_text_centered(const struct surface *screen, unsigned center_x,
                             unsigned baseline, unsigned size, int bold,
                             struct ui_rgb color, const char *text) {
    unsigned width = ui_text_width(size, bold, text);
    unsigned x = center_x > width / 2u ? center_x - width / 2u : 0u;
    ui_text(screen, x, baseline, size, bold, color, text);
}

static unsigned long long ui_now_ms(void) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (unsigned long long)now.tv_sec * 1000ull +
           (unsigned long long)now.tv_nsec / 1000000ull;
}

/* Cubic ease-out over permille 0..1000, returned as permille. */
static unsigned ui_ease_out(unsigned permille) {
    if (permille > 1000u) permille = 1000u;
    unsigned inv = 1000u - permille;
    unsigned long long cube =
        (unsigned long long)inv * inv * inv;
    return (unsigned)(1000ull - cube / 1000000ull);
}

/* Dashboard geometry (UI_DESIGN.md: left nav rail, card content). */
static unsigned ui_rail_w(unsigned w) {
    unsigned rail = w / 6u;
    if (rail < 180u) rail = 180u;
    if (rail > 300u) rail = 300u;
    if (rail > w) rail = w;
    return rail;
}

static unsigned ui_content_x(unsigned w) { return ui_rail_w(w) + 36u; }

static unsigned ui_content_w(unsigned w) {
    unsigned x = ui_content_x(w);
    return w > x + 24u ? w - x - 24u : 0u;
}

#define UI_RAIL_TOP 108u
#define UI_RAIL_ITEM_H 40u
#define UI_RAIL_ITEM_GAP 6u
#define UI_PAGE_TOP 120u
#define UI_FILES_TOP 150u
#define UI_FILES_ROW_H 32u

static const char *const UI_PAGES[6] = {
    "STATUS", "STORAGE", "NETWORK", "TERMINAL", "SETTINGS", "FILES"
};

static unsigned ui_files_first(unsigned selected) {
    return selected > 6u ? selected - 6u : 0u;
}

static unsigned ui_files_rows(unsigned height) {
    if (height <= UI_FILES_TOP + 96u) return 1u;
    unsigned rows = (height - UI_FILES_TOP - 64u) / UI_FILES_ROW_H;
    if (rows > 8u) rows = 8u;
    return rows ? rows : 1u;
}

/* Simple geometric rail glyphs, one per page, drawn in a 16x16 box. */
static void ui_icon(const struct surface *screen, unsigned kind,
                    unsigned x, unsigned y, struct ui_rgb color,
                    struct ui_rgb behind) {
    switch (kind) {
        case 0: /* STATUS: gauge ring and needle */
            ui_ring(screen, x + 8u, y + 8u, 7u, 2u, color, behind);
            ui_circle(screen, x + 8u, y + 8u, 2u, color);
            for (unsigned i = 0; i < 4u; i++)
                ui_fill(screen, x + 9u + i, y + 6u - (i > 1u ? 1u : 0u),
                        1u, 1u, color);
            break;
        case 1: /* STORAGE: disk outline and hub */
            ui_rrect_outline(screen, x, y + 3u, 16u, 11u, 2u, color, behind);
            ui_circle(screen, x + 12u, y + 8u, 2u, color);
            break;
        case 2: /* NETWORK: globe ring and equator */
            ui_ring(screen, x + 8u, y + 8u, 7u, 2u, color, behind);
            ui_fill(screen, x + 2u, y + 7u, 12u, 2u, color);
            break;
        case 3: /* TERMINAL: prompt chevron and cursor bar */
            ui_rrect_outline(screen, x, y + 1u, 16u, 14u, 2u, color, behind);
            ui_fill(screen, x + 3u, y + 5u, 2u, 2u, color);
            ui_fill(screen, x + 4u, y + 7u, 2u, 2u, color);
            ui_fill(screen, x + 3u, y + 9u, 2u, 2u, color);
            ui_fill(screen, x + 7u, y + 11u, 5u, 2u, color);
            break;
        case 4: /* SETTINGS: gear ring and spokes */
            ui_ring(screen, x + 8u, y + 8u, 5u, 2u, color, behind);
            ui_fill(screen, x + 7u, y, 2u, 3u, color);
            ui_fill(screen, x + 7u, y + 13u, 2u, 3u, color);
            ui_fill(screen, x, y + 7u, 3u, 2u, color);
            ui_fill(screen, x + 13u, y + 7u, 3u, 2u, color);
            break;
        default: /* FILES: folder body and tab */
            ui_fill(screen, x, y + 2u, 7u, 3u, color);
            ui_rrect_outline(screen, x, y + 4u, 16u, 10u, 2u, color, behind);
            break;
    }
}

// Deliberately tiny read-only framebuffer launcher prototype. Terminal and
// privileged system actions are not exposed through this UI.
struct menu_state {
    unsigned selected;
    int page;       // -1: launcher; 0-2: read-only, 3: demo terminal
    int quit;
    int launch;
    int high_contrast;
    unsigned cursor_scale;  // 0: normal, 1: large
    int authenticated;     // fixed UID1000 graphical session only
};

static void menu_key(struct menu_state *state, unsigned code) {
    if (code == KEY_ESC) {
        if (state->page >= 0) state->page = -1;
        else state->quit = 1;
    } else if (code == KEY_BACKSPACE) {
        state->page = -1;
    } else if (state->page == 3 && code == KEY_ENTER) {
        // Explicit second action: selection alone never launches a shell.
        state->launch = 1;
    } else if (state->page == 4) {
        if (code == KEY_LEFT || code == KEY_RIGHT ||
            code == KEY_A || code == KEY_D) {
            state->high_contrast = !state->high_contrast;
        } else if (code == KEY_UP) {
            state->cursor_scale = 1u;
        } else if (code == KEY_DOWN) {
            state->cursor_scale = 0u;
        }
    } else if (state->page < 0) {
        if (code == KEY_LEFT || code == KEY_A) {
            unsigned count = state->authenticated ? 6u : 5u;
            state->selected = (state->selected + count - 1u) % count;
        } else if (code == KEY_RIGHT || code == KEY_D) {
            unsigned count = state->authenticated ? 6u : 5u;
            state->selected = (state->selected + 1u) % count;
        }
        else if (code == KEY_ENTER) state->page = (int)state->selected;
    }
}

static void render_menu(const struct surface *screen,
                        const struct menu_state *state);
static void render_private_files(const struct surface *screen,
                                 const struct synveil_file_browser *files,
                                 const struct menu_state *state);

/* Sliding page transitions (UI_DESIGN.md motion: 280 ms ease-out).
 * The outgoing frame is snapshotted and the incoming page is rendered
 * once into an offscreen surface; each step then only composites. Input
 * is never blocked: the loops keep polling, and if the target page
 * changes mid-transition the transition restarts from the frame that is
 * actually on screen. Full-screen cost rule: a transition whose slowest
 * frame exceeds 140 ms degrades the NEXT transition one level (full
 * slide, then half slide with crossfade, then crossfade only) and the
 * level that shipped is reported on stdout as SYNVEIL_UI_MOTION_LEVEL.
 * Frame skipping is inherent: progress is a function of elapsed time. */
#define UI_SLIDE_MS 280ull
#define UI_FRAME_SLOW_MS 140ull

static struct {
    int active;
    int to_page;
    int backward;
    unsigned long long start_ms;
    unsigned long long slowest_frame_ms;
    unsigned level;
    struct surface frame;
    unsigned char *old_frame;
    unsigned char *new_frame;
    size_t bytes;
} ui_anim = {.level = 1u};

static int ui_shown_page = -2; /* -2: nothing painted yet */

static int ui_anim_active(void) { return ui_anim.active; }

static int ui_anim_begin(const struct surface *screen,
                         const struct menu_state *state,
                         const struct synveil_file_browser *files) {
    size_t bytes = (size_t)screen->fixed.line_length *
                   screen->variable.yres;
    if (bytes != ui_anim.bytes) {
        free(ui_anim.old_frame);
        free(ui_anim.new_frame);
        ui_anim.old_frame = malloc(bytes);
        ui_anim.new_frame = malloc(bytes);
        ui_anim.bytes = bytes;
        if (!ui_anim.old_frame || !ui_anim.new_frame) {
            free(ui_anim.old_frame);
            free(ui_anim.new_frame);
            ui_anim.old_frame = ui_anim.new_frame = NULL;
            ui_anim.bytes = 0;
            return 0;
        }
    }
    memcpy(ui_anim.old_frame, screen->mapped, bytes);
    ui_anim.frame = *screen;
    ui_anim.frame.mapped = ui_anim.new_frame;
    ui_anim.frame.length = bytes;
    render_menu(&ui_anim.frame, state);
    if (files) render_private_files(&ui_anim.frame, files, state);
    ui_anim.to_page = state->page;
    ui_anim.backward = state->page == -1;
    ui_anim.start_ms = ui_now_ms();
    ui_anim.slowest_frame_ms = 0;
    ui_anim.active = 1;
    return 1;
}

static void ui_anim_blend_pixel(const struct surface *screen,
                                unsigned char *dst, const unsigned char *oldpx,
                                const unsigned char *newpx, unsigned alpha) {
    if (screen->variable.red.length == 8u &&
        screen->variable.green.length == 8u &&
        screen->variable.blue.length == 8u) {
        const unsigned offsets[3] = {
            screen->variable.red.offset / 8u,
            screen->variable.green.offset / 8u,
            screen->variable.blue.offset / 8u
        };
        unsigned char blended[4];
        memcpy(blended, newpx, 4u);
        for (unsigned i = 0; i < 3u; i++) {
            unsigned o = oldpx[offsets[i]];
            unsigned n = newpx[offsets[i]];
            blended[offsets[i]] = (unsigned char)(
                (o * (255u - alpha) + n * alpha + 127u) / 255u);
        }
        memcpy(dst, blended, 4u);
        return;
    }
    /* Non-8-bit-channel formats take a hard cut halfway through. */
    memcpy(dst, alpha >= 128u ? newpx : oldpx, 4u);
}

static void ui_anim_frame(const struct surface *screen) {
    unsigned long long frame_start = ui_now_ms();
    unsigned long long elapsed = frame_start - ui_anim.start_ms;
    unsigned permille = elapsed >= UI_SLIDE_MS ? 1000u :
        (unsigned)(elapsed * 1000ull / UI_SLIDE_MS);
    unsigned eased = ui_ease_out(permille);
    unsigned w = screen->variable.xres;
    unsigned h = screen->variable.yres;
    size_t stride = screen->fixed.line_length;
    if (!UI_MOTION) permille = 1000u;
    if (ui_anim.level >= 3u || !UI_MOTION) {
        unsigned alpha = eased * 255u / 1000u;
        for (unsigned y = 0; y < h; y++) {
            unsigned char *dst = screen->mapped + (size_t)y * stride;
            const unsigned char *op = ui_anim.old_frame + (size_t)y * stride;
            const unsigned char *np = ui_anim.new_frame + (size_t)y * stride;
            for (unsigned x = 0; x < w; x++) {
                ui_anim_blend_pixel(screen, dst + (size_t)x * 4u,
                                    op + (size_t)x * 4u,
                                    np + (size_t)x * 4u, alpha);
            }
        }
    } else {
        unsigned distance = ui_anim.level == 1u ? w : w / 2u;
        unsigned dx = eased * distance / 1000u;
        if (dx > w) dx = w;
        for (unsigned y = 0; y < h; y++) {
            unsigned char *dst = screen->mapped + (size_t)y * stride;
            const unsigned char *op = ui_anim.old_frame + (size_t)y * stride;
            const unsigned char *np = ui_anim.new_frame + (size_t)y * stride;
            if (!ui_anim.backward) {
                if (w > dx) memcpy(dst, op + (size_t)dx * 4u,
                                   (size_t)(w - dx) * 4u);
                if (dx) memcpy(dst + (size_t)(w - dx) * 4u, np,
                               (size_t)dx * 4u);
            } else {
                if (dx) memcpy(dst, np + (size_t)(w - dx) * 4u,
                               (size_t)dx * 4u);
                if (w > dx) memcpy(dst + (size_t)dx * 4u, op,
                                   (size_t)(w - dx) * 4u);
            }
        }
        if (ui_anim.level == 2u) {
            unsigned alpha = eased * 255u / 1000u;
            for (unsigned y = 0; y < h; y++) {
                unsigned char *dst = screen->mapped + (size_t)y * stride;
                const unsigned char *np = ui_anim.new_frame + (size_t)y * stride;
                for (unsigned x = 0; x < w; x++) {
                    unsigned char current[4];
                    memcpy(current, dst + (size_t)x * 4u, 4u);
                    ui_anim_blend_pixel(screen, dst + (size_t)x * 4u,
                                        current, np + (size_t)x * 4u, alpha);
                }
            }
        }
    }
    unsigned long long frame_ms = ui_now_ms() - frame_start;
    if (frame_ms > ui_anim.slowest_frame_ms)
        ui_anim.slowest_frame_ms = frame_ms;
    if (permille >= 1000u) {
        memcpy(screen->mapped, ui_anim.new_frame, ui_anim.bytes);
        ui_anim.active = 0;
        printf("\nSYNVEIL_UI_MOTION_LEVEL %u\n", ui_anim.level);
        fflush(stdout);
        if (ui_anim.slowest_frame_ms > UI_FRAME_SLOW_MS &&
            ui_anim.level < 3u)
            ui_anim.level++;
    }
}

/* Paint the dashboard, animating page changes. files may be NULL in the
 * unauthenticated launcher, which has no Files page. */
static void dash_paint(const struct surface *screen,
                       const struct menu_state *state,
                       const struct synveil_file_browser *files) {
    if (!UI_MOTION) {
        render_menu(screen, state);
        if (files) render_private_files(screen, files, state);
        ui_shown_page = state->page;
        return;
    }
    if (ui_anim.active) {
        if (ui_anim.to_page != state->page) {
            /* Target changed mid-flight: fall through and restart the
             * transition from whatever is currently displayed. */
            ui_anim.active = 0;
            ui_shown_page = -2;
        } else {
            ui_anim_frame(screen);
            if (!ui_anim.active) ui_shown_page = state->page;
            return;
        }
    }
    if (ui_shown_page != -2 && ui_shown_page != state->page &&
        ui_anim_begin(screen, state, files)) {
        ui_anim_frame(screen);
        if (!ui_anim.active) ui_shown_page = state->page;
        return;
    }
    render_menu(screen, state);
    if (files) render_private_files(screen, files, state);
    ui_shown_page = state->page;
}

static int mounted_state(void) {
    FILE *mounts = fopen("/proc/mounts", "r");
    if (!mounts) return 0;
    char line[512];
    int found = 0;
    while (fgets(line, sizeof(line), mounts)) {
        if (strstr(line, " /var ext4 ") != NULL) {
            found = 1;
            break;
        }
    }
    fclose(mounts);
    return found;
}

/* Detail rows for the Status/Storage/Network cards. Row baselines are
 * y + 30*n. All strings are the pre-existing readouts, unchanged. */
static void show_runtime_details(const struct surface *screen, int page,
                                 unsigned x, unsigned y,
                                 const struct ui_palette *pal) {
    char line[96];
    if (page == 0) {
        long cpus = sysconf(_SC_NPROCESSORS_ONLN);
        if (cpus > 0) {
            snprintf(line, sizeof(line), "CPU %ld THREADS", cpus);
            ui_text(screen, x, y, 14, 0, pal->dim, line);
        }
        FILE *memory = fopen("/proc/meminfo", "r");
        if (memory != NULL) {
            unsigned long long available = 0;
            char buffer[256];
            while (fgets(buffer, sizeof(buffer), memory)) {
                if (strncmp(buffer, "MemAvailable:", 13) == 0 &&
                    sscanf(buffer + 13, " %llu kB", &available) == 1) break;
            }
            fclose(memory);
            if (available > 0) {
                snprintf(line, sizeof(line), "RAM %llu MB AVAILABLE", available / 1024u);
                ui_text(screen, x, y + 30u, 14, 0, pal->dim, line);
            }
        }
        FILE *uptime = fopen("/proc/uptime", "r");
        if (uptime != NULL) {
            double seconds = 0.0;
            if (fscanf(uptime, "%lf", &seconds) == 1 &&
                seconds >= 0.0 && seconds < 1.0e12) {
                snprintf(line, sizeof(line), "UPTIME %llu MIN",
                         (unsigned long long)(seconds / 60.0));
                ui_text(screen, x, y + 60u, 14, 0, pal->dim, line);
            }
            fclose(uptime);
        }
        // PSI is a scheduler stall percentage, not CPU utilization.
        // An absent or malformed kernel source does not display fake zeroes.
        static const char *const pressure_paths[] = {
            "/proc/pressure/cpu", "/proc/pressure/memory", "/proc/pressure/io"
        };
        static const char *const pressure_labels[] = {
            "CPU", "MEM", "IO"
        };
        for (unsigned i = 0; i < 3u; i++) {
            unsigned tenths = 0u;
            if (synveil_pressure_some_avg10(pressure_paths[i], &tenths)) {
                snprintf(line, sizeof(line), "%s STALL %u.%u",
                         pressure_labels[i], tenths / 10u, tenths % 10u);
            } else {
                snprintf(line, sizeof(line), "%s STALL UNAVAILABLE",
                         pressure_labels[i]);
            }
            ui_text(screen, x, y + 90u + 30u * i, 14, 0, pal->dim, line);
        }
    } else if (page == 1 && mounted_state()) {
        struct statvfs filesystem;
        if (statvfs("/var", &filesystem) == 0 && filesystem.f_frsize != 0) {
            unsigned long long free_mb =
                (unsigned long long)filesystem.f_bavail * filesystem.f_frsize / 1048576ull;
            snprintf(line, sizeof(line), "FREE %llu MB", free_mb);
            ui_text(screen, x, y, 14, 0, pal->dim, line);
        }
    } else if (page == 2) {
        struct synveil_network_diag network;
        synveil_network_snapshot_auto("/proc/net/route",
                                      "/etc/resolv.conf", &network);
        ui_text(screen, x, y, 14, 0, pal->dim,
                !network.present ? "NETWORK UNAVAILABLE" :
                network.link_up ? "LINK READY" : "LINK DOWN");
        snprintf(line, sizeof(line), "IF %s",
                 network.interface[0] ? network.interface : "NOT DETECTED");
        ui_text(screen, x, y + 30u, 14, 0, pal->dim, line);
        snprintf(line, sizeof(line), "IP %s",
                 network.address[0] ? network.address : "NOT ASSIGNED");
        ui_text(screen, x, y + 60u, 14, 0, pal->dim, line);
        snprintf(line, sizeof(line), "GW %s",
                 network.gateway[0] ? network.gateway : "NOT ASSIGNED");
        ui_text(screen, x, y + 90u, 14, 0, pal->dim, line);
        snprintf(line, sizeof(line), "DNS %s",
                 network.dns[0] ? network.dns : "NOT ASSIGNED");
        ui_text(screen, x, y + 120u, 14, 0, pal->dim, line);
    }
}

/* The dashboard: left navigation rail plus card content, per
 * UI_DESIGN.md. Every string below is a pre-existing label or readout;
 * the redesign changes geometry, type and color only. */
static void render_menu(const struct surface *screen, const struct menu_state *state) {
    unsigned w = screen->variable.xres;
    unsigned h = screen->variable.yres;
    const struct ui_palette *pal = state->high_contrast ? &UI_HC : &UI_DARK;
    unsigned rail = ui_rail_w(w);
    unsigned cx = ui_content_x(w);
    unsigned content_w = ui_content_w(w);
    unsigned count = state->authenticated ? 6u : 5u;
    int current = state->page >= 0 ? state->page : (int)state->selected;

    ui_fill(screen, 0, 0, w, h, pal->shell);
    /* Rail: brand mark, then one item per page. */
    ui_rrect(screen, 20u, 24u, 24u, 24u, 6u, pal->accent);
    ui_text(screen, 56u, 43u, 20, 1, pal->ink, "SYNVEIL");
    for (unsigned i = 0; i < count; i++) {
        unsigned y = UI_RAIL_TOP + i * (UI_RAIL_ITEM_H + UI_RAIL_ITEM_GAP);
        int active = (int)i == current;
        if (active)
            ui_rrect(screen, 8u, y, rail - 16u, UI_RAIL_ITEM_H, 6u,
                     pal->surface_hi);
        if (active)
            ui_fill(screen, 8u, y + 10u, 3u, UI_RAIL_ITEM_H - 20u, pal->accent);
        ui_icon(screen, i, 24u, y + 12u, active ? pal->ink : pal->dim,
                active ? pal->surface_hi : pal->shell);
        ui_text(screen, 52u, y + 25u, 14, active,
                active ? pal->ink : pal->dim, UI_PAGES[i]);
    }
    ui_fill(screen, rail, 0, 1u, h, pal->stroke);

    if (state->page >= 0) {
        /* Back affordance: chevron plus the existing BACK label. */
        for (unsigned i = 0; i < 7u; i++) {
            ui_fill(screen, cx + (i < 4u ? i : 6u - i), 30u + i, 2u, 2u,
                    pal->dim);
            ui_fill(screen, cx + (i < 4u ? i : 6u - i), 44u - i, 2u, 2u,
                    pal->dim);
        }
        ui_text(screen, cx + 16u, 44u, 14, 0, pal->dim, "BACK");
        ui_text(screen, cx, 92u, 20, 1, pal->ink, UI_PAGES[state->page]);
        if (state->page == 5 && state->authenticated) {
            ui_text(screen, cx, 128u, 14, 0, pal->dim, "PRIVATE HOME");
            ui_text(screen, cx, h - 24u, 12, 0, pal->faint,
                    "ARROWS SELECT ENTER DIR BACKSPACE UP");
            return;
        }
        if (state->page == 4) {
            ui_rrect_outline(screen, cx, UI_PAGE_TOP, content_w, 76u, 8u,
                             pal->stroke, pal->surface);
            ui_text(screen, cx + 20u, UI_PAGE_TOP + 34u, 14, 1, pal->ink,
                    state->high_contrast ? "BRIGHT COLORS" : "DARK COLORS");
            ui_text(screen, cx + 20u, UI_PAGE_TOP + 58u, 12, 0, pal->faint,
                    "LEFT RIGHT TO CHANGE");
            ui_rrect_outline(screen, cx, UI_PAGE_TOP + 88u, content_w, 76u,
                             8u, pal->stroke, pal->surface);
            ui_text(screen, cx + 20u, UI_PAGE_TOP + 122u, 14, 1, pal->ink,
                    state->cursor_scale ? "LARGE POINTER" : "SMALL POINTER");
            ui_text(screen, cx + 20u, UI_PAGE_TOP + 146u, 12, 0, pal->faint,
                    "UP DOWN TO CHANGE");
            return;
        }
        if (state->page == 3) {
            ui_rrect_outline(screen, cx, UI_PAGE_TOP, content_w, 170u, 8u,
                             pal->stroke, pal->surface);
            ui_text(screen, cx + 20u, UI_PAGE_TOP + 38u, 14, 0, pal->dim,
                    state->authenticated ? "USER TERMINAL" : "NON ROOT DEMO");
            ui_rrect(screen, cx + 20u, UI_PAGE_TOP + 58u, 300u, 48u, 4u,
                     pal->accent);
            ui_text_centered(screen, cx + 20u + 150u, UI_PAGE_TOP + 90u,
                             14, 1, pal->on_accent, "OPEN TERMINAL");
            ui_text(screen, cx + 20u, UI_PAGE_TOP + 142u, 12, 0, pal->faint,
                    "ENTER TO OPEN");
            ui_text(screen, cx, h - 24u, 12, 0, pal->faint, "ESC TO GO BACK");
            return;
        }
        const char *label = "";
        if (state->page == 0) {
            label = synveil_core_health("/run/synveil/veil-core.sock") ?
                "CORE READY" : "CORE UNAVAILABLE";
        } else if (state->page == 1) {
            label = mounted_state() ? "STATE DISK MOUNTED" : "STATE DISK MISSING";
        } else {
            label = "NETWORK DETAILS";
        }
        ui_rrect_outline(screen, cx, UI_PAGE_TOP, content_w, 252u, 8u,
                         pal->stroke, pal->surface);
        ui_text(screen, cx + 20u, UI_PAGE_TOP + 38u, 14, 1, pal->ink, label);
        show_runtime_details(screen, state->page, cx + 20u,
                             UI_PAGE_TOP + 76u, pal);
        ui_text(screen, cx, h - 24u, 12, 0, pal->faint, "ESC TO GO BACK");
        return;
    }

    /* Launcher home: title plus one summary card per page. */
    ui_text(screen, cx, 92u, 20, 1, pal->ink,
            state->authenticated ? "USER DESKTOP" : "SYSTEM LAUNCHER");
    for (unsigned i = 0; i < count; i++) {
        unsigned y = UI_PAGE_TOP + i * 54u;
        int active = (int)i == current;
        ui_rrect_outline(screen, cx, y, content_w, 46u, 8u, pal->stroke,
                         active ? pal->surface_hi : pal->surface);
        ui_icon(screen, i, cx + 16u, y + 15u, active ? pal->ink : pal->dim,
                active ? pal->surface_hi : pal->surface);
        ui_text(screen, cx + 44u, y + 29u, 14, 1, pal->ink, UI_PAGES[i]);
        const char *summary = "";
        if (i == 0u) {
            summary = synveil_core_health("/run/synveil/veil-core.sock") ?
                "CORE READY" : "CORE UNAVAILABLE";
        } else if (i == 1u) {
            summary = mounted_state() ? "STATE DISK MOUNTED" :
                                        "STATE DISK MISSING";
        } else if (i == 2u) {
            summary = "NETWORK DETAILS";
        } else if (i == 3u) {
            summary = state->authenticated ? "USER TERMINAL" :
                                             "NON ROOT DEMO";
        } else if (i == 4u) {
            summary = state->high_contrast ? "BRIGHT COLORS" : "DARK COLORS";
        } else {
            summary = "PRIVATE HOME";
        }
        unsigned name_w = ui_text_width(14, 1, UI_PAGES[i]);
        ui_text(screen, cx + 60u + name_w, y + 29u, 12, 0, pal->dim, summary);
    }
    ui_text(screen, cx, h - 48u, 12, 0, pal->faint, "LEFT RIGHT ENTER");
    ui_text(screen, cx, h - 24u, 12, 0, pal->faint,
            state->authenticated ? "ESC TO LOGOUT" : "ESC TO EXIT");
}

static int event_bit(const unsigned char *bits, size_t count, unsigned bit) {
    return bit / 8u < count && (bits[bit / 8u] & (1u << (bit % 8u))) != 0;
}

// A device with only arrow keys and Enter can drive the developer menu,
// but it cannot enter a secure password. Require a real text keyboard for
// the exclusive graphical-login grab.
static int login_keyboard_capable(const unsigned char *bits, size_t count) {
    return event_bit(bits, count, KEY_A) &&
           event_bit(bits, count, KEY_Z) &&
           event_bit(bits, count, KEY_0) &&
           event_bit(bits, count, KEY_1) &&
           event_bit(bits, count, KEY_BACKSPACE) &&
           event_bit(bits, count, KEY_SPACE) &&
           event_bit(bits, count, KEY_LEFTSHIFT);
}

static int open_keyboard_policy(int password_keyboard) {
    DIR *directory = opendir("/dev/input");
    if (directory == NULL) return -1;
    struct dirent *item;
    int chosen = -1;
    while ((item = readdir(directory)) != NULL) {
        if (strncmp(item->d_name, "event", 5) != 0) continue;
        const char *digit = item->d_name + 5;
        if (*digit == '\0') continue;
        int valid = 1;
        for (const char *p = digit; *p; p++)
            if (*p < '0' || *p > '9') valid = 0;
        if (!valid) continue;
        char path[256];
        int len = snprintf(path, sizeof(path), "/dev/input/%s", item->d_name);
        if (len < 0 || (size_t)len >= sizeof(path)) continue;
        int fd = open(path, O_RDONLY | O_CLOEXEC | O_NONBLOCK | O_NOFOLLOW);
        if (fd < 0) continue;
        struct stat info;
        unsigned char bits[(KEY_MAX + 8u) / 8u] = {0};
        if (fstat(fd, &info) == 0 && S_ISCHR(info.st_mode) &&
            ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(bits)), bits) >= 0 &&
            event_bit(bits, sizeof(bits), KEY_ENTER) &&
            event_bit(bits, sizeof(bits), KEY_LEFT) &&
            event_bit(bits, sizeof(bits), KEY_RIGHT) &&
            (!password_keyboard || login_keyboard_capable(bits, sizeof(bits)))) {
            chosen = fd;
            break;
        }
        close(fd);
    }
    closedir(directory);
    return chosen;
}

static int open_keyboard(void) {
    return open_keyboard_policy(0);
}

struct pointer_device {
    int fd;
    struct input_absinfo x;
    struct input_absinfo y;
    unsigned screen_x;
    unsigned screen_y;
};

static int event_number(const char *name) {
    if (strncmp(name, "event", 5) != 0 || name[5] == '\0') return 0;
    for (const char *p = name + 5; *p; p++)
        if (*p < '0' || *p > '9') return 0;
    return 1;
}

static struct pointer_device open_pointer(void) {
    struct pointer_device pointer = {.fd = -1};
    DIR *directory = opendir("/dev/input");
    if (!directory) return pointer;
    struct dirent *item;
    while ((item = readdir(directory)) != NULL) {
        if (!event_number(item->d_name)) continue;
        char path[256];
        int len = snprintf(path, sizeof(path), "/dev/input/%s", item->d_name);
        if (len < 0 || (size_t)len >= sizeof(path)) continue;
        int fd = open(path, O_RDONLY | O_CLOEXEC | O_NONBLOCK | O_NOFOLLOW);
        if (fd < 0) continue;
        struct stat info;
        unsigned char events[(EV_MAX + 8u) / 8u] = {0};
        unsigned char keys[(KEY_MAX + 8u) / 8u] = {0};
        unsigned char axes[(ABS_MAX + 8u) / 8u] = {0};
        if (fstat(fd, &info) == 0 && S_ISCHR(info.st_mode) &&
            ioctl(fd, EVIOCGBIT(0, sizeof(events)), events) >= 0 &&
            event_bit(events, sizeof(events), EV_KEY) &&
            event_bit(events, sizeof(events), EV_ABS) &&
            ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(keys)), keys) >= 0 &&
            ioctl(fd, EVIOCGBIT(EV_ABS, sizeof(axes)), axes) >= 0 &&
            event_bit(keys, sizeof(keys), BTN_LEFT) &&
            event_bit(axes, sizeof(axes), ABS_X) &&
            event_bit(axes, sizeof(axes), ABS_Y) &&
            ioctl(fd, EVIOCGABS(ABS_X), &pointer.x) >= 0 &&
            ioctl(fd, EVIOCGABS(ABS_Y), &pointer.y) >= 0 &&
            pointer.x.maximum > pointer.x.minimum &&
            pointer.y.maximum > pointer.y.minimum) {
            pointer.fd = fd;
            break;
        }
        close(fd);
    }
    closedir(directory);
    return pointer;
}

static unsigned absolute_pixel(int value, int minimum, int maximum, unsigned extent) {
    if (maximum <= minimum || extent == 0u) return 0u;
    int64_t range = (int64_t)maximum - minimum;
    int64_t offset = (int64_t)value - minimum;
    if (offset <= 0) return 0u;
    if (offset >= range) return extent - 1u;
    return (unsigned)((uint64_t)offset * (extent - 1u) / (uint64_t)range);
}

static void menu_click(struct menu_state *state, unsigned x, unsigned y,
                       unsigned width, unsigned height) {
    unsigned cx = ui_content_x(width);
    unsigned content_w = ui_content_w(width);
    (void)height;
    if (state->page >= 0) {
        if (x >= cx && x < cx + 120u && y >= 16u && y < 56u) {
            state->page = -1;
        } else if (state->page == 3 && x >= cx + 20u && x < cx + 320u &&
                   y >= UI_PAGE_TOP + 58u && y < UI_PAGE_TOP + 106u) {
            state->launch = 1;
        } else if (state->page == 4 && x >= cx && x < cx + content_w) {
            if (y >= UI_PAGE_TOP && y < UI_PAGE_TOP + 76u)
                state->high_contrast = !state->high_contrast;
            if (y >= UI_PAGE_TOP + 88u && y < UI_PAGE_TOP + 164u)
                state->cursor_scale = !state->cursor_scale;
        }
        return;
    }
    unsigned count = state->authenticated ? 6u : 5u;
    unsigned rail = ui_rail_w(width);
    if (x >= 8u && x < rail - 8u) {
        for (unsigned i = 0; i < count; ++i) {
            unsigned top = UI_RAIL_TOP + i * (UI_RAIL_ITEM_H + UI_RAIL_ITEM_GAP);
            if (y >= top && y < top + UI_RAIL_ITEM_H) {
                state->selected = i;
                state->page = (int)i;
                return;
            }
        }
    }
    if (x >= cx && x < cx + content_w) {
        for (unsigned i = 0; i < count; ++i) {
            unsigned top = UI_PAGE_TOP + i * 54u;
            if (y >= top && y < top + 46u) {
                state->selected = i;
                state->page = (int)i;
                return;
            }
        }
    }
}

static void render_cursor(const struct surface *screen, const struct pointer_device *pointer,
                          const struct menu_state *state) {
    if (pointer->fd >= 0) {
        unsigned size = state->cursor_scale ? 16u : 9u;
        rectangle(screen, pointer->screen_x, pointer->screen_y, size, size,
                  state->high_contrast ? rgb(screen, 0, 95, 184) :
                                         rgb(screen, 76, 194, 255));
        rectangle(screen, pointer->screen_x + 2u, pointer->screen_y + 2u,
                  state->cursor_scale ? 9u : 3u, state->cursor_scale ? 9u : 3u,
                  state->high_contrast ? rgb(screen, 245, 248, 250) :
                                         rgb(screen, 32, 32, 32));
    }
}

static int launch_demo_terminal(void) {
    // Fixed binary and arguments, never a shell command or model-provided text.
    // A display crash must kill its terminal launcher, not orphan a shell.
    pid_t owner = getpid();
    pid_t process = fork();
    if (process < 0) return 1;
    if (process == 0) {
        if (synveil_parent_death_guard(owner) != 0) _exit(1);
        execl("/usr/bin/synveil-vt", "synveil-vt", "--demo-terminal", (char *)NULL);
        _exit(127);
    }
    int status = 0;
    while (waitpid(process, &status, 0) < 0) {
        if (errno == EINTR) continue;
        return 1;
    }
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}

static int run_menu(const struct surface *screen) {
    int keyboard = open_keyboard();
    if (keyboard < 0) {
        fputs("[synveil-display] evdev keyboard unavailable\n", stderr);
        return 1;
    }
    struct menu_state state = {.selected = 0u, .page = -1, .quit = 0};
    // Persist only explicit display choices. No authorization or AI policy
    // is read from this file. Without the opt-in ext4 state disk the UI works
    // exactly as before, with ephemeral settings.
    const char *const preferences_dir = "/var/lib/synveil";
    if (mounted_state()) {
        struct desktop_preferences loaded = {0};
        if (preferences_load(preferences_dir, &loaded)) {
            state.high_contrast = loaded.high_contrast;
            state.cursor_scale = loaded.cursor_scale;
            puts("\nSYNVEIL_SETTINGS_LOADED");
        }
    }
    struct pointer_device pointer = open_pointer();
    dash_paint(screen, &state, NULL);
    render_cursor(screen, &pointer, &state);
    // The serial recovery shell may already have printed a prompt without
    // a newline. Begin on a new line so CI can require a standalone marker.
    puts("\nSYNVEIL_DESKTOP_READY");
    fflush(stdout);
    while (!state.quit) {
        int old_contrast = state.high_contrast;
        unsigned old_cursor_scale = state.cursor_scale;
        struct pollfd fds[2] = {{.fd = keyboard, .events = POLLIN},
                                {.fd = pointer.fd, .events = POLLIN}};
        nfds_t count = pointer.fd >= 0 ? 2u : 1u;
        int result = poll(fds, count, ui_anim_active() ? 16 : 1000);
        if (result < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if ((fds[0].revents & (POLLERR | POLLHUP | POLLNVAL)) != 0) break;
        int redraw = (result == 0 && state.page >= 0) || ui_anim_active();
        if ((fds[0].revents & POLLIN) != 0) {
            struct input_event event;
            if (read(keyboard, &event, sizeof(event)) == (ssize_t)sizeof(event) &&
                event.type == EV_KEY && event.value == 1) {
                menu_key(&state, event.code);
                redraw = 1;
            }
        }
        if (pointer.fd >= 0 && (fds[1].revents & (POLLERR | POLLHUP | POLLNVAL)) != 0) {
            close(pointer.fd);
            pointer.fd = -1;
            redraw = 1;
        } else if (pointer.fd >= 0 && (fds[1].revents & POLLIN) != 0) {
            struct input_event event;
            if (read(pointer.fd, &event, sizeof(event)) == (ssize_t)sizeof(event)) {
                if (event.type == EV_ABS && event.code == ABS_X) {
                    pointer.screen_x = absolute_pixel(event.value, pointer.x.minimum,
                                                      pointer.x.maximum, screen->variable.xres);
                    redraw = 1;
                } else if (event.type == EV_ABS && event.code == ABS_Y) {
                    pointer.screen_y = absolute_pixel(event.value, pointer.y.minimum,
                                                      pointer.y.maximum, screen->variable.yres);
                    redraw = 1;
                } else if (event.type == EV_KEY && event.code == BTN_LEFT && event.value == 1) {
                    menu_click(&state, pointer.screen_x, pointer.screen_y,
                               screen->variable.xres, screen->variable.yres);
                    redraw = 1;
                }
            }
        }
        if (state.launch) {
            state.launch = 0;
            if (launch_demo_terminal() != 0)
                fputs("[synveil-display] demo terminal did not start or exited abnormally\n", stderr);
            state.page = -1;
            redraw = 1;
        }
        if (state.high_contrast != old_contrast ||
            state.cursor_scale != old_cursor_scale) {
            if (mounted_state()) {
                struct desktop_preferences current = {
                    .high_contrast = state.high_contrast,
                    .cursor_scale = state.cursor_scale
                };
                if (preferences_save(preferences_dir, &current) != 0) {
                    fputs("[synveil-display] could not persist display settings\n", stderr);
                } else {
                    puts("\nSYNVEIL_SETTINGS_SAVED");
                    fflush(stdout);
                }
            }
        }
        if (redraw && !state.quit) {
            dash_paint(screen, &state, NULL);
            render_cursor(screen, &pointer, &state);
        }
    }
    if (pointer.fd >= 0) close(pointer.fd);
    close(keyboard);
    return state.quit ? 0 : 1;
}


// The authenticated VM session never opens privileged devices itself.
// Root-owned veil-seat launched a fixed VT helper which passed only fbdev
// descriptor 3 before dropping to UID/GID 1000. Read input from its own
// controlling tty1 in raw mode; no input-device permissions are relaxed.
// The menu does not accept command strings, identities or credentials.
static unsigned session_input_code(unsigned char byte) {
    switch (byte) {
        case '\r': case '\n': return KEY_ENTER;
        case 8: case 127: return KEY_BACKSPACE;
        case 27: return KEY_ESC;
        case 'a': case 'A': return KEY_A;
        case 'd': case 'D': return KEY_D;
        case 'h': case 'H': return KEY_LEFT;
        case 'l': case 'L': return KEY_RIGHT;
        case 'k': case 'K': return KEY_UP;
        case 'j': case 'J': return KEY_DOWN;
        default: return 0u;
    }
}

static unsigned session_read_key(void) {
    unsigned char byte;
    ssize_t got = read(STDIN_FILENO, &byte, 1u);
    // A closed/failed tty must exit the session and revoke its seat lease.
    if (got != 1) return UINT_MAX;
    if (byte != 27u) return session_input_code(byte);
    struct pollfd fd = {.fd = STDIN_FILENO, .events = POLLIN};
    if (poll(&fd, 1u, 25) != 1) return KEY_ESC;
    if (read(STDIN_FILENO, &byte, 1u) != 1 || byte != '[') return KEY_ESC;
    if (poll(&fd, 1u, 25) != 1) return KEY_ESC;
    if (read(STDIN_FILENO, &byte, 1u) != 1) return KEY_ESC;
    switch (byte) {
        case 'A': return KEY_UP;
        case 'B': return KEY_DOWN;
        case 'C': return KEY_RIGHT;
        case 'D': return KEY_LEFT;
        default: return KEY_ESC;
    }
}

// A non-root, fixed executable only. The running graphical session retains
// the seat lease through its root-owned parent, and the shell inherits no
// framebuffer descriptor. It can write in its own home, never as root.
static int session_terminal(const struct termios *original) {
    if (tcsetattr(STDIN_FILENO, TCSANOW, original) != 0) return -1;
    const char banner[] = "\033[2J\033[HSynveil user terminal (UID 1000)\r\n"
                          "Type exit to return to your desktop.\r\n";
    // glibc marks write() warn_unused_result; a short write must not
    // silently advance to an interactive shell with a broken tty.
    if (write(STDOUT_FILENO, banner, sizeof(banner)-1u) !=
        (ssize_t)(sizeof(banner)-1u)) return -1;
    pid_t owner = getpid();
    pid_t child = fork();
    if (child < 0) return -1;
    if (child == 0) {
        // No open framebuffer passed to arbitrary shell subprocesses.
        close(3);
        if (synveil_parent_death_guard(owner) != 0) _exit(1);
        execl("/bin/sh", "sh", "-i", (char *)NULL);
        _exit(127);
    }
    int status = 0;
    while (waitpid(child, &status, 0) < 0) {
        if (errno == EINTR) continue;
        return -1;
    }
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}

// The privileged VT helper supplies an optional, capability-checked
// absolute pointer as FD5. Never open arbitrary /dev/input as UID1000.
static struct pointer_device session_pointer(void) {
    struct pointer_device pointer = {.fd = -1};
    int fd = fcntl(5, F_DUPFD_CLOEXEC, 9);
    // Never retain an inheritable copy of the seat's pointer device.
    close(5);
    if (fd < 0) return pointer;
    struct stat info;
    if (fstat(fd, &info) != 0 || !S_ISCHR(info.st_mode) ||
        ioctl(fd, EVIOCGABS(ABS_X), &pointer.x) < 0 ||
        ioctl(fd, EVIOCGABS(ABS_Y), &pointer.y) < 0 ||
        pointer.x.maximum <= pointer.x.minimum ||
        pointer.y.maximum <= pointer.y.minimum) {
        close(fd);
        return pointer;
    }
    pointer.fd = fd;
    return pointer;
}

// Display only non-sensitive, read-only directory labels in a UID1000
// authenticated session. The login VT and unauthenticated demo menu cannot
// call this painter or open the file browser.
static void render_private_files(const struct surface *screen,
                                 const struct synveil_file_browser *files,
                                 const struct menu_state *state) {
    if (!state->authenticated || state->page != 5) return;
    unsigned h = screen->variable.yres;
    unsigned cx = ui_content_x(screen->variable.xres);
    unsigned content_w = ui_content_w(screen->variable.xres);
    const struct ui_palette *pal = state->high_contrast ? &UI_HC : &UI_DARK;
    if (!files->available) {
        ui_text(screen, cx, UI_FILES_TOP + 21u, 14, 0, pal->dim,
                "FILES UNAVAILABLE");
        return;
    }
    if (!files->count) {
        ui_text(screen, cx, UI_FILES_TOP + 21u, 14, 0, pal->dim,
                "EMPTY DIRECTORY");
        return;
    }
    unsigned first = ui_files_first(files->selected);
    unsigned rows = files->count - first;
    unsigned max_rows = ui_files_rows(h);
    if (rows > max_rows) rows = max_rows;
    for (unsigned row = 0u; row < rows; row++) {
        unsigned index = first + row;
        unsigned y = UI_FILES_TOP + row * UI_FILES_ROW_H;
        if (index == files->selected)
            ui_rrect(screen, cx > 6u ? cx - 6u : 0u, y, content_w + 12u,
                     UI_FILES_ROW_H, 6u, pal->select);
        ui_text(screen, cx + 8u, y + 21u, 12, 1, pal->faint,
                files->entries[index].directory ? "DIR" : "FILE");
        /* File names keep their real case; bytes outside printable ASCII
         * render as '?' inside the text layer. */
        ui_text_clipped(screen, cx + 64u, y + 21u, 14, 0, pal->ink,
                        files->entries[index].name, cx + content_w);
    }
    if (files->truncated)
        ui_text(screen, cx, h - 48u, 12, 0, pal->faint,
                "MORE FILES NOT SHOWN");
}

static int run_user_session(const struct surface *screen) {
    if (geteuid() != 1000 || getuid() != 1000 || !isatty(STDIN_FILENO))
        return 1;
    // User programs launched in the fixed shell have the same UID and could
    // otherwise ptrace the dashboard to read its mapped framebuffer or
    // injected input state. Refuse the session if the kernel cannot block
    // same-UID introspection of the privileged seat's delegated resources.
    if (synveil_protect_authenticated_ui() != 0) return 1;
    struct termios original, raw;
    if (tcgetattr(STDIN_FILENO, &original) != 0) return 1;
    raw = original;
    cfmakeraw(&raw);
    if (tcsetattr(STDIN_FILENO, TCSANOW, &raw) != 0) return 1;
    struct menu_state state = {.selected = 0u, .page = -1, .authenticated = 1};
    // This is user-owned data under the UID1000 private home. Never use
    // root-owned global display preferences as a session authorization input.
    struct desktop_preferences saved = {0};
    if (preferences_load("/home/synveil", &saved)) {
        state.high_contrast = saved.high_contrast;
        state.cursor_scale = saved.cursor_scale;
    }
    struct pointer_device pointer = session_pointer();
    struct synveil_file_browser files;
    (void)synveil_files_open(&files, "/home/synveil");
    dash_paint(screen, &state, &files);
    render_cursor(screen, &pointer, &state);
    puts("\nSYNVEIL_USER_DESKTOP_READY");
    fflush(stdout);
    int result = 0;
    while (!state.quit) {
        struct pollfd fds[2] = {
            {.fd = STDIN_FILENO, .events = POLLIN},
            {.fd = pointer.fd, .events = POLLIN},
        };
        nfds_t count = pointer.fd >= 0 ? 2u : 1u;
        int activity = poll(fds, count, ui_anim_active() ? 16 : -1);
        if (activity < 0 && errno == EINTR) continue;
        if (activity < 0 || (fds[0].revents & (POLLERR | POLLHUP | POLLNVAL))) {
            result = 1;
            break;
        }
        int old_contrast = state.high_contrast;
        unsigned old_cursor = state.cursor_scale;
        if (fds[0].revents & POLLIN) {
            unsigned code = session_read_key();
            if (code == UINT_MAX) {
                result = 1;
                break;
            }
            if (code && state.page == 5) {
                if (code == KEY_UP && files.available && files.count) {
                    synveil_files_select(&files,
                        (files.selected + files.count - 1u) % files.count);
                } else if (code == KEY_DOWN && files.available && files.count) {
                    synveil_files_select(&files, (files.selected + 1u) % files.count);
                } else if (code == KEY_ENTER) {
                    (void)synveil_files_enter(&files);
                } else if (code == KEY_BACKSPACE) {
                    if (synveil_files_back(&files) != 0) state.page = -1;
                } else if (code == KEY_ESC) {
                    state.page = -1;
                }
            } else if (code) {
                menu_key(&state, code);
            }
        }
        if (pointer.fd >= 0 && (fds[1].revents & (POLLERR | POLLHUP | POLLNVAL))) {
            close(pointer.fd);
            pointer.fd = -1;
        } else if (pointer.fd >= 0 && (fds[1].revents & POLLIN)) {
            struct input_event event;
            ssize_t n = read(pointer.fd, &event, sizeof(event));
            if (n == (ssize_t)sizeof(event)) {
                if (event.type == EV_ABS && event.code == ABS_X)
                    pointer.screen_x = absolute_pixel(event.value, pointer.x.minimum,
                                                      pointer.x.maximum, screen->variable.xres);
                else if (event.type == EV_ABS && event.code == ABS_Y)
                    pointer.screen_y = absolute_pixel(event.value, pointer.y.minimum,
                                                      pointer.y.maximum, screen->variable.yres);
                else if (event.type == EV_KEY && event.code == BTN_LEFT && event.value == 1) {
                    if (state.page == 5 && files.available &&
                        pointer.screen_y >= UI_FILES_TOP &&
                        pointer.screen_y < UI_FILES_TOP +
                            ui_files_rows(screen->variable.yres) * UI_FILES_ROW_H) {
                        unsigned first = ui_files_first(files.selected);
                        unsigned index = first +
                            (pointer.screen_y - UI_FILES_TOP) / UI_FILES_ROW_H;
                        if (index < files.count)
                            synveil_files_select(&files, index);
                    } else {
                        menu_click(&state, pointer.screen_x, pointer.screen_y,
                                   screen->variable.xres, screen->variable.yres);
                    }
                }
            } else if (n == 0 || (n < 0 && errno != EAGAIN && errno != EINTR)) {
                close(pointer.fd);
                pointer.fd = -1;
            }
        }
        if (state.launch) {
            state.launch = 0;
            if (session_terminal(&original) < 0) {
                result = 1;
                break;
            }
            if (tcsetattr(STDIN_FILENO, TCSANOW, &raw) != 0) {
                result = 1;
                break;
            }
            state.page = -1;
        }
        if (state.high_contrast != old_contrast ||
            state.cursor_scale != old_cursor) {
            struct desktop_preferences prefs = {
                .high_contrast = state.high_contrast,
                .cursor_scale = state.cursor_scale
            };
            (void)preferences_save("/home/synveil", &prefs);
        }
        if (!state.quit) {
            dash_paint(screen, &state, &files);
            render_cursor(screen, &pointer, &state);
        }
    }
    synveil_files_close(&files);
    if (pointer.fd >= 0) close(pointer.fd);
    (void)tcsetattr(STDIN_FILENO, TCSANOW, &original);
    puts("\nSYNVEIL_USER_DESKTOP_EXITED");
    fflush(stdout);
    return result;
}

// Experimental *developer-only* graphical login client for veil-seat.
// Never renders raw password bytes, grants root commands or authorizes a
// session itself. A production compositor/input isolation layer is pending.
// Match the verifier's byte-size bound, not a shorter UI-only limit.
#define AUTH_MAX_UI_PASSWORD 1024u
#define AUTH_SEAT_SOCKET "/run/synveil/veil-seat.sock"
// Dedicated graphical login VT. Authenticated shells temporarily use tty1.
// Returning to tty2 is required: merely repainting /dev/fb0 while fbcon
// still owns tty1 can expose the preceding terminal or hide the login.
#define AUTH_LOGIN_VT 2

// An unbounded VT_WAITACTIVE can strand the graphical supervisor if a
// broken VT cannot activate. Check kernel VT state for at most two seconds.
// On failure exit to the bounded desktop supervisor; never declare relock.
#define AUTH_VT_RESTORE_TIMEOUT_SEC 2
#define AUTH_VT_RESTORE_POLL_MS 25

static int auth_vt_restore_expired(const struct timespec *start,
                                   const struct timespec *now) {
    time_t seconds = now->tv_sec - start->tv_sec;
    long nanoseconds = now->tv_nsec - start->tv_nsec;
    return seconds > AUTH_VT_RESTORE_TIMEOUT_SEC ||
           (seconds == AUTH_VT_RESTORE_TIMEOUT_SEC && nanoseconds >= 0);
}

static int auth_restore_login_vt(void) {
    int controller = open("/dev/tty0", O_RDWR | O_CLOEXEC | O_NOCTTY);
    if (controller < 0) return -1;
    int result = -1;
    struct timespec start;
    if (ioctl(controller, VT_ACTIVATE, AUTH_LOGIN_VT) == 0 &&
        clock_gettime(CLOCK_MONOTONIC, &start) == 0) {
        for (;;) {
            struct vt_stat current = {0};
            if (ioctl(controller, VT_GETSTATE, &current) != 0) break;
            if (current.v_active == AUTH_LOGIN_VT) {
                int login_tty = open("/dev/tty2", O_RDWR | O_CLOEXEC |
                                    O_NOCTTY | O_NOFOLLOW | O_NONBLOCK);
                if (login_tty >= 0) {
                    result = synveil_login_vt_quiet(login_tty);
                    close(login_tty);
                }
                break;
            }
            struct timespec now;
            if (clock_gettime(CLOCK_MONOTONIC, &now) != 0 ||
                auth_vt_restore_expired(&start, &now)) break;
            if (poll(NULL, 0u, AUTH_VT_RESTORE_POLL_MS) < 0 && errno != EINTR)
                break;
        }
    }
    close(controller);
    return result;
}

// The kernel refuses to switch away from a VT_AUTO console that is in
// KD_GRAPHICS (set_console() in the VT layer): the login VT's graphics
// mode, which protects the greeter's scanout while it waits for input,
// would otherwise turn the authenticated session's VT_ACTIVATE into a
// permanent no-op and the session could never start. The login flow
// owns this VT's mode, so it drops the VT to KD_TEXT for the handoff;
// auth_restore_login_vt() re-applies K_OFF + KD_GRAPHICS when the
// session ends. Fail closed: if the mode cannot be dropped, the caller
// does not attempt a session.
static int auth_handoff_login_vt(void) {
    int login_tty = open("/dev/tty2", O_RDWR | O_CLOEXEC | O_NOCTTY |
                         O_NOFOLLOW | O_NONBLOCK);
    if (login_tty < 0) return -1;
    int result = -1;
    int display_mode = -1;
    if (ioctl(login_tty, KDSETMODE, KD_TEXT) == 0 &&
        ioctl(login_tty, KDGETMODE, &display_mode) == 0 &&
        display_mode == KD_TEXT) result = 0;
    close(login_tty);
    return result;
}

static int auth_open_private_keyboard(void) {
    int keyboard = open_keyboard_policy(1);
    if (keyboard < 0) return -1;
    // The login VT is K_OFF, so waiting for release cannot echo passwords.
    // Grabbing a held VT-switch chord could hide its releases from Linux's
    // console modifier state. Wait for idle, grab, drain and recheck instead.
    // Closing this FD before launching releases the exclusive grab.
    if (synveil_login_keyboard_grab(keyboard) != 0) {
        close(keyboard);
        return -1;
    }
    return keyboard;
}

struct auth_input {
    unsigned char password[AUTH_MAX_UI_PASSWORD];
    unsigned length;
    unsigned shift;     // bit 0 = left, bit 1 = right
    int caps_lock;      // only affects letters, not symbols
    int denied;
    unsigned long long denied_at_ms;  // shake clock; 0 = no denial shown
    int keyboard_missing;
    // 0: normal login; 1: first password; 2: repeat password.
    unsigned enroll_stage;
};

static void auth_clear(struct auth_input *state) {
    // Force wiping the UI-side secret even under compiler optimization.
    volatile unsigned char *bytes = state->password;
    for (unsigned i = 0; i < AUTH_MAX_UI_PASSWORD; i++) bytes[i] = 0u;
    state->length = 0u;
    // Evdev is closed while the terminal owns the seat; old held-key
    // events cannot remain logically pressed after that device is reopened.
    state->shift = 0u;
}

// Device loss must never keep a partially entered password, held Shift,
// previous denial or stale Caps Lock state. Reacquisition requires EVIOCGRAB.
static void auth_keyboard_disconnected(struct auth_input *state) {
    auth_clear(state);
    state->caps_lock = 0;
    state->denied = 0;
    state->denied_at_ms = 0;
    state->keyboard_missing = 1;
}

static void auth_keyboard_connected(struct auth_input *state) {
    auth_clear(state);
    state->caps_lock = 0;
    state->denied = 0;
    state->denied_at_ms = 0;
    state->keyboard_missing = 0;
}

static unsigned char auth_key_char(unsigned code, int shift) {
    const struct {unsigned key; unsigned char value;} keys[] = {
        {KEY_A,'a'}, {KEY_B,'b'}, {KEY_C,'c'}, {KEY_D,'d'},
        {KEY_E,'e'}, {KEY_F,'f'}, {KEY_G,'g'}, {KEY_H,'h'},
        {KEY_I,'i'}, {KEY_J,'j'}, {KEY_K,'k'}, {KEY_L,'l'},
        {KEY_M,'m'}, {KEY_N,'n'}, {KEY_O,'o'}, {KEY_P,'p'},
        {KEY_Q,'q'}, {KEY_R,'r'}, {KEY_S,'s'}, {KEY_T,'t'},
        {KEY_U,'u'}, {KEY_V,'v'}, {KEY_W,'w'}, {KEY_X,'x'},
        {KEY_Y,'y'}, {KEY_Z,'z'}
    };
    for (unsigned i = 0; i < sizeof(keys)/sizeof(keys[0]); i++) {
        if (keys[i].key == code) {
            return (unsigned char)(shift ? keys[i].value - ('a'-'A') : keys[i].value);
        }
    }
    const struct {unsigned key; unsigned char normal; unsigned char shifted;} symbols[] = {
        {KEY_1,'1','!'}, {KEY_2,'2','@'}, {KEY_3,'3','#'},
        {KEY_4,'4','$'}, {KEY_5,'5','%'}, {KEY_6,'6','^'},
        {KEY_7,'7','&'}, {KEY_8,'8','*'}, {KEY_9,'9','('},
        {KEY_0,'0',')'}, {KEY_MINUS,'-','_'}, {KEY_EQUAL,'=','+'},
        {KEY_DOT,'.','>'}, {KEY_COMMA,',','<'}, {KEY_SLASH,'/','?'},
        {KEY_SPACE,' ',' '}, {KEY_SEMICOLON,';',':'},
        {KEY_APOSTROPHE,39u,34u},
        {KEY_LEFTBRACE,'[','{'}, {KEY_RIGHTBRACE,']','}'},
        {KEY_BACKSLASH,92u,'|'}, {KEY_GRAVE,96u,'~'},
        {KEY_KP0,'0','0'}, {KEY_KP1,'1','1'},
        {KEY_KP2,'2','2'}, {KEY_KP3,'3','3'},
        {KEY_KP4,'4','4'}, {KEY_KP5,'5','5'},
        {KEY_KP6,'6','6'}, {KEY_KP7,'7','7'},
        {KEY_KP8,'8','8'}, {KEY_KP9,'9','9'},
        {KEY_KPDOT,'.','.'}, {KEY_KPSLASH,'/','/'},
        {KEY_KPASTERISK,'*','*'}, {KEY_KPMINUS,'-','-'},
        {KEY_KPPLUS,'+','+'}
    };
    for (unsigned i = 0; i < sizeof(symbols)/sizeof(symbols[0]); i++) {
        if (symbols[i].key == code)
            return shift ? symbols[i].shifted : symbols[i].normal;
    }
    return 0u;
}

static void auth_input_key(struct auth_input *state, unsigned code, int value) {
    if (code == KEY_LEFTSHIFT || code == KEY_RIGHTSHIFT) {
        unsigned bit = code == KEY_LEFTSHIFT ? 1u : 2u;
        if (value == 0) state->shift &= ~bit;
        else if (value == 1) state->shift |= bit;
        return;
    }
    if (value != 1) return;
    if (code == KEY_CAPSLOCK) {
        state->caps_lock = !state->caps_lock;
        return;
    }
    if (code == KEY_BACKSPACE) {
        if (state->length) {
            state->length--;
            state->password[state->length] = 0;
        }
        return;
    }
    // Caps Lock only modifies alpha keys. Shift still selects punctuation.
    int shifted = state->shift != 0u;
    unsigned char letter = auth_key_char(code, shifted);
    if (letter >= 'a' && letter <= 'z' && state->caps_lock)
        letter = (unsigned char)(letter - ('a' - 'A'));
    else if (letter >= 'A' && letter <= 'Z' && state->caps_lock)
        letter = (unsigned char)(letter + ('a' - 'A'));
    if (letter && state->length < AUTH_MAX_UI_PASSWORD) {
        state->password[state->length++] = letter;
        state->denied = 0;
    }
}

/* Record a denial and start the wrong-password shake clock. The denial
 * itself is decided by the caller exactly as before; this only stamps
 * the presentation timing. */
static void auth_note_denied(struct auth_input *state) {
    state->denied = 1;
    state->denied_at_ms = ui_now_ms();
}

#define AUTH_SHAKE_MS 200ull

static int auth_shake_active(const struct auth_input *state) {
    return state->denied && state->denied_at_ms &&
           ui_now_ms() - state->denied_at_ms < AUTH_SHAKE_MS;
}

/* Horizontal shake offset: +-8 px decaying over 200 ms (UI_DESIGN.md). */
static int auth_shake_dx(const struct auth_input *state) {
    static const int offsets[4] = {8, -8, 5, -3};
    if (!auth_shake_active(state)) return 0;
    unsigned long long elapsed = ui_now_ms() - state->denied_at_ms;
    return offsets[(elapsed / 50ull) & 3ull];
}

/* Centered login composition (UI_DESIGN.md): desktop gradient, avatar
 * circle with the owner initial, owner name, one 320x36 password field.
 * Every string is a pre-existing greeter string, unchanged. Rendering
 * only: no credential handling lives here, and the field shows one dot
 * per entered character, never the secret itself. */
static void auth_render(const struct surface *screen, const struct auth_input *state) {
    unsigned w = screen->variable.xres;
    unsigned h = screen->variable.yres;
    const struct ui_palette *pal = &UI_DARK;
    unsigned center_x = w / 2u;
    int shake = auth_shake_dx(state);
    unsigned field_x = center_x > 160u ? center_x - 160u : 0u;
    if (shake > 0) field_x += (unsigned)shake;
    else if (shake < 0) field_x = field_x > (unsigned)-shake ?
        field_x - (unsigned)-shake : 0u;
    unsigned field_y = h * 2u / 5u + 40u;

    ui_gradient(screen, pal->grad_near, pal->grad_far);
    if (state->enroll_stage) {
        ui_text_centered(screen, center_x, h / 4u, 20, 1, pal->ink,
                         "FIRST USER SETUP");
        ui_text_centered(screen, center_x, h / 4u + 34u, 14, 0, pal->dim,
                         state->enroll_stage == 1u ? "CREATE PASSWORD" :
                                                     "RETYPE PASSWORD");
    } else {
        unsigned avatar_y = h / 4u + 64u;
        ui_circle(screen, center_x, avatar_y, 64u, pal->surface_hi);
        ui_text_centered(screen, center_x, avatar_y + 17u, 48, 0, pal->ink,
                         "S");
        ui_text_centered(screen, center_x, avatar_y + 64u + 56u, 32, 0,
                         pal->ink, "Synveil");
        ui_text_centered(screen, center_x, avatar_y + 64u + 84u, 14, 0,
                         pal->dim, "LOCAL LOGIN");
        field_y = avatar_y + 64u + 104u;
    }
    /* Password field: surface fill, stroke outline, accent focus bar. */
    ui_rrect_outline(screen, field_x, field_y, 320u, 36u, 4u,
                     pal->stroke, pal->field);
    ui_fill(screen, field_x + 10u, field_y + 33u, 300u, 2u, pal->accent);
    /* Constant glyph per character, never a raw or encoded secret. */
    unsigned visible = state->length < 22u ? state->length : 22u;
    for (unsigned i = 0; i < visible; i++)
        ui_circle(screen, field_x + 18u + i * 13u, field_y + 17u, 3u,
                  pal->ink);
    unsigned message_y = field_y + 70u;
    if (state->caps_lock)
        ui_text_centered(screen, center_x, message_y, 14, 0, pal->dim,
                         "CAPS LOCK ON");
    if (state->length >= AUTH_MAX_UI_PASSWORD)
        ui_text_centered(screen, center_x, message_y + 26u, 14, 0,
                         pal->dim, "PASSWORD LIMIT");
    if (state->keyboard_missing) {
        ui_text_centered(screen, center_x, message_y + 52u, 14, 0, pal->dim,
                         "KEYBOARD DISCONNECTED");
        ui_text_centered(screen, center_x, message_y + 78u, 14, 0, pal->dim,
                         "RECONNECT TO CONTINUE");
    } else if (state->denied) {
        ui_text_centered(screen, center_x, message_y + 52u, 14, 0, pal->ink,
                         state->enroll_stage ? "SETUP RETRY" : "LOGIN DENIED");
    }
    ui_text_centered(screen, center_x, h * 4u / 5u, 12, 0, pal->faint,
                     state->enroll_stage ? "ENTER TO CONTINUE" :
                                           "ENTER TO LOGIN");
    ui_text_centered(screen, center_x, h * 4u / 5u + 22u, 12, 0, pal->faint,
                     "ESC TO CLEAR");
}

static int auth_send_all(int fd, const unsigned char *bytes, size_t len) {
    while (len) {
        ssize_t n = send(fd, bytes, len, MSG_NOSIGNAL);
        if (n <= 0) return -1;
        bytes += (size_t)n;
        len -= (size_t)n;
    }
    return 0;
}

// A receive timeout per syscall can be extended by a slow/misbehaving seat
// peer. Keep the entire short authorization response within one deadline.
// poll() and MSG_DONTWAIT also prevent an accidental blocking recv after
// readiness changes.
static int auth_receive_response(int fd, unsigned char *buffer, size_t length,
                                 long timeout_ms) {
    struct timespec start;
    if (clock_gettime(CLOCK_MONOTONIC, &start) != 0) return -1;
    size_t read_bytes = 0;
    while (read_bytes < length) {
        struct timespec now;
        if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return -1;
        long long elapsed_ms = (long long)(now.tv_sec - start.tv_sec) * 1000LL +
                               (now.tv_nsec - start.tv_nsec) / 1000000LL;
        if (elapsed_ms >= timeout_ms) return -1;
        struct pollfd ready = {.fd = fd, .events = POLLIN};
        int result = poll(&ready, 1u, (int)(timeout_ms - elapsed_ms));
        if (result < 0 && errno == EINTR) continue;
        if (result <= 0 || !(ready.revents & POLLIN)) return -1;
        ssize_t got = recv(fd, buffer + read_bytes, length - read_bytes, MSG_DONTWAIT);
        if (got < 0 && (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK))
            continue;
        if (got <= 0) return -1;
        read_bytes += (size_t)got;
    }
    return 0;
}

static int auth_attempt(struct auth_input *state) {
    int connected = -1;
    if (state->length < 8u) goto denied;
    connected = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (connected < 0) goto denied;
    struct timeval limit = {.tv_sec = 4, .tv_usec = 0};
    if (setsockopt(connected, SOL_SOCKET, SO_SNDTIMEO, &limit, sizeof(limit)) != 0 ||
        setsockopt(connected, SOL_SOCKET, SO_RCVTIMEO, &limit, sizeof(limit)) != 0)
        goto denied;
    struct sockaddr_un addr = {0};
    addr.sun_family = AF_UNIX;
    const char *name = AUTH_SEAT_SOCKET;
    if (strlen(name) >= sizeof(addr.sun_path)) goto denied;
    memcpy(addr.sun_path, name, strlen(name)+1u);
    if (connect(connected, (struct sockaddr *)&addr, sizeof(addr)) != 0) goto denied;
    // The broker uses a network-order u16 length (8..1024).
    unsigned char header[] = {
        'S','V','L','1',
        (unsigned char)(state->length >> 8u),
        (unsigned char)(state->length & 0xffu)
    };
    if (auth_send_all(connected, header, sizeof(header)) != 0 ||
        auth_send_all(connected, state->password, state->length) != 0)
        goto denied;
    auth_clear(state);
    // The broker sends only ACTIVE/DENIED/THROTTLED; never a token.
    unsigned char response[7] = {0};
    if (auth_receive_response(connected, response, sizeof(response), 4000) != 0 ||
        memcmp(response, "ACTIVE\n", sizeof(response)) != 0) goto denied;
    puts("\nSYNVEIL_GRAPHICAL_AUTH_ACTIVE");
    fflush(stdout);
    // This open descriptor is the lease. On a UI crash the OS closes the
    // socket and veil-seat immediately revokes the unprivileged VT session.
    limit.tv_sec = 1;
    if (setsockopt(connected, SOL_SOCKET, SO_RCVTIMEO, &limit, sizeof(limit)) != 0)
        goto denied;
    for (;;) {
        unsigned char discard[16];
        ssize_t n = recv(connected, discard, sizeof(discard), 0);
        if (n == 0) break;
        if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) continue;
        if (n < 0) break;
        if (n > 0) break;
    }
    close(connected);
    return 1;

denied:
    auth_clear(state);
    if (connected >= 0) close(connected);
    return 0;
}

static int run_auth_login(const struct surface *screen) {
    // Fail closed if the graphical login cannot own a dedicated VT.
    if (auth_restore_login_vt() != 0) return 1;
    int keyboard = auth_open_private_keyboard();
    struct auth_input state = {0};
    // Only immutable auth images without the unsafe developer serial
    // override may perform first-user credential setup.
    state.enroll_stage = synveil_enroll_can_start() ? 1u : 0u;
    unsigned char first_password[AUTH_MAX_UI_PASSWORD] = {0};
    size_t first_length = 0u;
    if (keyboard < 0) auth_keyboard_disconnected(&state);
    auth_render(screen, &state);
    if (keyboard >= 0) {
        puts(state.enroll_stage ? "\nSYNVEIL_ENROLL_READY" :
             "\nSYNVEIL_LOGIN_READY");
    } else {
        puts("\nSYNVEIL_LOGIN_INPUT_UNAVAILABLE");
    }
    fflush(stdout);
    // Remain locked through missing/unplugged keyboards. Bounded restarts
    // cannot repair a keyboard absent for more than a few seconds, but
    // retrying the exclusive grab every second can recover a hotplug.
    // Never continue with a partially typed secret across device changes.
    for (;;) {
        if (keyboard < 0) {
            if (poll(NULL, 0u, 1000) < 0 && errno != EINTR) break;
            keyboard = auth_open_private_keyboard();
            if (keyboard < 0) continue;
            auth_keyboard_connected(&state);
            synveil_enroll_wipe(first_password, sizeof(first_password));
            first_length = 0u;
            state.enroll_stage = synveil_enroll_can_start() ? 1u : 0u;
            auth_render(screen, &state);
            puts(state.enroll_stage ? "\nSYNVEIL_ENROLL_READY" :
                 "\nSYNVEIL_LOGIN_READY");
            fflush(stdout);
            continue;
        }
        struct pollfd fd = {.fd = keyboard, .events = POLLIN};
        int n = poll(&fd, 1u, auth_shake_active(&state) ? 10 : 1000);
        if (n < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (n == 0) {
            // Virtio framebuffer scanout is asynchronous. If the initial
            // paint was missed during VT activation, maintain a visible
            // locked greeter without accepting input or changing auth state.
            // One masked repaint per second avoids a busy redraw loop.
            auth_render(screen, &state);
            continue;
        }
        if (fd.revents & (POLLERR | POLLHUP | POLLNVAL)) {
            close(keyboard);
            keyboard = -1;
            synveil_enroll_wipe(first_password, sizeof(first_password));
            first_length = 0u;
            state.enroll_stage = synveil_enroll_can_start() ? 1u : 0u;
            auth_keyboard_disconnected(&state);
            auth_render(screen, &state);
            puts("\nSYNVEIL_LOGIN_INPUT_UNAVAILABLE");
            fflush(stdout);
            continue;
        }
        if ((fd.revents & POLLIN) == 0) continue;
        struct input_event event;
        ssize_t received = read(keyboard, &event, sizeof(event));
        if (received != (ssize_t)sizeof(event)) {
            if (received < 0 && (errno == EINTR || errno == EAGAIN ||
                                 errno == EWOULDBLOCK)) continue;
            close(keyboard);
            keyboard = -1;
            synveil_enroll_wipe(first_password, sizeof(first_password));
            first_length = 0u;
            state.enroll_stage = synveil_enroll_can_start() ? 1u : 0u;
            auth_keyboard_disconnected(&state);
            auth_render(screen, &state);
            puts("\nSYNVEIL_LOGIN_INPUT_UNAVAILABLE");
            fflush(stdout);
            continue;
        }
        if (event.type != EV_KEY) continue;
        if (event.value == 1 && event.code == KEY_ESC) {
            auth_clear(&state);
            synveil_enroll_wipe(first_password, sizeof(first_password));
            first_length = 0u;
            if (state.enroll_stage) state.enroll_stage = 1u;
            state.denied = 0;
            state.denied_at_ms = 0;
        } else if (event.value == 1 &&
                   (event.code == KEY_ENTER || event.code == KEY_KPENTER)) {
            if (state.enroll_stage == 1u) {
                if (state.length >= 8u) {
                    memcpy(first_password, state.password, state.length);
                    first_length = state.length;
                    auth_clear(&state);
                    state.enroll_stage = 2u;
                    state.denied = 0;
                    auth_render(screen, &state);
                    puts("\nSYNVEIL_ENROLL_CONFIRM_READY");
                    fflush(stdout);
                } else {
                    auth_clear(&state);
                    auth_note_denied(&state);
                    auth_render(screen, &state);
                }
                continue;
            }
            if (state.enroll_stage == 2u) {
                int matched = synveil_enroll_matches(first_password, first_length,
                                                     state.password, state.length);
                // Keep EVIOCGRAB during fixed root enroller subprocess.
                int enrolled = matched &&
                    synveil_enroll_password(first_password, first_length) == 0;
                auth_clear(&state);
                synveil_enroll_wipe(first_password, sizeof(first_password));
                first_length = 0u;
                if (enrolled) {
                    state.enroll_stage = 0u;
                    state.denied = 0;
                    auth_render(screen, &state);
                    puts("\nSYNVEIL_ENROLL_COMPLETED");
                    puts("SYNVEIL_LOGIN_READY");
                } else {
                    state.enroll_stage = synveil_enroll_can_start() ? 1u : 0u;
                    auth_note_denied(&state);
                    auth_render(screen, &state);
                    puts("\nSYNVEIL_ENROLL_FAILED");
                }
                fflush(stdout);
                continue;
            }
            // Drop EVIOCGRAB before switching to the authenticated shell.
            close(keyboard);
            keyboard = -1;
            // Release the login VT's graphics mode so the kernel permits
            // the session's switch to tty1; it is restored on relock.
            if (auth_handoff_login_vt() != 0) {
                auth_clear(&state);
                auth_note_denied(&state);
            } else if (auth_attempt(&state)) {
                state.denied = 0;
                state.denied_at_ms = 0;
            } else {
                auth_note_denied(&state);
            }
            // Authentication can return "denied" even if the seat accepted
            // the password but the response was interrupted. In that race
            // tty1 may have activated. Always restore tty2 before exposing
            // a login surface or reopening the exclusive keyboard.
            if (auth_restore_login_vt() != 0) break;
            // A denial is *not* safe evidence of input readiness until tty2
            // has been restored and EVIOCGRAB has been reacquired. Test QMP
            // clients may submit the next password as soon as this marker
            // appears; emitting it early silently drops their first keys.
            keyboard = auth_open_private_keyboard();
            if (keyboard < 0) {
                auth_keyboard_disconnected(&state);
                puts("\nSYNVEIL_LOGIN_INPUT_UNAVAILABLE");
                fflush(stdout);
            }
            auth_render(screen, &state);
            if (keyboard >= 0 && state.denied) {
                // The keyboard is grabbed and the denied UI fully painted.
                puts("\nSYNVEIL_GRAPHICAL_AUTH_DENIED");
                fflush(stdout);
            } else if (keyboard >= 0) {
                // Evidence only once VT2 is visible, painted and securely
                // receiving keystrokes; never report a premature relock.
                puts("\nSYNVEIL_LOGIN_RELOCKED");
                fflush(stdout);
            }
        } else {
            auth_input_key(&state, event.code, event.value);
            auth_render(screen, &state);
        }
    }
    auth_clear(&state);
    synveil_enroll_wipe(first_password, sizeof(first_password));
    if (keyboard >= 0) close(keyboard);
    return 1;
}

static int self_test(void) {
    // Arrow-only controllers must never be mistaken for a login keyboard.
    unsigned char keys[(KEY_MAX + 8u) / 8u] = {0};
    const unsigned login_keys[] = {
        KEY_A, KEY_Z, KEY_0, KEY_1, KEY_BACKSPACE, KEY_SPACE, KEY_LEFTSHIFT
    };
    if (login_keyboard_capable(keys, sizeof(keys))) return 1;
    for (unsigned i = 0; i < sizeof(login_keys)/sizeof(login_keys[0]); ++i)
        keys[login_keys[i] / 8u] |= (unsigned char)(1u << (login_keys[i] % 8u));
    if (!login_keyboard_capable(keys, sizeof(keys))) return 1;
    keys[KEY_BACKSPACE / 8u] &= (unsigned char)~(1u << (KEY_BACKSPACE % 8u));
    if (login_keyboard_capable(keys, sizeof(keys))) return 1;
    struct surface screen;
    memset(&screen, 0, sizeof(screen));
    screen.variable.bits_per_pixel = 32;
    screen.variable.xres = 640;
    screen.variable.yres = 480;
    screen.variable.red.offset = 16;
    screen.variable.red.length = 8;
    screen.variable.green.offset = 8;
    screen.variable.green.length = 8;
    screen.variable.blue.offset = 0;
    screen.variable.blue.length = 8;
    screen.fixed.visual = FB_VISUAL_TRUECOLOR;
    screen.fixed.line_length = 640 * 4;
    screen.fixed.smem_len = 640 * 480 * 4;
    if (!valid_layout(&screen) || rgb(&screen, 255, 0, 0) != 0x00ff0000u) return 1;
    screen.fixed.smem_len--;
    if (valid_layout(&screen)) return 1;
    struct menu_state state = {.selected = 0u, .page = -1, .quit = 0};
    menu_key(&state, KEY_RIGHT);
    if (state.selected != 1u) return 1;
    menu_key(&state, KEY_ENTER);
    if (state.page != 1) return 1;
    menu_key(&state, KEY_ESC);
    if (state.page != -1 || state.quit) return 1;
    menu_key(&state, KEY_LEFT);
    if (state.selected != 0u) return 1;
    menu_key(&state, KEY_ESC);
    if (!state.quit) return 1;
    struct menu_state click_state = {.selected = 0u, .page = -1, .quit = 0};
    menu_click(&click_state, 60u, 170u, 900u, 600u);
    if (click_state.page != 1 || click_state.selected != 1u) return 1;
    menu_click(&click_state, 240u, 36u, 900u, 600u);
    if (click_state.page != -1) return 1;
    struct menu_state demo = {.selected = 3u, .page = -1, .quit = 0};
    menu_key(&demo, KEY_ENTER);
    if (demo.page != 3 || demo.launch) return 1;
    menu_key(&demo, KEY_ENTER);
    if (!demo.launch) return 1;
    demo.launch = 0;
    menu_click(&demo, 300u, 200u, 900u, 600u);
    if (!demo.launch) return 1;
    struct menu_state settings = {.selected = 4u, .page = -1, .quit = 0};
    menu_key(&settings, KEY_ENTER);
    if (settings.page != 4 || settings.high_contrast || settings.cursor_scale) return 1;
    menu_key(&settings, KEY_RIGHT);
    menu_key(&settings, KEY_UP);
    if (!settings.high_contrast || settings.cursor_scale != 1u) return 1;
    menu_click(&settings, 300u, 150u, 900u, 600u);
    menu_click(&settings, 300u, 240u, 900u, 600u);
    if (settings.high_contrast || settings.cursor_scale) return 1;
    // An incomplete seat reply must not hold the login screen indefinitely.
    // The successful path accepts exactly the broker's seven-byte ACTIVE reply.
    int pair[2];
    unsigned char seat_reply[7] = {0};
    if (socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, pair) != 0) return 1;
    if (send(pair[1], "ACTIVE\n", 7u, MSG_NOSIGNAL) != 7 ||
        auth_receive_response(pair[0], seat_reply, sizeof(seat_reply), 100) != 0 ||
        memcmp(seat_reply, "ACTIVE\n", sizeof(seat_reply)) != 0) return 1;
    close(pair[0]);
    close(pair[1]);
    if (socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, pair) != 0) return 1;
    if (send(pair[1], "ACT", 3u, MSG_NOSIGNAL) != 3 ||
        auth_receive_response(pair[0], seat_reply, sizeof(seat_reply), 40) == 0)
        return 1;
    close(pair[0]);
    close(pair[1]);
    // The VT restore loop must return to supervision at its fixed deadline,
    // including the nanosecond boundary rather than an extra whole second.
    struct timespec before = {.tv_sec = 100, .tv_nsec = 500000000};
    struct timespec early = {.tv_sec = 102, .tv_nsec = 499999999};
    struct timespec deadline = {.tv_sec = 102, .tv_nsec = 500000000};
    struct timespec late = {.tv_sec = 103, .tv_nsec = 0};
    if (auth_vt_restore_expired(&before, &early) ||
        !auth_vt_restore_expired(&before, &deadline) ||
        !auth_vt_restore_expired(&before, &late)) return 1;
    struct menu_state user = {.selected = 0u, .page = -1, .authenticated = 1};
    menu_key(&user, KEY_ESC);
    if (!user.quit) return 1;
    if (session_input_code('h') != KEY_LEFT ||
        session_input_code('l') != KEY_RIGHT ||
        session_input_code('a') != KEY_A ||
        session_input_code('\r') != KEY_ENTER ||
        session_input_code(27u) != KEY_ESC ||
        session_input_code('x') != 0u) return 1;
    struct auth_input auth = {0};
    auth_input_key(&auth, KEY_A, 1);
    auth_input_key(&auth, KEY_1, 1);
    auth_input_key(&auth, KEY_MINUS, 1);
    if (auth.length != 3u || auth.password[0] != 'a' ||
        auth.password[1] != '1' || auth.password[2] != '-') return 1;
    auth_input_key(&auth, KEY_BACKSPACE, 1);
    auth_input_key(&auth, KEY_LEFTSHIFT, 1);
    auth_input_key(&auth, KEY_B, 1);
    auth_input_key(&auth, KEY_LEFTSHIFT, 0);
    if (auth.length != 3u || auth.password[2] != 'B') return 1;
    auth_clear(&auth);
    if (auth.length != 0u || auth.password[0] != 0u || auth.password[2] != 0u) return 1;
    // Independent shift keys, Caps Lock XOR shift, and symbols must map
    // consistently before we send any password bytes over the seat IPC.
    auth_input_key(&auth, KEY_LEFTSHIFT, 1);
    auth_input_key(&auth, KEY_RIGHTSHIFT, 1);
    auth_input_key(&auth, KEY_LEFTSHIFT, 0);
    auth_input_key(&auth, KEY_A, 1);
    if (auth.password[0] != 'A') return 1;
    auth_input_key(&auth, KEY_RIGHTSHIFT, 0);
    auth_input_key(&auth, KEY_CAPSLOCK, 1);
    auth_input_key(&auth, KEY_A, 1);
    auth_input_key(&auth, KEY_RIGHTSHIFT, 1);
    auth_input_key(&auth, KEY_A, 1);
    auth_input_key(&auth, KEY_LEFTBRACE, 1);
    if (auth.length != 4u || auth.password[1] != 'A' ||
        auth.password[2] != 'a' || auth.password[3] != '{') return 1;
    auth_input_key(&auth, KEY_RIGHTSHIFT, 0);
    auth_input_key(&auth, KEY_BACKSLASH, 1);
    auth_input_key(&auth, KEY_KP7, 1);
    if (auth.password[4] != 92u || auth.password[5] != '7') return 1;
    auth_clear(&auth);
    if (auth.length || auth.shift || auth.password[0] || auth.password[5]) return 1;
    // A hot-unplug discards all secret bytes and volatile modifier state.
    auth_input_key(&auth, KEY_LEFTSHIFT, 1);
    auth_input_key(&auth, KEY_Q, 1);
    auth.denied = 1;
    auth_keyboard_disconnected(&auth);
    if (!auth.keyboard_missing || auth.length || auth.shift ||
        auth.caps_lock || auth.denied || auth.password[0]) return 1;
    auth_keyboard_connected(&auth);
    if (auth.keyboard_missing || auth.length || auth.shift ||
        auth.caps_lock || auth.denied || auth.password[0]) return 1;
    // The UI must accept the complete verifier policy limit, reject all
    // further characters, then wipe the entire 1024-byte secret buffer.
    for (unsigned i = 0; i < AUTH_MAX_UI_PASSWORD + 4u; i++)
        auth_input_key(&auth, KEY_M, 1);
    if (auth.length != AUTH_MAX_UI_PASSWORD) return 1;
    if ((auth.length >> 8u) != 4u || (auth.length & 0xffu) != 0u)
        return 1;
    auth_clear(&auth);
    if (auth.length || auth.password[0] ||
        auth.password[AUTH_MAX_UI_PASSWORD - 1u]) return 1;
    if (glyph_for('4') == NULL || glyph_for('.') == NULL ||
        glyph_for('N') == NULL || glyph_for('@') != NULL) return 1;
    // The embedded UI atlas must decode to exactly width*height coverage
    // bytes per glyph and fit the renderer's static bitmap buffer.
    for (unsigned i = 0; i < sizeof(ui_fonts) / sizeof(ui_fonts[0]); i++) {
        static unsigned char decoded[64 * 64];
        for (unsigned c = 0; c < 95u; c++) {
            const struct ui_glyph *glyph = &ui_fonts[i].glyphs[c];
            if (glyph->width > 64u || glyph->height > 64u) return 1;
            if (ui_glyph_decode(&ui_fonts[i], glyph, decoded) !=
                (unsigned)glyph->width * glyph->height) return 1;
        }
    }
    if (ui_text_width(20, 0, "SYNVEIL") == 0u ||
        ui_text_width(14, 1, "STATUS") == 0u) return 1;
    if (ui_ease_out(0u) != 0u || ui_ease_out(1000u) != 1000u ||
        ui_ease_out(500u) <= 500u) return 1;
    if (absolute_pixel(-20, 0, 100, 900u) != 0u ||
        absolute_pixel(200, 0, 100, 900u) != 899u ||
        absolute_pixel(50, 0, 100, 900u) != 449u) return 1;
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--self-test") == 0) return self_test();
    if (argc != 2 || (strcmp(argv[1], "--probe") != 0 &&
                      strcmp(argv[1], "--demo") != 0 &&
                      strcmp(argv[1], "--menu") != 0 &&
                      strcmp(argv[1], "--login") != 0 &&
                      strcmp(argv[1], "--session") != 0)) {
        fputs("usage: synveil-display --probe|--demo|--menu|--login|--session|--self-test\n", stderr);
        return 2;
    }
    const int user_session = strcmp(argv[1], "--session") == 0;
    // Unprivileged desktop uses only the inherited framebuffer lease.
    // A direct --session invocation with no valid FD cannot open fbdev.
    if (user_session && (geteuid() != 1000 || getuid() != 1000))
        return 1;
    int fd = user_session ? fcntl(3, F_DUPFD_CLOEXEC, 8) :
                            open("/dev/fb0", O_RDWR | O_CLOEXEC);
    if (user_session) close(3); // only the CLOEXEC copy may reach shell fork
    struct stat session_device;
    if (user_session && (fd < 0 || fstat(fd, &session_device) != 0 ||
                         !S_ISCHR(session_device.st_mode))) {
        if (fd >= 0) close(fd);
        return 1;
    }
    if (fd < 0) {
        fprintf(stderr, "[synveil-display] /dev/fb0 unavailable: %s\n", strerror(errno));
        return 1;
    }
    struct surface screen;
    memset(&screen, 0, sizeof(screen));
    if (ioctl(fd, FBIOGET_FSCREENINFO, &screen.fixed) == -1 ||
        ioctl(fd, FBIOGET_VSCREENINFO, &screen.variable) == -1 ||
        !valid_layout(&screen)) {
        fputs("[synveil-display] unsupported framebuffer layout\n", stderr);
        close(fd);
        return 1;
    }
    screen.length = screen.fixed.smem_len;
    screen.mapped = mmap(NULL, screen.length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (screen.mapped == MAP_FAILED) {
        fprintf(stderr, "[synveil-display] mmap failed: %s\n", strerror(errno));
        return 1;
    }
    // A child process can inherit mmap() even when the fd was CLOEXEC or
    // explicitly closed. The authenticated user terminal must never see a
    // framebuffer mapping, including if exec of the shell fails or races
    // with the seat being revoked. Refuse to start if the kernel cannot
    // enforce MADV_DONTFORK for this framebuffer.
    if ((user_session || strcmp(argv[1], "--login") == 0) &&
        synveil_exclude_mapping_from_children(screen.mapped, screen.length) != 0) {
        fputs("[synveil-display] cannot isolate framebuffer from child processes\n", stderr);
        munmap(screen.mapped, screen.length);
        return 1;
    }
    int result = 0;
    if (strcmp(argv[1], "--demo") == 0) paint(&screen);
    else if (strcmp(argv[1], "--menu") == 0) result = run_menu(&screen);
    else if (strcmp(argv[1], "--login") == 0) result = run_auth_login(&screen);
    else if (user_session) result = run_user_session(&screen);
    else rectangle(&screen, 0, 0, 1, 1, rgb(&screen, 13, 20, 36));
    munmap(screen.mapped, screen.length);
    if (result == 0) puts("SYNVEIL_DISPLAY_READY");
    return result;
}
