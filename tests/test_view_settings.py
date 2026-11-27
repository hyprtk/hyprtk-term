"""The QML boundary on the terminal view: settings arrive as QJSValue.

``applySettings`` is called from QML with ``Bridge.config`` and
``Bridge.palette``. A JS object reaches a ``QVariant`` slot as an opaque
``QJSValue`` (PySide6 6.12 does this for every container), so without an
explicit unwrap ``dict(cfg)`` raises and every launch silently runs on the
dataclass defaults: the user's font size, opacity and scrollback ignored.
"""

from __future__ import annotations

import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QJSEngine  # noqa: E402

from hyprtk_term import view as view_mod  # noqa: E402


class ApplySettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.js = QJSEngine()

    def setUp(self) -> None:
        # The view loads ~/.config/hyprtk-term/config.json; never the developer's.
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["HYPRTK_TERM_CONFIG"] = os.path.join(self.tmp.name, "config.json")

    def tearDown(self) -> None:
        os.environ.pop("HYPRTK_TERM_CONFIG", None)
        self.tmp.cleanup()

    def test_qjsvalue_config_and_palette_are_applied(self) -> None:
        pane = view_mod.TerminalView()
        pane.applySettings(
            self.js.evaluate("({ font_size: 20, opacity: 0.4, scrollback: 1234 })"),
            self.js.evaluate("({ background: '#101010', foreground: '#eeeeee' })"),
        )
        self.assertAlmostEqual(pane._font_size, 20.0)
        self.assertAlmostEqual(pane._opacity, 0.4)
        self.assertEqual(pane._cfg.scrollback, 1234)
        self.assertEqual(pane._colors.get("background"), "#101010")

    def test_plain_dicts_still_work(self) -> None:
        pane = view_mod.TerminalView()
        pane.applySettings({"font_size": 15.5}, {"background": "#202020"})
        self.assertAlmostEqual(pane._font_size, 15.5)
        self.assertEqual(pane._colors.get("background"), "#202020")


if __name__ == "__main__":
    unittest.main()
