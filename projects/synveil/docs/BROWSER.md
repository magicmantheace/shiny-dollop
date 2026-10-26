# Networking and the graphical browser

Status: **QEMU-proven** (Priority 3/4 acceptance,
`docs/validation/browser-qemu-proof-2026-10-26/`). No physical
hardware claim: the TG01's Ethernet/Wi-Fi devices, their kernel
drivers, and firmware are unverified — the proof uses QEMU's
`virtio-net-pci` with user networking (slirp), which is also the
only network device the current kernel configuration targets.

## Evaluation and choice

The sealed image is a static-BusyBox rootfs plus source-built
components, booting as a single initramfs UKI (~61 MB baseline).
Candidates were judged against that reality, not against a
conventional distribution:

| Candidate | Verdict |
|---|---|
| Firefox | Established engine, native Wayland — but no Buildroot recipe exists (only binary repackaging upstream), the source build is multi-GB/multi-hour with a Rust+LLVM toolchain the pinned recipes do not carry, and its size dwarfs the whole sealed image. Impractical in this build system. |
| Chromium | Same class of problem, worse: a depot_tools/GN build that cannot be expressed in the pinned Buildroot recipes at all. |
| WebKitGTK | In the pinned recipes, but it is a very large C++ stack (WebCore/JSC) with a long tail of media/codec dependencies; build time and image growth are disproportionate for this milestone. |
| **NetSurf (GTK3 frontend)** | **Chosen.** An established, independently developed browser (since 2003) with a real release history, present in the pinned Buildroot recipes (3.10) with a content-hash-pinned tarball. Its GTK3 frontend is a **native Wayland client** through GDK's Wayland backend — no XWayland, no Xorg anywhere. Of the frontends usable on this stack it is the only one with a download manager (the framebuffer frontend registers none — downloads are impossible there). |

Honest limitations of the choice, recorded rather than smoothed
over:

- NetSurf's engine (LibDOM/Hubbub) is far behind Gecko/Blink on
  modern web compatibility. It renders standards-based pages; it
  is not a general replacement for Firefox on the open web.
- **NetSurf has no multi-process sandbox.** Isolation is the
  session's ordinary one: the browser runs as the authenticated
  unprivileged user (uid 1000), the home mount is nosuid/nodev,
  and the browser cannot write outside the user's home. There is
  no seccomp/namespace sandbox to claim, so none is claimed.
- JavaScript support (Duktape) is present in the recipe set but
  basic; the acceptance does not depend on it.

## How it is built

`tools/native_browser.py` mirrors the Weston stage exactly: the
pinned Buildroot recipes (2026.08.1, commit
`7fdeadb3b9f12f78e5fccca914d7fef47090ab9a`) with the project's
external toolchain, packages-only (`make netsurf`), sources
hash-forced (`BR2_DOWNLOAD_FORCE_CHECK_HASHES=y`), glibc
preservation verified against the Weston stage, and the output
sealed by `tools/native_browser_assets.py`
(`build/manifests/native-browser.json` is the pin record).
Mesa is compiled only because Buildroot's GTK-Wayland
configuration requires an EGL/GLES provider at build time; the
browser draws with Cairo and creates no GL context, and Mesa's
DRI drivers are excluded from the seal.

Two build-time facts worth knowing:

- GTK's schema cache (`gschemas.compiled`) is a target-finalize
  product; the packages-only build never runs finalize, so the
  builder compiles it with the build's own host tool before
  sealing and refuses to seal without a gdk-pixbuf loader cache.
- `host-vim` exists in the dependency set only for its `xxd` host
  tool; its configure needs `-lncurses`, which the stock
  host-ncurses install does not provide (wide library only). The
  builder adds the plain-name symlink after building
  host-ncurses. A package-override `+=` does not reach a host
  package's configure line in this Buildroot version (verified
  empirically, 2026-10-26).

## Integration

`tools/native_ab.py --browser` builds the proof disk under
`out/browser-proof/`: each generation rootfs additionally gets

- the sealed browser payload (byte-verified against the seal;
  every copied ELF's `DT_NEEDED` closure is checked against the
  finished rootfs, so a missing library fails the build, not the
  first boot),
- `configure-network` + `udhcpc-script` in
  `/usr/libexec/synveil/` (the joined image's network hooks:
  link wait, DHCP, `SYNVEIL_NETWORK_READY`),
- the browser launcher `/usr/bin/synveil-browser` and the
  `/etc/synveil/browser` + `/etc/synveil/files-app` markers the
  Weston session keys on,
- a `[launcher]` entry (icon) appended to `weston.ini` — the
  graphical launch entry in the desktop panel.

The session (`build/rootfs/weston-session`) starts the browser
after login when the marker exists. The launcher refuses to run
as any uid but the session user's, creates `~/Downloads` (0700),
seeds NetSurf's profile at `$HOME/.netsurf/Choices` **only if
absent** (first run) with `downloads_directory` pointing at the
persistent home, and execs `netsurf-gtk3` with the start URL
from `/etc/synveil/browser-start-url` when present. It sets no
TLS-related option, ever.

The profile, the downloads, and all session state live under
`/home/synveil`, which the A/B machinery mounts from the DATA
partition — outside both replaceable generations, so profile and
downloads survive update and rollback by construction, and the
acceptance proves they do.

## TLS and trust

TLS verification is libcurl's default and is **never disabled** —
not in the browser, not in any fixture, not with any flag. The
proof's controlled endpoint is a local HTTPS server whose
certificate (SAN: `test.synveil.invalid`, `10.0.2.2`) is signed
by a per-run test CA; the image build installs **that CA** as the
generations' trust bundle and records its sha256 in the build
receipt, and the test driver refuses to run against a disk whose
receipt names a different CA. A second endpoint serves the same
name from an unrelated CA; the gate requires zero GET requests
there plus at least one refused handshake — a browser that
verified nothing could not produce that record.

Production images built without `--browser-test-ca` currently
ship **no root CA bundle at all** (no CA-certificates package is
selected yet): HTTPS to real sites will fail verification until a
curated bundle is added through the same sealed-build route.
That is the honest state; failing closed is the correct default.

## Downloads

Semantics are NetSurf GTK's, verified against the pinned 3.10
source (`frontends/gtk/download.c`) and exercised by the
acceptance:

- Clicking a downloadable link opens a dialog — **Save** (to the
  downloads directory), **Cancel**, or **Save As** (file chooser,
  starting in the downloads directory). Nothing is written
  before the user chooses.
- If the target file exists, Save asks again — **Replace** or
  **Cancel** (`request_overwrite`, default on). There is no
  silent overwrite path.
- Write failures (including a full disk) surface an error dialog;
  the partial file is the download manager's to report, and the
  acceptance proves no complete oversized file remains.
- Downloads are never executed or installed: nothing in the
  browser, the session, or the image opens a downloaded file.

Graphical file access is `synveil-files`
(`src/desktop-wayland/files-window.c`), a small read-only native
Wayland window the session opens alongside the browser: it lists
the Downloads directory, then the home directory — names and
sizes, dotfiles skipped, nothing opened, executed, moved, or
deleted — with a Refresh button and a session log
(`~/files-window.log`) recording every scan. It is deliberately
not a file manager; it is the minimal graphical path by which a
user can see that a download is where it should be.

## The acceptance

`tests/smoke-native-browser.py` (see its docstring for B0–B7):
graphical login → browser autostarts → the proof page loads over
verified HTTPS → a known payload downloads → its digest is
computed **inside the guest** and the bytes are read back from
the disk image host-side → collision/Cancel → oversized download
→ bad-CA refusal → cold reboot → A/B update to v2 → second
payload → rollback to v1 — with digests, profile, and credential
verified at every readback, and every verdict re-derived by
`validate_browser_results` from the recorded artifacts (the
server's request log travels inside the receipt; missing
artifacts fail). Negative tests for the gate live in
`tests/smoke-gates.py` (`BrowserGate`).

Reproduce:

```
python3 tests/smoke-native-browser.py --prepare-tls   # prints the build command
python3 tools/native_ab.py --build --browser --browser-test-ca <ca.pem> \
    --browser-test-host 10.0.2.2 test.synveil.invalid \
    --browser-start-url https://test.synveil.invalid:8443/
python3 tests/smoke-native-browser.py                  # non-root
```

## Open items

- Hardware networking (TG01 devices/drivers) — unverified.
- A curated production CA bundle — not yet selected.
- Browser window management under Weston is minimal (no
  maximize state handling of the kind the first window needed);
  the browser is a guest application, and its window simply
  opens at its requested size.
- The downloads window has no graphical cancel interaction in
  the acceptance; per-download cancel exists in NetSurf's UI and
  is unexercised by the proof.
