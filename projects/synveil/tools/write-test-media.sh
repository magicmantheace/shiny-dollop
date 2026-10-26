#!/usr/bin/env bash
# SPDX-License-Identifier: MPL-2.0
# Guarded writer for Synveil TEST media (owner first-boot test).
#
# Writes a checksummed Synveil test image to ONE removable USB disk
# after verifying: the image digest equals the digest the operator
# supplies from the committed validation record, the target is a
# whole removable/USB disk (never a partition, never an internal
# disk), nothing on it is mounted, and it does not host the running
# system. The operator must confirm the exact target device name
# after being shown its model, serial and size. After writing, the
# image bytes are read back and their digest compared.
#
# This is a test-media writer, not an installer: it copies a
# prebuilt image byte for byte and creates no partitions itself.
set -Eeuo pipefail

usage() {
    cat >&2 <<'EOF'
usage: write-test-media.sh --image IMAGE --device /dev/WHOLE_DISK \
       --expected-sha256 HEX64

  --image           regular file (not a symlink) with the test image
  --device          whole-disk device, e.g. /dev/sdb (no partitions)
  --expected-sha256 SHA-256 of the image from the validation record
EOF
    exit 2
}

IMAGE='' DEVICE='' EXPECTED=''
while [[ $# -gt 0 ]]; do
    case "$1" in
        --image) IMAGE=${2:-}; shift 2 ;;
        --device) DEVICE=${2:-}; shift 2 ;;
        --expected-sha256) EXPECTED=${2:-}; shift 2 ;;
        *) usage ;;
    esac
done
[[ -n "$IMAGE" && -n "$DEVICE" && -n "$EXPECTED" ]] || usage
[[ "$EXPECTED" =~ ^[0-9a-f]{64}$ ]] || {
    echo "ERROR: --expected-sha256 must be 64 lowercase hex characters" >&2
    exit 2
}
[[ $EUID -eq 0 ]] || {
    echo "ERROR: run as root (sudo) — raw device writes require it" >&2
    exit 2
}
for cmd in sha256sum blockdev dd findmnt stat readlink; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "ERROR: required command not found: $cmd" >&2; exit 2; }
done

# --- image identity -------------------------------------------------
[[ -f "$IMAGE" && ! -L "$IMAGE" ]] || {
    echo "ERROR: image must be a regular, non-symlink file: $IMAGE" >&2
    exit 1
}
IMAGE_SIZE=$(stat -c '%s' "$IMAGE")
IMAGE_SHA=$(sha256sum "$IMAGE" | awk '{print $1}')
if [[ "$IMAGE_SHA" != "$EXPECTED" ]]; then
    echo "ERROR: image digest mismatch — refusing to write." >&2
    echo "  expected (validation record): $EXPECTED" >&2
    echo "  actual file:                  $IMAGE_SHA" >&2
    exit 1
fi
echo "Image:  $IMAGE"
echo "  size:   $IMAGE_SIZE bytes"
echo "  sha256: $IMAGE_SHA  (matches the validation record)"

# --- device identity ------------------------------------------------
[[ "$DEVICE" =~ ^/dev/(sd[a-z]+|nvme[0-9]+n[0-9]+|mmcblk[0-9]+)$ ]] || {
    echo "ERROR: device must be a whole disk (no partition suffix): $DEVICE" >&2
    exit 1
}
[[ -b "$DEVICE" ]] || {
    echo "ERROR: not a block device: $DEVICE" >&2; exit 1
}
BASE=${DEVICE#/dev/}
SYS=/sys/block/$BASE
[[ -d "$SYS" ]] || { echo "ERROR: no sysfs entry for $BASE" >&2; exit 1; }

REMOVABLE=$(cat "$SYS/removable" 2>/dev/null || echo '?')
DEVPATH=$(readlink -f "$SYS/device" 2>/dev/null || echo '')
TRANSPORT=$(cat "$SYS/device/transport" 2>/dev/null || echo '')
if [[ "$REMOVABLE" != 1 && "$DEVPATH" != *'/usb'* && "$TRANSPORT" != *usb* ]]; then
    echo "ERROR: $DEVICE is not removable and not USB-attached — refusing." >&2
    echo "  removable=$REMOVABLE transport=$TRANSPORT path=$DEVPATH" >&2
    exit 1
fi

DEV_SIZE=$(blockdev --getsize64 "$DEVICE")
[[ "$DEV_SIZE" -ge "$IMAGE_SIZE" ]] || {
    echo "ERROR: device ($DEV_SIZE bytes) is smaller than the image" \
         "($IMAGE_SIZE bytes)" >&2; exit 1
}

# Nothing on the target may be mounted, and it must not host the
# running system's root, boot or swap.
MOUNTED=$( { grep -E "^$DEVICE" /proc/mounts || true; } )
SWAP=$( { grep -E "^$DEVICE" /proc/swaps || true; } )
ROOTSRC=$(findmnt -no SOURCE / 2>/dev/null || echo '')
BOOTSRC=$(findmnt -no SOURCE /boot 2>/dev/null || echo '')
if [[ -n "$MOUNTED" || -n "$SWAP" ||
      "$ROOTSRC" == "$DEVICE"* || "$BOOTSRC" == "$DEVICE"* ]]; then
    echo "ERROR: $DEVICE is in use by the running system — refusing." >&2
    [[ -n "$MOUNTED" ]] && echo "  mounted: $MOUNTED" >&2
    [[ -n "$SWAP" ]] && echo "  swap: $SWAP" >&2
    echo "  root source: $ROOTSRC  boot source: $BOOTSRC" >&2
    exit 1
fi

MODEL=$(cat "$SYS/device/model" 2>/dev/null || echo '(unknown)')
VENDOR=$(cat "$SYS/device/vendor" 2>/dev/null || echo '(unknown)')
SERIAL=$(cat "$SYS/device/serial" 2>/dev/null || echo '(unknown)')
echo
echo "Target device: $DEVICE"
echo "  model:  $VENDOR $MODEL"
echo "  serial: $SERIAL"
echo "  size:   $DEV_SIZE bytes (image uses $IMAGE_SIZE)"
echo "  removable=$REMOVABLE transport=${TRANSPORT:-n/a}"
echo
echo "ALL DATA ON $DEVICE WILL BE DESTROYED."
printf 'Type the device name (%s) to confirm: ' "$BASE"
read -r CONFIRM
[[ "$CONFIRM" == "$BASE" ]] || {
    echo "Confirmation did not match — nothing written." >&2; exit 1
}

# --- write + verify ---------------------------------------------------
echo "Writing image…"
dd if="$IMAGE" of="$DEVICE" bs=4M conv=fsync status=progress
sync
echo "Reading back $IMAGE_SIZE bytes for verification…"
READBACK_SHA=$(dd if="$DEVICE" iflag=count_bytes count="$IMAGE_SIZE" \
    bs=4M status=none | sha256sum | awk '{print $1}')
if [[ "$READBACK_SHA" != "$EXPECTED" ]]; then
    echo "ERROR: read-back digest mismatch — media is NOT trustworthy." >&2
    echo "  expected: $EXPECTED" >&2
    echo "  readback: $READBACK_SHA" >&2
    exit 1
fi
sync
echo
echo "SYNVEIL_TEST_MEDIA_WRITTEN device=$DEVICE sha256=$READBACK_SHA"
echo "The media is verified. Eject it before unplugging."
