"""Settings: defaults, coercion, clamping, atomic save."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyprtk_term import settings  # noqa: E402


class RoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "config.json")
        self._old = os.environ.get("HYPRTK_TERM_CONFIG")
        os.environ["HYPRTK_TERM_CONFIG"] = self.path

    def tearDown(self):
        if self._old is None:
            os.environ.pop("HYPRTK_TERM_CONFIG", None)
        else:
            os.environ["HYPRTK_TERM_CONFIG"] = self._old
        self.tmp.cleanup()

    def test_defaults_when_missing(self):
        cfg = settings.Settings.load()
        self.assertEqual(cfg.font_family, "JetBrainsMono Nerd Font Mono")
        self.assertGreater(cfg.font_size, 0)
        self.assertTrue(cfg.login_shell)

    def test_save_and_load(self):
        cfg = settings.Settings()
        cfg.font_size = 13.5
        cfg.scrollback = 4000
        cfg.save()
        again = settings.Settings.load()
        self.assertEqual(again.font_size, 13.5)
        self.assertEqual(again.scrollback, 4000)

    def test_saved_file_is_json_and_atomic(self):
        cfg = settings.Settings()
        cfg.save()
        with open(self.path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIn("font_family", data)
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_unknown_keys_are_ignored(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({"font_size": 12, "nonsense": True}, fh)
        cfg = settings.Settings.load()
        self.assertEqual(cfg.font_size, 12)
        self.assertFalse(hasattr(cfg, "nonsense"))

    def test_wrong_types_fall_back(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({"font_size": "big", "opacity": "no", "cursor_blink": 0}, fh)
        cfg = settings.Settings.load()
        self.assertEqual(cfg.font_size, settings.Settings().font_size)
        self.assertEqual(cfg.opacity, settings.Settings().opacity)
        self.assertFalse(cfg.cursor_blink)

    def test_broken_json_is_ignored(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        cfg = settings.Settings.load()
        self.assertEqual(cfg.font_family, settings.Settings().font_family)

    def test_update_from_a_dict(self):
        cfg = settings.Settings()
        cfg.update({"font_family": "FiraCode Nerd Font", "scrollback": 1234})
        self.assertEqual(cfg.font_family, "FiraCode Nerd Font")
        self.assertEqual(cfg.scrollback, 1234)

    def test_as_dict_covers_every_field(self):
        cfg = settings.Settings()
        data = cfg.as_dict()
        self.assertIn("cursor_shape", data)
        self.assertIn("bell", data)


class Clamps(unittest.TestCase):
    def test_font_size(self):
        self.assertEqual(settings.clamp_font_size(0), 4.0)
        self.assertEqual(settings.clamp_font_size(200), 72.0)

    def test_opacity(self):
        self.assertEqual(settings.clamp_opacity(0.0), 0.35)
        self.assertEqual(settings.clamp_opacity(4.0), 1.0)

    def test_scrollback(self):
        self.assertEqual(settings.clamp_scrollback(-5), 0)
        self.assertEqual(settings.clamp_scrollback(10 ** 9), 200_000)

    def test_negative_scrollback_is_allowed_but_clamped_by_the_bridge(self):
        self.assertEqual(settings.clamp_scrollback(-1), 0)


if __name__ == "__main__":
    unittest.main()
