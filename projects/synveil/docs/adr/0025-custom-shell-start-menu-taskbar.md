# ADR 0025: Custom shell — Start menu and task buttons in the desktop shell

- Status: Accepted
- Date: 2026-11-06
- Supersedes: none. This ADR **amends ADR 0024 clause 4** in one
  respect: the custom shell it reserved as "a separate future
  owner decision" is authorized by this ADR. ADR 0024 otherwise
  stands, including its freeze carve-outs and its rule that every
  visible control must be real.
- Superseded by: none
- Related: [ADR 0023](0023-physical-validation-parked-boot-update-freeze.md)
  (boot/update freeze; this work stays outside the frozen zones),
  [ADR 0024](0024-windows-11-ui-design-language.md) (the design
  language and tokens the shell is built in),
  [ADR 0022](0022-weston-subsurface-assert-and-pixbuf-data.md)
  (the carried-patch mechanism this work reuses),
  `docs/UI_DESIGN.md` (design spec; its recorded Start-menu gap
  is closed by this ADR).

## Context

ADR 0024 adopted the Windows 11 design language for Synveil's
surfaces but recorded that the stock Weston 15.0.1
`desktop-shell.so` has no Start menu and no task buttons, and
that replacing it was not authorized. On 2026-11-06 the owner
authorized exactly that work ("S4"): a custom shell with a
Start button and Start menu, task buttons for open windows, and
the panel clock, in the UI_DESIGN tokens, with every control
real. The boot chain, the updater, and authentication mechanics
remain unauthorized and frozen under ADR 0023, and the session
startup mechanism (`weston-session`, the seat-lease flow) is
unchanged.

Weston's architecture splits the shell plugin
(`desktop-shell.so`, window management inside the compositor)
from its helper client (`weston-desktop-shell`, which draws the
background and panel under the shell's direction via the
desktop-shell protocol). The pinned Weston is built from source
by this project with a carried-patch mechanism (ADR 0022), so a
patched shell stays reproducible from the pinned tarball.

## Decision

1. **The custom shell is the pinned Weston's desktop shell,
   patched in place** through the carried-patch mechanism
   (`build/native/patches/weston/`). The module keeps the name
   `desktop-shell.so`; `weston.ini` keeps `shell=desktop-shell.so`;
   no Buildroot configuration, module set, or session file
   changes. The patch is verified by the native Weston build
   gate like the ADR 0022 patch before it.

2. **A small private protocol** between the shell and its own
   helper client carries the window list: the shell (which alone
   knows the toplevel surfaces) publishes window add/remove and
   title/state changes; the helper requests activation and
   minimization, which the shell performs with its existing
   window-management paths. The helper is the shell's own
   privileged client (launched and identified by the shell, as
   stock); no other client can bind the protocol's privileged
   requests, and toplevel clients gain no new powers.

3. **Panel behaviour (helper client, UI_DESIGN tokens).** The
   bottom panel is 48 px, `shell` (#202020): a Start button
   (original four-pane geometric mark), task buttons for open
   windows (window title; the active window is marked with the
   `accent` underline and raised surface; clicking a task button
   activates/raises its window, clicking the active window's
   button minimizes it — the behaviour the compositor protocol
   supports), and the existing clock. The Start menu lists the
   desktop applications the image actually ships — gated by the
   same marker files `weston-session` uses (`/etc/synveil/files-app`,
   `/etc/synveil/browser`, `/etc/synveil/ab-system`) plus the
   always-present terminal and demo window — and launches them
   by executing the same binaries the session launches. The
   menu offers **no session actions**: the existing session
   machinery exposes no logout or lock request the shell could
   honestly invoke (the session ends when its two initial
   windows close), so none is drawn, per ADR 0024's
   no-fake-controls rule.

4. **Motion.** Menus and panel transitions use the fade/zoom
   springs stock Weston provides plus the helper's own
   frame-driven fade for the menu, per UI_DESIGN.md. Stock
   Weston still provides no compositor slide for window
   map/minimize; that recorded gap stands and is not papered
   over.

5. **Validation** is the joined QEMU acceptance plus a
   dedicated shell acceptance with screenshots (desktop with
   the new panel, Start menu open, an application launched from
   the menu, task-button activate/minimize), and the existing
   desktop-touching smokes (joined, files, browser, A/B round
   trip) re-run, per ADR 0023 Decision 3. QEMU evidence only;
   physical validation remains parked.

## Rationale

Patching the pinned shell in place reuses the project's
existing source-pin and patch-verification machinery, keeps
every other consumer of the desktop shell (session script,
smoke locators keyed on window appearance, the updates/files
clients) working against the same protocol and module, and
confines the new attack surface to one private protocol bound
only by the shell's own helper. A from-scratch shell module
would re-implement Weston's window management (the part most
likely to break the frozen-adjacent session behaviour) for no
functional gain.

## Alternatives considered

- **A separate new shell module alongside desktop-shell.**
  Rejected: duplicates Weston's window management and splits
  the validation surface; see above.
- **Start menu and task buttons as ordinary clients.**
  Rejected: ordinary xdg-toplevel clients cannot position
  themselves at the panel, cannot enumerate other clients'
  windows, and cannot raise them; the controls would be fake
  or absent.
- **Ini launcher icons only (stock capability).** Rejected by
  the owner's S4 direction: launchers are not a Start menu and
  say nothing about open windows.

## Consequences

### Positive

- The desktop gains the Start menu and task buttons ADR 0024
  recorded as a gap, in the adopted design language, with all
  controls functional.
- The change rides the existing image/update path as userspace
  payload; the frozen boot/update zones are untouched.

### Negative / tradeoffs

- The carried Weston patch grows from a one-function fix to a
  shell feature patch; it must be re-based by hand when the
  pinned Weston version changes, and the native build gate
  verifies its markers like the ADR 0022 patch.
- The private shell/helper protocol is Synveil-specific and
  version-locked to the pinned Weston, by design.

## Security implications

The private protocol is advertised by the compositor but its
state-changing requests are honored only from the shell's own
helper client (identified by the shell at launch, the stock
desktop-shell trust pattern). Window titles are the only client
data crossing it — the same titles the panel would draw in any
taskbar design. No new client-visible capability is created:
activation/minimization requests name windows the shell
published to its helper, and the shell performs them itself.
No boot, updater, authentication, or firmware-variable surface
changes.

## Reversibility

Dropping the patch files and rebuilding restores the stock
desktop shell exactly (the ADR 0022 gate pattern); the image
payload differs only in the shell module and helper client.

## Validation

Joined QEMU acceptance with the shell acceptance screenshots
under `docs/validation/`, the A/B update round trip on the
same revision, and the host-side patch-tree verification in
the native Weston build. See `docs/VALIDATION.md`.
