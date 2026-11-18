"""Command line: the arguments the bar's launcher and desktop files use."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyprtk_term.__main__ import _parse  # noqa: E402


class Parse(unittest.TestCase):
    def test_no_arguments(self):
        self.assertEqual(_parse(["hyprtk-term"]), ([], None))

    def test_exec_takes_the_rest(self):
        self.assertEqual(_parse(["hyprtk-term", "-e", "htop"]), (["htop"], None))
        self.assertEqual(
            _parse(["hyprtk-term", "-e", "sh", "-c", "echo hi"]),
            (["sh", "-c", "echo hi"], None))

    def test_exec_long_form(self):
        self.assertEqual(_parse(["t", "--exec", "btop", "-d"]), (["btop", "-d"], None))

    def test_double_dash_is_exec(self):
        self.assertEqual(_parse(["t", "--", "nvim", "notes.md"]), (["nvim", "notes.md"], None))

    def test_directory_forms(self):
        self.assertEqual(_parse(["t", "-d", "/tmp"]), ([], "/tmp"))
        self.assertEqual(_parse(["t", "--directory", "~/x"]), ([], os.path.expanduser("~/x")))
        self.assertEqual(_parse(["t", "--working-directory=/var"]), ([], "/var"))

    def test_qt_flags_are_not_swallowed(self):
        # Qt's own -name flag must reach Qt; only -e/-d are ours.
        self.assertEqual(_parse(["t", "-name", "hyprtk-term"]), ([], None))

    def test_exec_wins_over_directory(self):
        self.assertEqual(_parse(["t", "-d", "/tmp", "-e", "htop"]), (["htop"], "/tmp"))


if __name__ == "__main__":
    unittest.main()
