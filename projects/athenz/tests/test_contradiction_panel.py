"""Headless safety of the Tk contradiction adjudication input boundary."""
import unittest
from unittest.mock import Mock, patch

from athenz.contradiction_panel import (
    checked_adjudication, mount_contradiction_review_button)
from athenz.contradiction_review import ContradictionReviewError


class ContradictionPanelTests(unittest.TestCase):
    def test_action_mapping_is_explicit(self):
        self.assertEqual(checked_adjudication('keep-a', ''),
                         {'action': 'confirm', 'resolution': 'keep-a', 'note': ''})
        self.assertEqual(checked_adjudication('keep-b', ' x '),
                         {'action': 'confirm', 'resolution': 'keep-b', 'note': 'x'})
        self.assertEqual(checked_adjudication('keep-both', ''),
                         {'action': 'confirm', 'resolution': 'keep-both', 'note': ''})
        self.assertEqual(checked_adjudication('dismiss', ''),
                         {'action': 'dismiss', 'resolution': None, 'note': ''})
        self.assertEqual(checked_adjudication('defer', ''),
                         {'action': 'defer', 'resolution': None, 'note': ''})

    def test_unknown_action_and_oversized_note_are_refused(self):
        for action in ('', 'approve', 'reject', 'model-decided', 'keep'):
            with self.assertRaises(ContradictionReviewError):
                checked_adjudication(action, '')
        with self.assertRaises(ContradictionReviewError):
            checked_adjudication('defer', 'x' * 1001)
        with self.assertRaises(ContradictionReviewError):
            checked_adjudication('defer', None)

    def test_native_button_only_opens_on_user_action(self):
        try:
            import tkinter as tk
            from tkinter import ttk
            window = tk.Tk()
        except Exception as exc:  # ImportError or TclError when headless
            self.skipTest(f'No graphical Tk session: {type(exc).__name__}')
        try:
            toolbar = ttk.Frame(window)
            toolbar.pack()
            service = Mock()
            service.contradiction_candidates.side_effect = AssertionError(
                'automatic scan at mount')
            button = mount_contradiction_review_button(
                toolbar, window, service, lambda message: None, lambda: None)
            self.assertEqual(button.cget('text'), 'Review contradictions…')
            window.update_idletasks()
            service.contradiction_candidates.assert_not_called()
        finally:
            window.destroy()

    def test_import_only_does_not_scan_or_launch_window(self):
        with patch('athenz.contradiction_review.ContradictionStore.scan',
                   side_effect=AssertionError('scan')):
            self.assertTrue(callable(mount_contradiction_review_button))
            self.assertTrue(callable(checked_adjudication))


if __name__ == '__main__':
    unittest.main()
