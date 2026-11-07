# ADR 0024: Windows 11 design language for the login, dashboard, and desktop surfaces

- Status: Accepted
- Date: 2026-11-05
- Supersedes: none
- Superseded by: none
- Related: [ADR 0023](0023-physical-validation-parked-boot-update-freeze.md)
  (boot/update freeze; this ADR records the owner-approved carve-outs
  for presentation work), [ADR 0015](0015-first-owner-enrollment.md),
  [ADR 0018](0018-login-vt-graphics-handoff.md),
  [ADR 0022](0022-weston-subsurface-assert-and-pixbuf-data.md),
  `docs/UI_DESIGN.md` (the design spec this ADR adopts).

## Context

ADR 0023 parked physical validation and froze the boot/update
mechanisms, with the working queue resuming at the Phase 2 durable
audit format. Before that queue starts, the owner directed a
redesign of the login and UI: the system should look like Microsoft
Windows, move smoothly with sliding motion instead of snapping, and
visually work like Windows at the GUI level. The owner chose the
**Windows 11** design language (over Windows 10) on 2026-11-05.

Current presentation state:

- `src/veil-display/` is a hand-drawn framebuffer program: owner
  enrollment, graphical login, and the fixed-UID dashboard
  (Status/Storage/Network/Terminal/Settings pages). Every pixel is
  Synveil-rendered; page changes are instant redraws.
- The Weston session uses the stock `desktop-shell.so` with every
  animation explicitly disabled in `build/rootfs/weston.ini`
  (`animation=none`, close/focus/startup animations `none`) and the
  panel in its default top position.
- The Synveil desktop clients (`src/desktop-wayland/`: files,
  updates, demo window) are hand-drawn C Wayland clients with
  custom title bars, set in DejaVu Sans.

The pinned Weston 15.0.1 desktop-shell supports a bottom panel
position and built-in spring animations (`fade`, `zoom`). It has no
Start menu, no task buttons, and no slide animation type; those are
recorded gaps, not problems this ADR papers over.

## Decision

1. **Design language: Windows 11**, as specified in
   `docs/UI_DESIGN.md`: bottom panel, centered login composition,
   8 px window corner radius, caption buttons
   (minimize/maximize/close) at the right of title bars, the spec's
   palette and accent, and card-based dashboard pages with a left
   navigation rail. Artwork is original work in that style: no
   Microsoft assets, logos, wallpaper, or icon artwork are copied.
   The UI typeface is **Selawik** (open licence, metric-compatible
   with Segoe UI); Segoe UI itself is proprietary and is not
   shipped. DejaVu Sans remains the fallback.

2. **Motion: sliding over snapping.** Page, menu, and panel
   transitions slide with the spec's durations and ease-out curve
   (200–300 ms class). In `veil-display` and the Synveil clients,
   transitions are frame-driven redraws. At the compositor level,
   Weston's built-in `zoom`/`fade` springs are enabled via
   `weston.ini`; stock Weston provides no slide for window
   mapping/minimize, and that gap stands until a future decision.

3. **Freeze carve-outs (ADR 0023).** The owner approves
   presentation-only changes to:
   - `src/veil-display/` **rendering code only**. Authentication
     logic, credential handling, enrollment flow semantics, and
     the seat-broker protocol are unchanged. A control that exists
     on screen must keep its real function; no decorative fake
     controls are drawn.
   - The Synveil desktop clients' chrome and rendering. The
     updates window's behaviour contract with the updater (same
     actions, same confirmations, same wording of record in the
     audit trail) is unchanged; only presentation changes.
   - `build/rootfs/weston.ini` **presentation keys** (panel
     position, colours, animation keys). The session startup
     mechanism (`weston-session`, the seat-lease flow) is
     unchanged.

   Per ADR 0023, every slice is validated by the joined QEMU
   acceptance (boot → enroll/login → desktop → update round trip)
   with before/after screenshots recorded.

4. **Not authorized by this ADR:** replacing `desktop-shell.so`
   with a custom shell (a Start menu / taskbar shell is a separate
   future owner decision), any change to the boot chain or the
   updater, and any change to authentication mechanics.
   *Amendment (2026-11-06): the owner made that future decision —
   the custom shell is authorized by
   [ADR 0025](0025-custom-shell-start-menu-taskbar.md), for the
   shell only. The boot chain, updater, and authentication
   exclusions above are unchanged.*

No firmware variables are written by this work. No sandbox, TLS,
or connection behaviour changes.

## Consequences

- Synveil's visual identity becomes the Windows 11 language across
  login, dashboard, panel placement, and its own applications.
  Third-party application interiors (Chromium, weston-terminal)
  keep their own look; the redesign covers Synveil's surfaces.
- Selawik is added to the image payload for the Synveil clients
  and `veil-display`; that payload change is gated by the joined
  QEMU acceptance like any other under ADR 0023.
- Full-screen sliding at 3840×2160 in software-rendered
  `veil-display` is bandwidth-heavy; the design spec's
  frame-skipping and reduced-amplitude fallback rules apply if
  the joined acceptance shows jank. Smooth must never cost the
  login its responsiveness.
- The compositor-level motion gap (no slide for window
  map/minimize in stock Weston) remains an explicitly recorded
  limitation until the owner decides on a custom shell.
