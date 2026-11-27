"""Every TerminalView method the QML calls must be a ``@Slot``.

QML resolves calls through the meta-object. A plain Python method is not in
it, so ``view.paste()`` from QML raises "Property 'paste' ... is not a
function" and nothing happens -- which is how copy, paste, select all, zoom,
close tab and clear-scrollback were all silently dead while the Python side
tested green.
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMetaMethod, QObject  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402

from hyprtk_term import view as view_mod  # noqa: E402

# Qt's own API on the type (``view.destroy()`` in closeTab is QObject's).
INHERITED = set(dir(QObject)) | set(dir(QQuickItem))
# C++ meta-object slots that PySide does not expose as Python attributes.
QT_ONLY = {"destroy"}

QML_DIR = Path(view_mod.__file__).resolve().parent / "qml"

# ``view.copy()``, ``views[id].applySettings(...)``, ``win.activeView().paste()``
CALLS = (
    re.compile(r"(?<![\w.])view\.([A-Za-z_]\w*)\("),
    re.compile(r"views\[[^\]]+\]\.([A-Za-z_]\w*)\("),
    re.compile(r"activeView\(\)\.([A-Za-z_]\w*)\("),
)


def qml_calls() -> set[str]:
    names: set[str] = set()
    for path in sorted(QML_DIR.rglob("*.qml")):
        text = path.read_text(encoding="utf-8")
        for pattern in CALLS:
            names.update(pattern.findall(text))
    return names


class QmlBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.pane = view_mod.TerminalView()

    def test_qml_calls_are_slots(self) -> None:
        methods = {}
        meta = self.pane.metaObject()
        for index in range(meta.methodCount()):
            method = meta.method(index)
            methods[bytes(method.name()).decode()] = method.methodType()

        calls = {name for name in qml_calls() if name not in INHERITED and name not in QT_ONLY}
        self.assertTrue(calls, "the QML scan found no view calls at all")

        missing = sorted(n for n in calls if n not in methods)
        self.assertEqual(missing, [], f"called from QML but not a slot: {missing}")

        not_slot = sorted(n for n in calls if methods.get(n) != QMetaMethod.MethodType.Slot)
        self.assertEqual(not_slot, [], f"not exposed as a slot: {not_slot}")

    def test_the_scan_sees_the_known_api(self) -> None:
        # Guards the regexes: if the QML is refactored these still must be found.
        calls = qml_calls()
        for name in ("copy", "paste", "selectAll", "clearScrollback", "zoom", "kill"):
            self.assertIn(name, calls)


if __name__ == "__main__":
    unittest.main()
