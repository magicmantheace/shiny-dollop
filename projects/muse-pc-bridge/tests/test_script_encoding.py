"""Shipped Windows scripts must be pure ASCII bytes.

Windows PowerShell 5.1 reads a BOM-less .ps1 file as ANSI. A UTF-8
em dash in a comment or string then decodes to bytes that include a
stray double-quote, which breaks string quoting and cascades into
"Missing closing '}'" / "string is missing the terminator" parse
errors across the whole file -- the bridge-core.ps1 install script
failed exactly this way on the owner's PC (2026-11-08). cmd.exe has
the same class of problem with non-ASCII bytes in .cmd files.

No PowerShell parser runs in this suite, so the enforceable rule is
byte-level: every shipped .ps1/.cmd file is ASCII-only. If a script
genuinely needs a non-ASCII character, it must be saved with a BOM
and this test revisited deliberately -- not bypassed silently.
"""

from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_SUFFIXES = {".ps1", ".cmd"}


def shipped_scripts() -> list[Path]:
    return sorted(
        p
        for p in PROJECT_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in SCRIPT_SUFFIXES
    )


class ScriptEncodingTestCase(unittest.TestCase):
    def test_scripts_exist(self):
        scripts = shipped_scripts()
        self.assertTrue(scripts, "no .ps1/.cmd files found -- scan is broken")
        names = {p.name for p in scripts}
        self.assertIn("bridge-core.ps1", names)
        self.assertIn("bridge-service.ps1", names)

    def test_all_scripts_are_ascii_only(self):
        offenders = []
        for path in shipped_scripts():
            data = path.read_bytes()
            bad = sorted({b for b in data if b > 127})
            if bad:
                offenders.append(
                    f"{path.relative_to(PROJECT_DIR)}: "
                    f"non-ASCII byte(s) {[hex(b) for b in bad]}"
                )
        self.assertEqual(
            offenders,
            [],
            "Windows scripts must be pure ASCII (PowerShell 5.1 reads "
            "BOM-less files as ANSI): " + "; ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
