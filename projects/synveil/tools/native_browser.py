#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Build the source-pinned browser stage with Synveil's own GCC/glibc.

The browser is NetSurf (established engine, first release 2007)
with its GTK3 frontend on the GDK Wayland backend — the only
NetSurf frontend with a download manager, and a native Wayland
client of the sealed Weston stack (no XWayland, no SDL layer).
Buildroot is a pinned package-recipe executor only, exactly as in
tools/native_weston.py: no image/rootfs target is invoked and its
generated /etc, init or accounts are never imported.

Mesa is present in this build for one reason: Buildroot's GTK3
Wayland backend configuration requires an EGL/GLES provider at
build time. NetSurf draws with Cairo software surfaces and never
creates a GL context; which Mesa files (if any) become runtime
assets is decided by the asset seal and the DT_NEEDED closure
check at image-build time, not by this build's package list.
"""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import native_libffi as ffi
import native_weston as weston
import native_browser_assets as assets

OUT = ROOT / "out/native-browser"
LOCK = ROOT / "build/manifests/native-browser.json"
RECIPE_COMMIT = weston.RECIPE_COMMIT
NETSURF_SHA256 = "495adf6b6614ce36fca6c605f7c321f9cb4a3df838043158122678ce2b3325b7"
NETSURF_VERSION = "3.10"


def source_pin():
    data = json.loads(LOCK.read_text())
    if (data.get("schema") != "synveil.native-browser/v1" or
        data.get("target") != ffi.TARGET or
        data.get("recipe_builder") != {
            "repository": "https://github.com/buildroot/buildroot.git",
            "tag": "2026.08.1", "commit": RECIPE_COMMIT} or
        data.get("netsurf") != {"version": NETSURF_VERSION,
                                "sha256": NETSURF_SHA256}):
        raise ValueError("unreviewed browser source or dependency-recipe identity")
    weston.source_pin()
    return data


def configuration(toolchain, overrides):
    # The toolchain/init lines are the Weston stage's, verbatim:
    # same external toolchain, no internal compiler/libc/bootloader,
    # forced hash checking on every downloaded source.
    lines = [
        'BR2_x86_64=y', 'BR2_TOOLCHAIN_EXTERNAL=y',
        'BR2_TOOLCHAIN_EXTERNAL_CUSTOM=y', 'BR2_TOOLCHAIN_EXTERNAL_PREINSTALLED=y',
        'BR2_TOOLCHAIN_EXTERNAL_PATH=' + json.dumps(str(toolchain)),
        'BR2_TOOLCHAIN_EXTERNAL_CUSTOM_PREFIX="' + ffi.TARGET + '"',
        'BR2_TOOLCHAIN_EXTERNAL_CUSTOM_GCC_16=y', 'BR2_TOOLCHAIN_EXTERNAL_HEADERS_6_18=y',
        'BR2_TOOLCHAIN_EXTERNAL_CUSTOM_GLIBC=y', 'BR2_TOOLCHAIN_EXTERNAL_CXX=y',
        '# BR2_TOOLCHAIN_EXTERNAL_INET_RPC is not set',
        'BR2_REPRODUCIBLE=y', 'BR2_DOWNLOAD_FORCE_CHECK_HASHES=y',
        'BR2_PACKAGE_OVERRIDE_FILE=' + json.dumps(str(overrides)),
        'BR2_INIT_NONE=y', 'BR2_ROOTFS_DEVICE_CREATION_DYNAMIC_EUDEV=y',
        '# BR2_PACKAGE_BUSYBOX is not set', '# BR2_TARGET_ROOTFS_TAR is not set',
        # The browser stack: NetSurf + its GTK3 frontend (GDK Wayland
        # backend only — no X11/Xorg anywhere in this build), the
        # libcurl/OpenSSL fetch stack (TLS verification is libcurl's
        # default and is never disabled), and Mesa solely as the
        # build-time EGL/GLES provider the GTK Wayland configuration
        # requires.
        'BR2_PACKAGE_NETSURF=y', 'BR2_PACKAGE_NETSURF_GTK3=y',
        'BR2_PACKAGE_LIBCURL=y', 'BR2_PACKAGE_LIBCURL_OPENSSL=y',
        'BR2_PACKAGE_LIBGTK3=y', 'BR2_PACKAGE_LIBGTK3_WAYLAND=y',
        'BR2_PACKAGE_MESA3D=y', 'BR2_PACKAGE_MESA3D_OPENGL_EGL=y',
        'BR2_PACKAGE_MESA3D_OPENGL_ES=y',
        # OPENGL_EGL depends on a gallium driver in this recipe
        # set; softpipe is the no-LLVM software driver. Mesa is
        # still only the build-time EGL/GLES provider (see module
        # docstring); the image never renders through it.
        'BR2_PACKAGE_MESA3D_GALLIUM_DRIVER_SOFTPIPE=y',
    ]
    return "\n".join(lines) + "\n"


def check_configuration(text, toolchain):
    settings = dict(line.split("=", 1) for line in text.splitlines()
                    if line and not line.startswith("#") and "=" in line)
    for key in ("BR2_TOOLCHAIN_EXTERNAL", "BR2_TOOLCHAIN_EXTERNAL_CUSTOM",
                "BR2_TOOLCHAIN_EXTERNAL_CUSTOM_GLIBC", "BR2_TOOLCHAIN_EXTERNAL_CXX",
                "BR2_TOOLCHAIN_EXTERNAL_GCC_16", "BR2_TOOLCHAIN_EXTERNAL_HEADERS_6_18",
                "BR2_DOWNLOAD_FORCE_CHECK_HASHES", "BR2_INIT_NONE",
                "BR2_PACKAGE_NETSURF", "BR2_PACKAGE_NETSURF_GTK3",
                "BR2_PACKAGE_LIBCURL", "BR2_PACKAGE_LIBCURL_OPENSSL",
                "BR2_PACKAGE_LIBGTK3", "BR2_PACKAGE_LIBGTK3_WAYLAND",
                "BR2_PACKAGE_MESA3D", "BR2_PACKAGE_HAS_LIBEGL"):
        if settings.get(key) != "y":
            raise ValueError("native browser configuration lost required " + key)
    if settings.get("BR2_TOOLCHAIN_EXTERNAL_PATH") != json.dumps(str(toolchain)):
        raise ValueError("dependency builder substituted the native compiler")
    if settings.get("BR2_TOOLCHAIN_EXTERNAL_PREFIX") != json.dumps(ffi.TARGET):
        raise ValueError("dependency builder substituted the native target")
    forbidden = ("BR2_LINUX_KERNEL", "BR2_TARGET_GRUB2", "BR2_TOOLCHAIN_BUILDROOT",
                 "BR2_PACKAGE_BUSYBOX", "BR2_PACKAGE_SYSTEMD", "BR2_INIT_BUSYBOX",
                 "BR2_INIT_SYSTEMD", "BR2_PACKAGE_XORG7", "BR2_PACKAGE_LIBGTK3_X11",
                 "BR2_PACKAGE_NETSURF_SDL")
    if any(settings.get(key) == "y" for key in forbidden):
        raise ValueError("unexpected system/boot/X11 stack in browser dependency build")
    if any(key.startswith("BR2_TARGET_ROOTFS_") and value == "y"
           for key, value in settings.items()):
        raise ValueError("dependency build must not generate a root filesystem image")


def run(argv, **kwargs):
    subprocess.run([str(a) for a in argv], check=True, **kwargs)


def target_finalize_fixups(build_dir):
    """The packages-only build never runs Buildroot's target
    finalize, which is where glib's schema compilation normally
    happens. GTK's file chooser and settings machinery expect
    gschemas.compiled; compile it with the build's own host tool,
    into the target tree, before sealing. gdk-pixbuf's loader cache
    is generated per-package by its own target hooks in this
    Buildroot version; verify it exists instead of inventing one."""
    notes = []
    target = build_dir / "target"
    schemas = target / "usr/share/glib-2.0/schemas"
    compiled = schemas / "gschemas.compiled"
    if schemas.is_dir() and any(schemas.glob("*.gschema.xml")) and not compiled.exists():
        tool = build_dir / "host/bin/glib-compile-schemas"
        if not tool.is_file():
            raise ValueError("host glib-compile-schemas missing for schema fixup")
        run([str(tool), str(schemas)])
        notes.append("gschemas.compiled generated with the build's host tool")
    loaders = list((target / "usr/lib/gdk-pixbuf-2.0").rglob("loaders.cache"))
    if not loaders:
        raise ValueError("gdk-pixbuf loaders.cache missing from browser target tree")
    notes.append("gdk-pixbuf loaders.cache present: " +
                 str(loaders[0].relative_to(target)))
    return notes


def build(*, resume=False):
    pin = source_pin()
    if os.geteuid() == 0:
        raise ValueError("refusing privileged browser dependency build")
    tools, sysroot = ffi.target_tools()
    marker = ffi.TOOLCHAIN / "SYNVEIL-TOOLCHAIN"
    if "cxx=1" not in marker.read_text().splitlines():
        raise ValueError("native browser build needs the post-glibc C++ toolchain")
    cxx = ROOT / "out/native-cxx/validation.json"
    proof = json.loads(cxx.read_text())
    if proof.get("schema") != "synveil.native-cxx/v1" or proof.get("target") != ffi.TARGET:
        raise ValueError("missing native C++ runtime provenance")
    if (ROOT / "out").is_symlink() or OUT.is_symlink() or (OUT.exists() and not resume):
        raise ValueError("refusing existing or symlinked browser dependency output")
    if any(character.isspace() for character in str(ROOT)):
        raise ValueError("dependency build path cannot contain whitespace")
    context = {"recipe_commit": RECIPE_COMMIT,
               "netsurf": {"version": NETSURF_VERSION, "sha256": NETSURF_SHA256},
               "native_sources": {
                   "wayland_sha512": weston.wayland.release_spec()["sha512"],
                   "ffi_sha256": ffi.source_pin()["sha256"],
                   "pixman_sha512": weston.pixman.pin()["sha512"],
                   "protocols_sha512": weston.xdg.pin()["sha512"]},
               "native_cxx": proof, "toolchain_marker": marker.read_text()}
    source = OUT / "recipes"
    if OUT.exists():
        if not OUT.is_dir() or (OUT.stat().st_mode & 0o077):
            raise ValueError("cached browser output must be private")
        if json.loads((OUT / "build-context.json").read_text()) != context:
            raise ValueError("cached browser build does not match native source/toolchain pins")
        commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if commit != RECIPE_COMMIT or subprocess.check_output(
                ["git", "-C", str(source), "status", "--porcelain"], text=True).strip():
            raise ValueError("cached source recipes changed")
    else:
        OUT.mkdir(parents=True, mode=0o700)
        run(["git", "init", source])
        run(["git", "-C", source, "remote", "add", "origin", pin["recipe_builder"]["repository"]])
        run(["git", "-C", source, "fetch", "--depth", "1", "origin", "refs/tags/2026.08.1"])
        run(["git", "-C", source, "checkout", "--detach", "FETCH_HEAD"])
        commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if commit != RECIPE_COMMIT:
            raise ValueError("dependency recipe tag moved from reviewed commit")
        if NETSURF_SHA256 not in (source / "package/netsurf/netsurf.hash").read_text():
            raise ValueError("NetSurf release digest missing from pinned recipes")
        (OUT / "build-context.json").write_text(json.dumps(context, sort_keys=True) + "\n")
    # Reuse the Weston stage's verified source overrides (Wayland,
    # libffi, Pixman, protocols at the project's canonical pins) so
    # the two stages cannot drift apart on shared components.
    overrides, _native_sources = weston.pristine_overrides(cached=True)
    config = OUT / "browser.defconfig"
    config.write_text(configuration(ffi.TOOLCHAIN, overrides))
    build_dir = OUT / "build"
    base = ["make", "-C", str(source), "O=" + str(build_dir)]
    env = dict(os.environ)
    for key in ("CC", "CXX", "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS", "CPATH",
                "LIBRARY_PATH", "PKG_CONFIG_PATH", "PKG_CONFIG_LIBDIR", "PKG_CONFIG_SYSROOT_DIR"):
        env.pop(key, None)
    env["LC_ALL"] = "C"
    run(base + ["BR2_DEFCONFIG=" + str(config), "defconfig"], env=env)
    check_configuration((build_dir / ".config").read_text(), ffi.TOOLCHAIN)
    # Deliberately invoke the package only, never `all`,
    # `target-finalize`, or images.
    run(base + ["-j4", "netsurf"], env=env)
    fixups = target_finalize_fixups(build_dir)
    target = build_dir / "target"
    required = ("usr/bin/netsurf-gtk3",)
    hashes = {}
    for relative in required:
        path = target / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError("native browser component missing: " + relative)
        header = subprocess.check_output([str(tools["readelf"]), "-h", str(path)], text=True)
        program = subprocess.check_output([str(tools["readelf"]), "-l", str(path)], text=True)
        if "Advanced Micro Devices X86-64" not in header or "/lib64/ld-linux-x86-64.so.2" not in program:
            raise ValueError("non-native browser executable: " + relative)
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    libc_hashes = {}
    for name, original in (("libc.so.6", sysroot / "lib64/libc.so.6"),
                           ("ld-linux-x86-64.so.2", sysroot / "lib64/ld-linux-x86-64.so.2")):
        expected = hashlib.sha256(original.read_bytes()).hexdigest()
        candidates = list(target.rglob(name))
        if not candidates or any(
                not path.resolve().is_relative_to(target.resolve()) or
                hashlib.sha256(path.read_bytes()).hexdigest() != expected
                for path in candidates):
            raise ValueError("dependency builder did not preserve native glibc bytes: " + name)
        libc_hashes[name] = expected
    package_info = subprocess.check_output(base + ["-s", "show-info"], env=env)
    (OUT / "package-info.json").write_bytes(package_info)
    info = json.loads(package_info)
    components = {}
    for name in ("netsurf", "libgtk3", "libcurl", "libopenssl", "mesa3d",
                 "libepoxy", "libglib2", "pango", "gdk-pixbuf", "atk"):
        if name in info:
            components[name] = info[name].get("version")
    asset_hash = assets.seal(target, OUT / "runtime-assets.json")
    receipt = {"schema": "synveil.native-browser-stage/v1", "target": ffi.TARGET,
               "recipe_commit": commit,
               "netsurf_version": NETSURF_VERSION,
               "netsurf_source_sha256": NETSURF_SHA256,
               "components": components,
               "executables_sha256": hashes,
               "native_glibc_sha256": libc_hashes,
               "runtime_assets_sha256": asset_hash,
               "target_finalize_fixups": fixups,
               "mesa_role": "build-time EGL/GLES provider for the GTK3 "
                            "Wayland backend configuration; NetSurf "
                            "creates no GL context (Cairo software "
                            "rendering)",
               "tls": "libcurl + OpenSSL, verification on by default; "
                      "bundle path /etc/ssl/certs/ca-certificates.crt "
                      "(provisioned per image, never by this build)",
               "native_boot_image_changed": False, "browser_executed": False,
               "foreign_rootfs_imported": False}
    (OUT / "validation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("SYNVEIL_NATIVE_BROWSER_COMPONENTS_SOURCE_BUILT_NOT_BOOTED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--build", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    source_pin()
    if args.build:
        build(resume=args.resume)
    else:
        print("SYNVEIL_NATIVE_BROWSER_SOURCE_BUILD_PLAN_VERIFIED")
