# ADR 0022: Weston subsurface-order assert (carried patch) and the distro payload's missing image-format data

- Status: Accepted
- Date: 2026-11-02
- Supersedes: none
- Superseded by: none
- Related: [ADR 0013](0013-first-install-and-desktop-priority.md)
  (owner desktop priority), the browser/downloads acceptance record
  (`docs/validation/browser-qemu-proof-2026-10-27/`)

## Context

Two defects were filmed on the owner's machine (QEMU 11.1 on the
TG01, WHPX and TCG) against the shipped `db32105` test-media
package, plus one observability gap that made the first defect
hard to see:

1. **The desktop session dies seconds after login.** Weston
   15.0.1 aborts with
   `../libweston/surface-state.c:282: Assertion
   comp->view_list_needs_rebuild == true (0 == 1) failed!`,
   followed by `weston-session: desktop did not survive the
   window close` and a session restart. Session lifetime varied
   from seconds to minutes — a race.
   Mechanism, verified against the pinned source:
   `weston_surface_apply_subsurface_order()` reorders pending
   subsurfaces and calls `weston_view_geometry_dirty()` per view;
   that function sets `compositor->view_list_needs_rebuild` only
   when a reordered subsurface actually has views. A client that
   creates a subsurface and reorders it **before the subsurface
   is first mapped** has no views, so the flag stays false and
   the trailing `weston_assert_true` aborts the compositor for a
   legitimate client pattern. The assertion follows
   `BROWSER_STARTED` in the filmed sessions (Chromium is
   subsurface-heavy), but the trigger client is not proven and
   does not matter: any client may do this.
2. **GTK image loading fails inside Chromium.** Opening the GTK
   file dialog asserted with `image-missing.png`:
   "Unrecognized image file format (gdk-pixbuf-error-quark, 3)".
   Root cause, established by bisecting the packaged rootfs: the
   distro-Chromium stage sealed `usr/share/mime/` with only the
   `packages/` XML sources. The generated shared-mime-info
   database (`mime.cache`, `globs`, `magic`, …) is a
   maintainer-script product the stage never generated, and
   gdk-pixbuf recognizes image files through GIO content-type
   guessing, which is blind without it — so **every** image load
   failed with error 3, including formats whose loaders are
   compiled in. Contrary to the initial hypothesis, PNG/JPEG
   need no loader module: in the pinned libgdk-pixbuf
   2.42.12+dfsg-4+deb13u1 they are compiled into the library
   (it links libpng16/libjpeg directly and registers both
   formats with no loaders.cache present). Debian 13's glycin
   plays no part: the pinned snapshot ships glycin 1.2.1, but no
   package provides a gdk-pixbuf glycin module and nothing in
   the pixbuf stack depends on it. The 11 `.so` module loaders
   the payload does ship (gif, ico, bmp, tiff, …) additionally
   never registered, because the payload also lacked
   `loaders.cache`. One gap remains, out of scope here:
   Adwaita's `image-missing` icon is SVG-only and no SVG loader
   (librsvg) is in the package closure; GTK falls back to its
   built-in PNG resource, which is the load the mime database
   fixes.
3. **weston-session's fatal branches left no on-disk record.**
   Every fatal exit echoed to the console only; the session log
   (`weston-session.log`, the file post-mortem extraction reads)
   received only the success-path marks, so a filmed failure
   could not be confirmed from the extracted logs afterwards.

## Decision

1. **Carry a minimal patch against the pinned Weston 15.0.1**
   (`build/native/patches/weston/weston-15.0.1-subsurface-order-assert.patch`),
   applied by the native Weston recipe through Buildroot's
   `BR2_GLOBAL_PATCH_DIR` after the tarball's forced hash check:

   ```diff
   -	weston_assert_true(comp, comp->view_list_needs_rebuild);
   +	/* Applying a new subsurface order is itself a view-order change.
   +	 * The geometry-dirty calls above only set this flag when a
   +	 * reordered subsurface already has views; a subsurface reordered
   +	 * before its first map has none, and the previous assert aborted
   +	 * the compositor for that legitimate client pattern. Setting the
   +	 * flag unconditionally is always safe: the rebuild is idempotent
   +	 * and a no-op when no views exist. */
   +	comp->view_list_needs_rebuild = true;
   ```

   Safety: applying a new subsurface order *is* a view-order
   change, so the flag's postcondition is the function's own
   contract; the rebuild it schedules is idempotent and a no-op
   when no views exist. The patch removes no check with a
   protective purpose — the assert guarded an implementation
   assumption, not a safety invariant. Upstream later reworked
   this area the same way (the flag is set when subsurface
   configuration is dirtied, independent of views).
   Recipe integrity, in the stage's existing style: a cached
   unpatched tree is `weston-dirclean`ed so it cannot survive
   into a build; a post-build gate fails unless the tree being
   compiled carries the change; `validation.json` records the
   patch name, the patch file's SHA-256
   (`bb4bf87e8ff51b12647860600fffcfcc348516eae198ea04b46fbd7e01ec5b40`),
   and the patched `libweston/surface-state.c` SHA-256
   (`99e3b8a532d3ebeff5a6556f49ec117b5e4fb34c1d5c51f7b917a3d22364636e`,
   identical to a pristine-extraction dry run).
2. **Generate the two missing derived artifacts in the
   distro-Chromium stage** (`tools/distro_chromium.py`,
   `generate_derived()`), with the closure's own pinned tools
   run under the closure's loader/libc (never the host's):
   `gdk-pixbuf-query-loaders` writes `loaders.cache` with module
   paths rewritten to guest paths, and `update-mime-database`
   generates the shared-mime-info database. A post-seal gate
   fails the build unless both are sealed, complete, and
   guest-addressed; `validation.json` records the gate
   (`pixbuf_mime_gate`). The manifest gains no packages: the
   loaders and the database sources were already in the
   closure; only their generated products were missing. (The
   stage's apt resolve also now passes
   `Acquire::Check-Valid-Until=false`: the pinned 20261024
   snapshot's trixie-security Release expired 2026-10-31 and
   blocked all rebuilds; every .deb remains SHA-256-verified
   against the manifest and the snapshot index, so freshness
   was never a property taken from apt.)
   Verified against the packaged rootfs in a chroot of the
   image's own files: PNG decode OK, GIF decode OK (module
   loader via the generated cache), all 13 formats registered.
3. **Route every weston-session fatal branch through a
   `fail()` helper** that echoes the identical message and
   appends it to `weston-session.log` before exiting 1.
   Success marks and behavior are otherwise unchanged.

No sandbox, TLS, browser-launch, or connection behavior
changes. No firmware variables are written by any part of
this pass. The publisher key is unchanged
(`synveil-dev-2026-01`, development).

## Consequences

- A new test-media package was built from source `a236213`
  (image SHA-256
  `f45a79c3bdf0690b3670ef0971f0457e5511d4a1e659724b05d45c8bea767f38`);
  the `db32105` package is superseded and must not be written.
  Record: `docs/validation/test-media-fixpass-2026-11-02/`.
- **Guest re-verification on the owner's machine (TG01, VM or
  physical) is still outstanding.** The fixes are proven at
  source, stage-gate, and packaged-rootfs level, and the local
  QEMU result is recorded in the validation record; the filmed
  failure modes (session survival across minutes of desktop
  use, the GTK save dialog) can only be closed where they were
  filmed.
- The carried Weston patch must be dropped if a future Weston
  pin contains the upstream rework; the build gate fails
  closed (patch absent from the tree) rather than silently
  shipping the assert again.
