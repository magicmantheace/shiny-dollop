#!/usr/bin/env python3
"""Extended-table (~1M star) measurement harness for S0.

NOT the shipping pipeline — a bounded scale measurement (Adam's §11
ruling: measure the ~1M-star table, don't guess). It reads the AT-HYG
v4.0 catalog (cache/athyg_40.csv.gz), selects the 1,000,000 nearest
stars with usable distances, and writes a stars.bin in the exact v1
format of pipeline/src/table.rs (no planets — AT-HYG has none) into
data/extended/, so the Godot viewer's --measure mode can time loading
it. Derived teff/mass use the same spectral anchors as derive.rs and
are flagged derived, same as the main pipeline.

Usage: python3 measure_extended.py [--count 1000000] [--out ../data/extended]
"""
import argparse
import csv
import gzip
import hashlib
import json
import math
import struct
import sys
import time

PC_TO_LY = 3.26156
# J2000 equatorial -> galactic rotation, identical to pipeline/src/astro.rs.
ROT = (
    (-0.0548755604, -0.8734370902, -0.4838350155),
    (+0.4941094279, -0.4448296300, +0.7469822445),
    (-0.8676661490, -0.1980763734, +0.4559837762),
)
SPECTRAL_CODE = {"O": 0, "B": 1, "A": 2, "F": 3, "G": 4, "K": 5, "M": 6}
TEFF_AT_SUBCLASS_0 = {0: 30000.0, 1: 15000.0, 2: 9000.0, 3: 6800.0, 4: 5800.0, 5: 4600.0, 6: 2900.0}
SOL_ABSMAG = 4.85
FLAG_NAMED, FLAG_TEMP_DERIVED, FLAG_MASS_DERIVED = 1, 16, 32


def parse_spectral(spect):
    """Return (code, teff) like derive.rs; teff 0.0 when unknown."""
    if not spect:
        return 8, 0.0
    s = spect.strip().lstrip("sd")
    if not s:
        return 8, 0.0
    letter = s[0].upper()
    if letter not in SPECTRAL_CODE:
        return 7, 0.0
    code = SPECTRAL_CODE[letter]
    sub = 0.0
    if len(s) > 1 and (s[1].isdigit()):
        sub = float(s[1])
        if len(s) > 2 and s[2] == "." and len(s) > 3 and s[3].isdigit():
            sub += float(s[3]) / 10.0
    t0 = TEFF_AT_SUBCLASS_0[code]
    if code < 6:
        t1 = TEFF_AT_SUBCLASS_0[code + 1]
    else:
        t1 = 2400.0
    teff = t0 + (t1 - t0) * (min(sub, 9.9) / 10.0)
    return code, teff


def display_name(row):
    if row["proper"]:
        return row["proper"], True
    bf = " ".join(p for p in (row["bayer"], row["flam"], row["con"]) if p).strip()
    if bf:
        return bf, False
    if row["gl"]:
        return row["gl"], False
    if row["hip"]:
        return "HIP " + row["hip"], False
    if row["hd"]:
        return "HD " + row["hd"], False
    return "AT-HYG " + row["id"], False


def f32_or_zero(text):
    try:
        v = float(text)
        return v if math.isfinite(v) else 0.0
    except (TypeError, ValueError):
        return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1_000_000)
    ap.add_argument("--cache", default="cache/athyg_40.csv.gz")
    ap.add_argument("--out", default="../data/extended")
    args = ap.parse_args()

    t_start = time.time()
    # Pass 1: distance distribution of usable rows.
    dists = []
    total = 0
    with gzip.open(args.cache, "rt", newline="") as fh:
        for row in csv.DictReader(fh):
            total += 1
            try:
                d = float(row["dist"])
            except (TypeError, ValueError):
                continue
            if 0.0 <= d < 100000.0 and math.isfinite(d):
                dists.append(d)
    usable = len(dists)
    dists.sort()
    take = min(args.count, usable)
    threshold = dists[take - 1]
    print(f"AT-HYG rows: {total}; usable distances: {usable}")
    print(f"selecting {take} nearest; distance cutoff: {threshold:.2f} pc")

    # Pass 2: collect the selected rows.
    chosen = []
    with gzip.open(args.cache, "rt", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                d = float(row["dist"])
            except (TypeError, ValueError):
                continue
            if 0.0 <= d <= threshold and math.isfinite(d):
                chosen.append((d, row))
    chosen.sort(key=lambda t: t[0])
    chosen = chosen[:take]

    strings = bytearray()
    string_offsets = []
    records = []
    for idx, (_d, row) in enumerate(chosen):
        name, named = display_name(row)
        string_offsets.append(len(strings))
        strings += name.encode("utf-8") + b"\0"
        x_pc, y_pc, z_pc = (f32_or_zero(row["x0"]), f32_or_zero(row["y0"]), f32_or_zero(row["z0"]))
        gx = (ROT[0][0] * x_pc + ROT[0][1] * y_pc + ROT[0][2] * z_pc) * PC_TO_LY
        gy = (ROT[1][0] * x_pc + ROT[1][1] * y_pc + ROT[1][2] * z_pc) * PC_TO_LY
        gz = (ROT[2][0] * x_pc + ROT[2][1] * y_pc + ROT[2][2] * z_pc) * PC_TO_LY
        absmag = f32_or_zero(row["absmag"])
        ci = f32_or_zero(row["ci"])
        code, teff = parse_spectral(row["spect"])
        flags = 0
        if named:
            flags |= FLAG_NAMED
        if teff > 0.0:
            flags |= FLAG_TEMP_DERIVED
        mass = 0.0
        if absmag != 0.0:
            lum = 10.0 ** (0.4 * (SOL_ABSMAG - absmag))
            mass = lum ** (1.0 / 3.5)
            flags |= FLAG_MASS_DERIVED
        records.append((idx, gx, gy, gz, absmag, ci, teff, mass, code, flags))

    n = len(records)
    stars_offset = 64
    planets_offset = stars_offset + 48 * n
    strings_offset = planets_offset + 4
    out = bytearray()
    out += b"MWST"
    out += struct.pack("<IIIQQQ", 1, n, 0, stars_offset, planets_offset, strings_offset)
    out += struct.pack("<Q", len(strings))
    out += b"\0" * 16
    assert len(out) == 64
    for (idx, gx, gy, gz, absmag, ci, teff, mass, code, flags), name_off in zip(records, string_offsets):
        out += struct.pack("<I", idx)
        out += struct.pack("<fff", gx, gy, gz)
        out += struct.pack("<ffff", absmag, ci, teff, mass)
        out += struct.pack("<BB", code, flags)
        out += b"\0\0"
        out += struct.pack("<II", 0, name_off)
        out += b"\0\0\0\0"
    out += struct.pack("<I", 0)  # planets section: reserved u32 only
    out += strings

    import os
    os.makedirs(args.out, exist_ok=True)
    bin_path = os.path.join(args.out, "stars.bin")
    with open(bin_path, "wb") as fh:
        fh.write(out)
    sha = hashlib.sha256(bytes(out)).hexdigest()
    elapsed = time.time() - t_start
    manifest = {
        "format": "mwcs-stars",
        "format_version": 1,
        "note": "EXTENDED measurement table (AT-HYG v4.0 nearest 1M) — not the shipping table",
        "source": "AT-HYG v4.0 (data/athyg_40.csv.gz, Codeberg astronexus/athyg), CC BY-SA 4.0",
        "athyg_rows_total": total,
        "athyg_usable_distances": usable,
        "distance_cutoff_pc": round(threshold, 2),
        "table": {"file": "stars.bin", "bytes": len(out), "stars": n, "planets": 0, "sha256": sha},
        "build_seconds": round(elapsed, 1),
    }
    with open(os.path.join(args.out, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"extended table: {n} stars, {len(out)} bytes, sha256 {sha[:16]}…")
    print(f"build time (2 passes over 488 MB CSV + write): {elapsed:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
