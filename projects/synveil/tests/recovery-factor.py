#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Host-side contract tests for the ADR 0010 tier 4 recovery factor.

These tests pin the shape of the implementation: the reset branch
in init (after the state mount, before maintenance/core/seat/
network, console locked unconditionally), the kernel flag plumbing,
the reset/rotation surface of veil-recovery, the interactive-only
enrollment tool, the record/anchor constants in the recovery
library, the A/B proof build's reset UKI, and the owner's approval
record. Guest behavior is covered by tests/smoke-recovery-factor.py
and tests/smoke-recovery-factor-ab.py.
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InitContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.init = (ROOT / "build/rootfs/init").read_text()

    def block(self):
        return self.init.split("# BEGIN PASSWORD_RESET", 1)[1].split(
            "# END PASSWORD_RESET", 1)[0]

    def test_init_parses_as_shell(self):
        subprocess.run(["sh", "-n", str(ROOT / "build/rootfs/init")],
                       check=True)

    def test_reset_branch_shape(self):
        block = self.block()
        self.assertIn("grep -qw 'synveil.recovery=reset' /proc/cmdline", block)
        self.assertIn("/usr/sbin/veil-recovery", block)
        self.assertIn("SYNVEIL_RECOVERY_RESET_UNAVAILABLE", block)
        self.assertIn("serial_lock_forever", block)

    def test_reset_branch_order(self):
        # After the state mount (verifier + anchor need it), before
        # the tier-2 maintenance branch and anything later.
        mount = self.init.index("/usr/libexec/synveil/mount-state")
        reset = self.init.index("# BEGIN PASSWORD_RESET")
        maint = self.init.index("# BEGIN AUTHENTICATED_MAINTENANCE")
        self.assertLess(mount, reset)
        self.assertLess(reset, maint)


class KernelContract(unittest.TestCase):
    def test_kernel_flag(self):
        script = (ROOT / "build/scripts/kernel.sh").read_text()
        self.assertIn("SYNVEIL_KERNEL_TEST_RECOVERY_RESET", script)
        self.assertIn("synveil.recovery=reset", script)


class RecoveryProgramContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "src/veil-core/src/bin/veil-recovery.rs").read_text()

    def test_reset_and_rotation_surface(self):
        for marker in (
            "SYNVEIL_RECOVERY_RESET_V1",
            "SYNVEIL_RECOVERY_RESET_VERIFIED",
            "SYNVEIL_RECOVERY_RESET_OK",
            "SYNVEIL_RECOVERY_RESET_DENIED",
            "SYNVEIL_RECOVERY_RESET_TRANSCRIPTION",
            "SYNVEIL_RECOVERY_ROTATE_OK",
            "SYNVEIL_RECOVERY_MAINT_FACTOR state=",
            '"rotate"',
        ):
            self.assertIn(marker, self.source)

    def test_only_subprocess_is_stty(self):
        commands = re.findall(r'Command::new\("([^"]+)"\)', self.source)
        self.assertEqual(set(commands), {"/bin/stty"})


class EnrollProgramContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            ROOT / "src/veil-core/src/bin/veil-recovery-enroll.rs").read_text()

    def test_interactive_only_enrollment(self):
        self.assertIn("is_terminal", self.source)
        self.assertIn("SYNVEIL_RECOVERY_ENROLL_OK", self.source)
        self.assertIn("SYNVEIL_RECOVERY_ENROLL_DECLINED", self.source)
        self.assertIn("SYNVEIL_RECOVERY_FACTOR_NOT_ENROLLED", self.source)
        self.assertIn("SYNVEIL_RECOVERY_FACTOR_DISPLAY_BEGIN", self.source)

    def test_local_print_only(self):
        self.assertIn("/dev/lp0", self.source)
        self.assertNotIn("lpadmin", self.source)
        self.assertNotIn("cups", self.source.lower())

    def test_only_subprocess_is_stty(self):
        commands = re.findall(r'Command::new\("([^"]+)"\)', self.source)
        self.assertEqual(set(commands), {"/bin/stty"})


class LibraryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "src/veil-core/src/recovery.rs").read_text()

    def test_record_anchor_and_binding_constants(self):
        for needle in (
            "synveil.recovery-record/v1",
            "synveil.installation-anchor/v1",
            "/var/lib/synveil/auth/recovery.json",
            "/var/lib/synveil/installation-anchor.json",
            "synveil-recovery-v1",
            "MAX_FAILED_ATTEMPTS",
        ):
            self.assertIn(needle, self.source)

    def test_no_network_anywhere_in_factor_code(self):
        for path in (
            "src/veil-core/src/recovery.rs",
            "src/veil-core/src/bin/veil-recovery.rs",
            "src/veil-core/src/bin/veil-recovery-enroll.rs",
        ):
            source = (ROOT / path).read_text()
            self.assertNotIn("TcpStream", source, path)
            self.assertNotIn("UdpSocket", source, path)


class ProofBuildContract(unittest.TestCase):
    def test_reset_uki_in_ab_build(self):
        source = (ROOT / "tools/native_ab.py").read_text()
        self.assertIn('"EFI/synveil/reset.efi"', source)
        self.assertIn("SYNVEIL_KERNEL_TEST_RECOVERY_RESET", source)
        self.assertIn('"reset": reset', source)

    def test_enroll_binary_in_build_and_packaging(self):
        for path in ("tools/native_build.py", "tools/package_native.py"):
            self.assertIn("veil-recovery-enroll", (ROOT / path).read_text())


class ApprovalContract(unittest.TestCase):
    def test_spec_status_header(self):
        lines = (ROOT / "docs/RECOVERY_FACTOR_SPEC.md").read_text().splitlines()
        self.assertIn("APPROVED BY OWNER 2026-10-27", "\n".join(lines[:12]))

    def test_approval_record_covers_all_decisions(self):
        record = (ROOT / "docs/adr/0020-recovery-factor-design-approval.md")
        text = record.read_text()
        self.assertIn("Option A", text)
        for decision in ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8",
                         "D9", "D10"):
            self.assertIn(f"**{decision} —", text)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]], verbosity=2)
