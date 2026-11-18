"""Palette resolution: pywal precedence, fallbacks, colour conversion."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyprtk_term import palette  # noqa: E402


class HexToInt(unittest.TestCase):
    def test_six_digits(self):
        self.assertEqual(palette.hex_to_int("#02dede"), 0x02DEDE)

    def test_three_digits(self):
        self.assertEqual(palette.hex_to_int("#f0a"), 0xFF00AA)

    def test_eight_digits_drops_alpha(self):
        self.assertEqual(palette.hex_to_int("#02DEDE80"), 0x02DEDE)

    def test_bad_input_returns_the_fallback(self):
        self.assertEqual(palette.hex_to_int("nope", 0x123456), 0x123456)
        self.assertEqual(palette.hex_to_int(None, 0x123456), 0x123456)
        self.assertEqual(palette.hex_to_int("#zzzzzz", 0x123456), 0x123456)

    def test_accepts_a_qcolor(self):
        class Fake:
            def red(self): return 0xAB
            def green(self): return 0xCD
            def blue(self): return 0xEF
        self.assertEqual(palette.hex_to_int(Fake()), 0xABCDEF)


class Resolve(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("HYPRTK_WAL_HOME")
        os.environ["HYPRTK_WAL_HOME"] = self.tmp.name
        os.makedirs(os.path.join(self.tmp.name, ".cache", "wal"))

    def tearDown(self):
        if self._old is None:
            os.environ.pop("HYPRTK_WAL_HOME", None)
        else:
            os.environ["HYPRTK_WAL_HOME"] = self._old
        self.tmp.cleanup()

    def test_without_pywal_the_stock_palette_is_used(self):
        p = palette.resolve()
        self.assertEqual(p["ansi"], palette.ANSI_FALLBACK)
        self.assertTrue(p["background"].startswith("#"))
        self.assertIn("accent", p)

    def test_pywal_colours_are_used_when_present(self):
        colors = {f"color{i}": f"#01010{i:x}" for i in range(16)}
        special = {"background": "#101010", "foreground": "#f0f0f0"}
        with open(os.path.join(self.tmp.name, ".cache", "wal", "colors.json"), "w") as fh:
            json.dump({"colors": colors, "special": special}, fh)
        p = palette.resolve()
        self.assertEqual(p["background"], "#101010")
        self.assertEqual(p["foreground"], "#f0f0f0")
        self.assertEqual(p["ansi"][1], "#010101")
        self.assertEqual(p["accent"], "#010105")

    def test_missing_ansi_slots_fall_back_individually(self):
        with open(os.path.join(self.tmp.name, ".cache", "wal", "colors.json"), "w") as fh:
            json.dump({"colors": {"color1": "#aabbcc"}}, fh)
        p = palette.resolve()
        self.assertEqual(p["ansi"][1], "#aabbcc")
        self.assertEqual(p["ansi"][0], palette.ANSI_FALLBACK[0])

    def test_roles_are_filled(self):
        p = palette.resolve()
        for key in ("cursor", "selection", "search", "surface", "border", "muted"):
            self.assertIn(key, p)
        self.assertEqual(len(p["ansi"]), 16)


if __name__ == "__main__":
    unittest.main()
