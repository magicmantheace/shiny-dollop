// SPDX-License-Identifier: MPL-2.0
// Original xdg_toplevel client. Host protocol proof is not native boot proof.
#define _GNU_SOURCE
#include <linux/input-event-codes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <wayland-client.h>
#include "xdg-shell-client.h"

enum { W = 400, H = 240, MAX_W = 4096, MAX_H = 2160, MAX_BUFFERS = 3 };
struct app;
struct buffer {
    struct app *app;
    struct buffer *next;
    struct wl_buffer *object;
    void *pixels;
    size_t size;
};
struct app {
    struct wl_display *display;
    struct wl_registry *registry;
    struct wl_compositor *compositor;
    struct wl_shm *shm;
    struct wl_seat *seat;
    struct wl_pointer *pointer;
    struct wl_keyboard *keyboard;
    struct xdg_wm_base *wm;
    struct wl_surface *surface;
    struct xdg_surface *xdg;
    struct xdg_toplevel *top;
    struct buffer *buffers;
    unsigned buffer_count;
    int width, height, pending_w, pending_h, floating_w, floating_h;
    int pointer_x, pointer_y;
    int configured, closed, failed, redraw, interactive, exercise;
    int maximized, exercise_stage;
    /* ADR 0024 first-show fade-in, paced by frame callbacks. */
    long long show_ms;
    struct wl_callback *frame_cb;
};

static int render(struct app *a);

/* ADR 0024 chrome helpers (duplicated per client; the clients are
 * standalone translation units by design). This client has no font
 * by design: its title bar carries glyphs only. */
static long long now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static unsigned ease_out_q(long long elapsed, long long total) {
    if (elapsed <= 0) return 0;
    if (elapsed >= total) return 255;
    unsigned p = (unsigned)(elapsed * 255 / total);
    unsigned q = 255 - p;
    return 255 - (q * q * q) / (255 * 255);
}

static void plot(struct app *a, uint32_t *px, int x, int y, uint32_t color) {
    if (x < 0 || y < 0 || x >= a->width || y >= a->height) return;
    px[(size_t)y * (size_t)a->width + (size_t)x] = color;
}

static void draw_app_glyph(struct app *a, uint32_t *px) {
    for (int y = 0; y < 16; y++)
        for (int x = 0; x < 16; x++) {
            int dx = x < 3 ? 3 - x : (x > 12 ? x - 12 : 0);
            int dy = y < 3 ? 3 - y : (y > 12 ? y - 12 : 0);
            if (dx * dx + dy * dy > 9) continue;
            plot(a, px, 10 + x, 8 + y, 0xff4cc2ffu);
        }
}

static void draw_close_glyph(struct app *a, uint32_t *px, int cx, int cy,
                             uint32_t color) {
    for (int d = -5; d <= 5; d++) {
        plot(a, px, cx + d, cy + d, color);
        plot(a, px, cx + d + 1, cy + d, color);
        plot(a, px, cx + d, cy - d, color);
        plot(a, px, cx + d + 1, cy - d, color);
    }
}

static void draw_max_glyph(struct app *a, uint32_t *px, int cx, int cy,
                           uint32_t color, int maximized) {
    int x0 = cx - 5, y0 = cy - 5;
    if (maximized) { x0 += 2; y0 -= 2; }
    for (int i = 0; i < 10; i++) {
        plot(a, px, x0 + i, y0, color);
        plot(a, px, x0 + i, y0 + 1, color);
        plot(a, px, x0 + i, y0 + 9, color);
        plot(a, px, x0, y0 + i, color);
        plot(a, px, x0 + 1, y0 + i, color);
        plot(a, px, x0 + 9, y0 + i, color);
    }
    if (maximized) {
        int bx = cx - 7, by = cy - 3;
        for (int i = 0; i < 10; i++) {
            if (i > 2) {
                plot(a, px, bx + i, by, color);
                plot(a, px, bx + i, by + 1, color);
            }
            plot(a, px, bx + 9, by + i, color);
            if (i > 2) plot(a, px, bx + i, by + 9, color);
        }
    }
}

static void finish_frame(struct app *a, uint32_t *px) {
    const int w = a->width, h = a->height, r = 8;
    const uint32_t stroke = 0xff454545u;
    for (int y = 0; y <= r; y++)
        for (int x = 0; x <= r; x++) {
            int dx = r - x, dy = r - y;
            int d2 = dx * dx + dy * dy;
            size_t corners[4] = {
                (size_t)y * (size_t)w + (size_t)x,
                (size_t)y * (size_t)w + (size_t)(w - 1 - x),
                (size_t)(h - 1 - y) * (size_t)w + (size_t)x,
                (size_t)(h - 1 - y) * (size_t)w + (size_t)(w - 1 - x)};
            for (int i = 0; i < 4; i++) {
                if (d2 > (r + 1) * (r + 1)) px[corners[i]] = 0;
                else if (d2 > (r - 1) * (r - 1)) px[corners[i]] = stroke;
            }
        }
    for (int x = r + 1; x < w - 1 - r; x++) {
        px[x] = stroke;
        px[(size_t)(h - 1) * (size_t)w + (size_t)x] = stroke;
    }
    for (int y = r + 1; y < h - 1 - r; y++) {
        px[(size_t)y * (size_t)w] = stroke;
        px[(size_t)y * (size_t)w + (size_t)(w - 1)] = stroke;
    }
}

static void frame_done(void *ctx, struct wl_callback *cb, uint32_t time_ms) {
    (void)time_ms;
    struct app *a = ctx;
    if (cb == a->frame_cb) a->frame_cb = NULL;
    wl_callback_destroy(cb);
    if (a->show_ms && ease_out_q(now_ms() - a->show_ms, 200) < 255) {
        a->redraw = 1;
        if (render(a) < 0) a->failed = 1;
    }
}
static const struct wl_callback_listener frame_handlers = {
    .done = frame_done
};
static void discard_buffer(struct buffer *b) {
    struct app *a = b->app;
    struct buffer **link = &a->buffers;
    while (*link && *link != b) link = &(*link)->next;
    if (*link) { *link = b->next; a->buffer_count--; }
    wl_buffer_destroy(b->object);
    munmap(b->pixels, b->size);
    free(b);
}
static void released(void *ctx, struct wl_buffer *object) {
    (void)object;
    struct buffer *b = ctx;
    struct app *a = b->app;
    discard_buffer(b);
    if (a->redraw && render(a) < 0) a->failed = 1;
}
static const struct wl_buffer_listener buffer_handlers = { .release = released };

static void pointer_enter(void *ctx, struct wl_pointer *pointer, uint32_t serial,
                          struct wl_surface *surface, wl_fixed_t x, wl_fixed_t y) {
    (void)pointer; (void)serial; (void)surface;
    struct app *a = ctx;
    a->pointer_x = wl_fixed_to_int(x); a->pointer_y = wl_fixed_to_int(y);
}
static void pointer_leave(void *ctx, struct wl_pointer *pointer, uint32_t serial,
                          struct wl_surface *surface) {
    (void)ctx; (void)pointer; (void)serial; (void)surface;
}
static void pointer_motion(void *ctx, struct wl_pointer *pointer, uint32_t time,
                           wl_fixed_t x, wl_fixed_t y) {
    (void)pointer; (void)time;
    struct app *a = ctx;
    a->pointer_x = wl_fixed_to_int(x); a->pointer_y = wl_fixed_to_int(y);
}
static void pointer_button(void *ctx, struct wl_pointer *pointer, uint32_t serial,
                           uint32_t time, uint32_t button, uint32_t state) {
    (void)pointer; (void)time;
    struct app *a = ctx;
    if (!a->interactive || !a->configured || button != BTN_LEFT ||
        state != WL_POINTER_BUTTON_STATE_PRESSED) return;
    if (a->pointer_y < 32) {
        if (a->pointer_x >= a->width - 46) a->closed = 1;
        else if (a->pointer_x >= a->width - 92) {
            if (a->maximized) xdg_toplevel_unset_maximized(a->top);
            else xdg_toplevel_set_maximized(a->top);
        }
        else xdg_toplevel_move(a->top, a->seat, serial);
    } else if (a->pointer_x >= a->width - 20 && a->pointer_y >= a->height - 20) {
        xdg_toplevel_resize(a->top, a->seat, serial,
                            XDG_TOPLEVEL_RESIZE_EDGE_BOTTOM_RIGHT);
    }
}
static void pointer_axis(void *ctx, struct wl_pointer *pointer, uint32_t time,
                         uint32_t axis, wl_fixed_t value) {
    (void)ctx; (void)pointer; (void)time; (void)axis; (void)value;
}
static const struct wl_pointer_listener pointer_handlers = {
    .enter = pointer_enter, .leave = pointer_leave, .motion = pointer_motion,
    .button = pointer_button, .axis = pointer_axis
};
static void keyboard_keymap(void *ctx, struct wl_keyboard *keyboard,
                            uint32_t format, int fd, uint32_t size) {
    (void)ctx; (void)keyboard; (void)format; (void)size;
    // Only the layout-independent Escape control is used. Do not map or log
    // keymap data; future text applications use source-built xkbcommon.
    if (fd >= 0) close(fd);
}
static void keyboard_enter(void *ctx, struct wl_keyboard *keyboard, uint32_t serial,
                           struct wl_surface *surface, struct wl_array *keys) {
    (void)ctx; (void)keyboard; (void)serial; (void)surface; (void)keys;
}
static void keyboard_leave(void *ctx, struct wl_keyboard *keyboard, uint32_t serial,
                           struct wl_surface *surface) {
    (void)ctx; (void)keyboard; (void)serial; (void)surface;
}
static void keyboard_key(void *ctx, struct wl_keyboard *keyboard, uint32_t serial,
                         uint32_t time, uint32_t key, uint32_t state) {
    (void)keyboard; (void)serial; (void)time;
    struct app *a = ctx;
    if (a->interactive && key == KEY_ESC && state == WL_KEYBOARD_KEY_STATE_PRESSED)
        a->closed = 1;
}
static void keyboard_modifiers(void *ctx, struct wl_keyboard *keyboard, uint32_t serial,
                               uint32_t depressed, uint32_t latched, uint32_t locked,
                               uint32_t group) {
    (void)ctx; (void)keyboard; (void)serial; (void)depressed;
    (void)latched; (void)locked; (void)group;
}
static const struct wl_keyboard_listener keyboard_handlers = {
    .keymap = keyboard_keymap, .enter = keyboard_enter, .leave = keyboard_leave,
    .key = keyboard_key, .modifiers = keyboard_modifiers
};
static void capabilities(void *ctx, struct wl_seat *seat, uint32_t caps) {
    struct app *a = ctx;
    if ((caps & WL_SEAT_CAPABILITY_KEYBOARD) && !a->keyboard) {
        a->keyboard = wl_seat_get_keyboard(seat);
        wl_keyboard_add_listener(a->keyboard, &keyboard_handlers, a);
    } else if (!(caps & WL_SEAT_CAPABILITY_KEYBOARD) && a->keyboard) {
        wl_keyboard_destroy(a->keyboard); a->keyboard = NULL;
    }
    if ((caps & WL_SEAT_CAPABILITY_POINTER) && !a->pointer) {
        a->pointer = wl_seat_get_pointer(seat);
        wl_pointer_add_listener(a->pointer, &pointer_handlers, a);
    } else if (!(caps & WL_SEAT_CAPABILITY_POINTER) && a->pointer) {
        wl_pointer_destroy(a->pointer); a->pointer = NULL;
    }
}
static const struct wl_seat_listener seat_handlers = { .capabilities = capabilities };
static void global(void *ctx, struct wl_registry *registry,
                   uint32_t name, const char *interface, uint32_t version) {
    struct app *a = ctx;
    if (!strcmp(interface, wl_compositor_interface.name))
        a->compositor = wl_registry_bind(registry, name, &wl_compositor_interface,
                                          version < 4 ? version : 4);
    else if (!strcmp(interface, wl_shm_interface.name))
        a->shm = wl_registry_bind(registry, name, &wl_shm_interface, 1);
    else if (!strcmp(interface, xdg_wm_base_interface.name))
        a->wm = wl_registry_bind(registry, name, &xdg_wm_base_interface,
                                  version < 3 ? version : 3);
    else if (!strcmp(interface, wl_seat_interface.name) && !a->seat) {
        a->seat = wl_registry_bind(registry, name, &wl_seat_interface, 1);
        wl_seat_add_listener(a->seat, &seat_handlers, a);
    }
}
static void global_removed(void *ctx, struct wl_registry *registry, uint32_t name) {
    (void)ctx; (void)registry; (void)name;
}
static const struct wl_registry_listener registry_handlers = {
    .global = global, .global_remove = global_removed
};
static void ping(void *ctx, struct xdg_wm_base *wm, uint32_t serial) {
    (void)ctx; xdg_wm_base_pong(wm, serial);
}
static const struct xdg_wm_base_listener wm_handlers = { .ping = ping };
static void configure_top(void *ctx, struct xdg_toplevel *top, int32_t w,
                          int32_t h, struct wl_array *states) {
    (void)top;
    struct app *a = ctx;
    a->maximized = 0;
    uint32_t *state;
    wl_array_for_each(state, states)
        if (*state == XDG_TOPLEVEL_STATE_MAXIMIZED) a->maximized = 1;
    if (w < 0 || h < 0 || w > MAX_W || h > MAX_H) { a->failed = 1; return; }
    /* A zero dimension means the compositor leaves the size to the
     * client. Weston sends exactly that when an interactive resize
     * grab ends (desktop-shell resize_grab_button set_size(0, 0)) and
     * when a maximized window is restored. Both cases want the last
     * FLOATING (non-maximized) size: after a resize that is the size
     * the user just dragged to, and after a maximize it is the
     * pre-maximize size. Keeping the current size instead would
     * leave a restored window at its maximized dimensions; snapping
     * to the initial constants would revert every resize. Before any
     * floating size exists, fall back to the current size, then the
     * initial constants. */
    a->pending_w = w ? w : (!a->maximized && a->floating_w ? a->floating_w :
                            (a->width ? a->width : W));
    a->pending_h = h ? h : (!a->maximized && a->floating_h ? a->floating_h :
                            (a->height ? a->height : H));
}
static void close_top(void *ctx, struct xdg_toplevel *top) {
    (void)top; ((struct app *)ctx)->closed = 1;
}
static const struct xdg_toplevel_listener top_handlers = {
    .configure = configure_top, .close = close_top
};
static void configure_surface(void *ctx, struct xdg_surface *xdg, uint32_t serial) {
    struct app *a = ctx;
    xdg_surface_ack_configure(xdg, serial);
    if (a->failed) return;
    a->width = a->pending_w; a->height = a->pending_h;
    /* The floating size is the last size actually committed while not
     * maximized (including a client-chosen size after a (0,0) initial
     * configure); configure_top's zero handling restores exactly it. */
    if (!a->maximized) { a->floating_w = a->width; a->floating_h = a->height; }
    a->redraw = 1;
    if (render(a) < 0) a->failed = 1;
}
static const struct xdg_surface_listener surface_handlers = {
    .configure = configure_surface
};

static int render(struct app *a) {
    // A busy buffer belongs to the compositor until wl_buffer.release. Bound
    // outstanding allocations and redraw the latest configure once one returns.
    if (a->buffer_count == MAX_BUFFERS) return 0;
    const size_t size = (size_t)a->width * (size_t)a->height * 4;
    int fd = memfd_create("synveil-first-window", MFD_CLOEXEC);
    if (fd < 0) return -1;
    if (ftruncate(fd, (off_t)size) < 0) { close(fd); return -1; }
    void *data = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (data == MAP_FAILED) { close(fd); return -1; }
    struct buffer *b = calloc(1, sizeof(*b));
    if (!b) { munmap(data, size); close(fd); return -1; }
    uint32_t *px = data;
    if (!a->show_ms) a->show_ms = now_ms();
    /* Body identity: the spec desktop gradient, vertical, over the
     * body below the 32 px shell title bar (ADR 0024). */
    int span = a->height - 32;
    if (span < 1) span = 1;
    for (int y = 0; y < a->height; y++)
        for (int x = 0; x < a->width; x++) {
            uint32_t color;
            if (y < 32) {
                color = 0xff202020u;
            } else {
                int t = y - 32;
                color = 0xff000000u |
                    ((uint32_t)(15 + 12 * t / span) << 16) |
                    ((uint32_t)(43 + 32 * t / span) << 8) |
                    (uint32_t)(91 + 52 * t / span);
            }
            if (x >= a->width - 20 && y >= a->height - 20)
                color = 0xff383838u;
            px[(size_t)y * (size_t)a->width + (size_t)x] = color;
        }
    draw_app_glyph(a, px);
    draw_max_glyph(a, px, a->width - 69, 16, 0xffffffffu, a->maximized);
    draw_close_glyph(a, px, a->width - 23, 16, 0xffffffffu);
    finish_frame(a, px);
    unsigned fade = ease_out_q(now_ms() - a->show_ms, 200);
    if (fade < 255) {
        size_t count = (size_t)a->width * (size_t)a->height;
        for (size_t i = 0; i < count; i++) {
            uint32_t c = px[i];
            uint32_t out = 0;
            for (int ch = 0; ch < 4; ch++) {
                unsigned v = (c >> (ch * 8)) & 0xff;
                out |= (uint32_t)(v * fade / 255) << (ch * 8);
            }
            px[i] = out;
        }
    }
    struct wl_shm_pool *pool = wl_shm_create_pool(a->shm, fd, (int)size);
    close(fd);
    if (!pool) { munmap(data, size); free(b); return -1; }
    b->object = wl_shm_pool_create_buffer(pool, 0, a->width, a->height,
                                          a->width * 4, WL_SHM_FORMAT_ARGB8888);
    wl_shm_pool_destroy(pool);
    if (!b->object) { munmap(data, size); free(b); return -1; }
    b->app = a; b->pixels = data; b->size = size;
    b->next = a->buffers; a->buffers = b; a->buffer_count++;
    wl_buffer_add_listener(b->object, &buffer_handlers, b);
    wl_surface_attach(a->surface, b->object, 0, 0);
    wl_surface_damage(a->surface, 0, 0, a->width, a->height);
    wl_surface_commit(a->surface);
    if (fade < 255 && !a->frame_cb) {
        a->frame_cb = wl_surface_frame(a->surface);
        wl_callback_add_listener(a->frame_cb, &frame_handlers, a);
    }
    a->redraw = 0; a->configured++;
    printf("SYNVEIL_XDG_SHM_SIZE %d %d\n", a->width, a->height);
    if (a->configured == 1) puts("SYNVEIL_XDG_TOPLEVEL_SHM_SUBMITTED");
    if (a->exercise && a->exercise_stage == 0) {
        a->exercise_stage = 1;
        xdg_toplevel_set_maximized(a->top);
        wl_surface_commit(a->surface);
    } else if (a->exercise && a->exercise_stage == 1 && a->maximized) {
        a->exercise_stage = 2;
        xdg_toplevel_unset_maximized(a->top);
        wl_surface_commit(a->surface);
    } else if (a->exercise && a->exercise_stage == 2 && !a->maximized) {
        a->exercise_stage = 3;
    }
    fflush(stdout);
    return 0;
}

static void cleanup(struct app *a) {
    if (a->keyboard) wl_keyboard_destroy(a->keyboard);
    if (a->pointer) wl_pointer_destroy(a->pointer);
    if (a->seat) wl_seat_destroy(a->seat);
    if (a->top) xdg_toplevel_destroy(a->top);
    if (a->xdg) xdg_surface_destroy(a->xdg);
    if (a->surface) wl_surface_destroy(a->surface);
    while (a->buffers) discard_buffer(a->buffers);
    if (a->wm) xdg_wm_base_destroy(a->wm);
    if (a->shm) wl_shm_destroy(a->shm);
    if (a->compositor) wl_compositor_destroy(a->compositor);
    if (a->registry) wl_registry_destroy(a->registry);
    if (a->display) wl_display_disconnect(a->display);
}

int main(int argc, char **argv) {
    struct app a = { .pending_w = W, .pending_h = H };
    int success = 0;
    if (argc == 2 && !strcmp(argv[1], "--interactive")) a.interactive = 1;
    else if (argc == 2 && !strcmp(argv[1], "--exercise-resize")) a.exercise = 1;
    else if (argc != 1) { fputs("unknown window mode\n", stderr); return 1; }
    if (geteuid() == 0) { fputs("refusing root window client\n", stderr); return 1; }
    a.display = wl_display_connect(NULL);
    if (!a.display) goto out;
    a.registry = wl_display_get_registry(a.display);
    if (!a.registry) goto out;
    wl_registry_add_listener(a.registry, &registry_handlers, &a);
    if (wl_display_roundtrip(a.display) < 0 ||
        !a.compositor || !a.shm || !a.wm) goto out;
    xdg_wm_base_add_listener(a.wm, &wm_handlers, &a);
    a.surface = wl_compositor_create_surface(a.compositor);
    if (!a.surface) goto out;
    a.xdg = xdg_wm_base_get_xdg_surface(a.wm, a.surface);
    if (!a.xdg) goto out;
    xdg_surface_add_listener(a.xdg, &surface_handlers, &a);
    a.top = xdg_surface_get_toplevel(a.xdg);
    if (!a.top) goto out;
    xdg_toplevel_add_listener(a.top, &top_handlers, &a);
    xdg_toplevel_set_title(a.top, "Synveil First Wayland Window");
    xdg_toplevel_set_app_id(a.top, "org.synveil.first-window");
    xdg_toplevel_set_min_size(a.top, 160, 100);
    xdg_toplevel_set_max_size(a.top, MAX_W, MAX_H);
    wl_surface_commit(a.surface);
    while (!a.closed && !a.failed) {
        if (wl_display_dispatch(a.display) < 0) goto out;
        if (!a.interactive && (a.exercise ? a.exercise_stage == 3 : a.configured > 0)) break;
    }
    if (a.failed || !a.configured || (!a.interactive && a.closed) ||
        wl_display_flush(a.display) < 0) goto out;
    if (a.exercise) puts("SYNVEIL_XDG_RESIZE_CYCLE_COMPLETE");
    fflush(stdout);
    if (!a.interactive) usleep(750000);
    success = 1;
out:
    cleanup(&a);
    return success ? 0 : 1;
}
