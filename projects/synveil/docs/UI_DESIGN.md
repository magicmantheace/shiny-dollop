# Synveil UI design spec — Windows 11 design language

Adopted by [ADR 0024](adr/0024-windows-11-ui-design-language.md)
(2026-11-05). This spec is the presentation contract for
`src/veil-display/`, the Synveil desktop clients in
`src/desktop-wayland/`, and the presentation keys of
`build/rootfs/weston.ini`. Behaviour, authentication, and update
contracts are out of scope and unchanged. All artwork is original;
no Microsoft assets are used.

## Design tokens

### Palette (dark shell, matching the current desktop)

| Token | Value | Use |
| --- | --- | --- |
| `ink` | `#FFFFFF` | Primary text on dark |
| `ink-dim` | `#C8C8C8` | Secondary text on dark (precomputed blend) |
| `ink-faint` | `#8A8A8A` | Tertiary text, glyph hints |
| `shell` | `#202020` | Panel/taskbar background |
| `surface` | `#2C2C2C` | Cards, menus, window bodies |
| `surface-hi` | `#383838` | Hover/raised surface |
| `stroke` | `#454545` | 1 px card/window borders on dark |
| `accent` | `#4CC2FF` | Accent (selection, focus ring, links) |
| `accent-pressed` | `#38A8E8` | Accent while pressed |
| `danger` | `#E81123` | Close-button hover (Windows convention) |
| `danger-ink` | `#FFFFFF` | Glyph on `danger` |
| `field` | `#2C2C2C` | Text fields on dark, 1 px `stroke` border |
| `desktop-near` | `#0F2B5B` | Desktop background gradient, top |
| `desktop-far` | `#1B4B8F` | Desktop background gradient, bottom |

Light surfaces (dashboard cards sit on `surface`; no light theme in
this pass). The desktop background is an original two-stop vertical
gradient in the Windows 11 spirit — no Bloom artwork.

### Type

- Family: **Selawik** (regular + semibold), fallback DejaVu Sans.
- Login user name: 32 px regular. Dashboard page title: 20 px
  semibold. Body: 14 px. Small/caption: 12 px. Panel clock: 12 px.

### Geometry

- Window corner radius: **8 px** (ARGB buffers; corners fully
  transparent). Card radius: 8 px. Button/field radius: 4 px.
- App title bar: 32 px high. Caption buttons: 46×32 px at the
  title bar's right edge, order minimize, maximize/restore, close.
  Glyphs are drawn primitives (line, square, ×) in `ink`; close
  hovers `danger`, others hover `surface-hi`.
- Panel: 48 px high, bottom edge. Login avatar: 128 px diameter
  circle, `surface-hi` fill with the owner's initial(s) in 48 px.
- Login password field: 320×36 px, radius 4, centred.

## Motion

- Curve: ease-out cubic approximation of the Windows 11 curve
  (fast start, gentle settle). No linear motion, no overshoot.
- Durations: page slide **280 ms**; menu/panel slide **200 ms**;
  hover/focus fade **150 ms**; window zoom/fade via Weston's
  springs (compositor-tuned, not client-timed).
- Frame-driven: `veil-display` animates on its input/timer loop;
  Wayland clients animate on frame callbacks. Frame skipping is
  permitted under load; an animation must never delay input
  handling — a keystroke or click during a transition is processed
  immediately and cancels or completes the transition.
- **Full-screen cost rule (veil-display):** at 3840×2160 a slide is
  two full frames per step in software. If the joined acceptance
  shows jank on the login transitions, fall back to a
  half-amplitude slide (pages travel 50% of the distance with a
  crossfade), then to crossfade-only. Record which level shipped
  in the slice's validation note.
- Reduced motion: a build-time constant `UI_MOTION=0` disables
  client-side sliding entirely (instant transitions), for
  diagnosis. Default is motion on.

## Surfaces

### Lock/login (veil-display)

Centred composition on the desktop gradient: avatar circle, owner
name under it, password field under that, sign-in affordance is
the field itself (Enter submits — unchanged behaviour). Wrong
password: the field shakes horizontally ±8 px over 200 ms and the
existing denial text appears (wording unchanged). Enrollment
screens keep their existing steps, order, and wording; only
layout, tokens, and transitions change. Session pages slide
horizontally (outgoing left, incoming from right; Back reverses).

### Dashboard (veil-display)

Left navigation rail (Settings-style): page names with simple
geometric glyphs, selected item shown as a `surface-hi` pill with
an `accent` left bar. Content area is cards on `surface` with
`stroke` borders. All existing pages, data, and controls carry
over; only presentation changes. No control may be drawn that has
no real function.

### Panel (weston.ini presentation keys)

`panel-position=bottom` if the pinned desktop-shell parses it from
the ini (verify against the pinned source; otherwise set the
position through the shell's panel-position protocol from the
session, and record which route shipped). `panel-color` =
`shell` token, `background-color` = `desktop-near` token.
Animations: `animation=zoom`, `close-animation=fade`,
`startup-animation=fade`, `focus-animation=none`.

### Synveil applications (desktop-wayland clients)

Title bar per the geometry tokens: app glyph (simple original
geometric mark) + title at the left in 12 px semibold, caption
buttons at the right with real minimize/maximize/close behaviour
matching what each window already supports (a window that cannot
maximize does not gain a maximize button). Body surfaces use
`surface`; selection uses `accent` at 25% blend over `surface`
(precomputed). Menus and page changes slide per the motion rules.
The updates window keeps its five actions, order, and
confirmations exactly; its purple title bar is replaced by the
standard chrome.

## Out of scope / recorded gaps

- No Start menu or task buttons: stock `desktop-shell.so` has
  neither. A custom shell is a separate owner decision (ADR 0024).
- No compositor-level slide for window map/minimize in stock
  Weston; `zoom`/`fade` springs are the available motion.
- Chromium and weston-terminal interiors are unchanged.
- No authentication, seat, boot, or updater behaviour changes.
