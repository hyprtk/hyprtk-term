#!/usr/bin/env python3
"""Dev-only: load the QML tree headlessly, drive it, and fail on warnings.

The point is not to re-test the VT (that is tests/test_vt.py) but to catch the
things only a real QML load finds: a renamed property, a missing slot, a
binding loop, a type that no longer registers.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

# Keep the gate hermetic: the app reads settings and the pywal palette from the
# user's real home, which would make the result depend on the wallpaper.
_SANDBOX = tempfile.mkdtemp(prefix="hyprtk-term-boot-")
for _var in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"):
    os.environ[_var] = os.path.join(_SANDBOX, _var.split("_")[1].lower())
os.environ["HYPRTK_WAL_HOME"] = _SANDBOX
os.environ["HYPRTK_TERM_CONFIG"] = os.path.join(_SANDBOX, "config.json")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Q_ARG, QMetaObject, QPoint, QPointF, QTimer, Qt, qInstallMessageHandler  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from hyprtk_term import __version__  # noqa: E402
from hyprtk_term.app import create  # noqa: E402
from hyprtk_term.terminal import Terminal  # noqa: E402
from hyprtk_term.view import TerminalView  # noqa: E402

SCRIPT = "printf 'BOOTCHECK-OK\\n'; stty size; seq 1 80"
problems: list[str] = []

# Resizes the shell is told about, in order. The window is laid out more than
# once before it settles, and a resize that lands while the shell draws its
# first prompt leaves zsh filling its partial-line marker with more spaces than
# the grid holds -- the stray '%' above the prompt. The shell must therefore be
# spawned into the settled grid, so this must stay empty through startup.
resizes: list[tuple[int, int]] = []
_resize = Terminal.resize


def counting_resize(self, rows, cols):
    changed = _resize(self, rows, cols)
    if changed:
        resizes.append((rows, cols))
    return changed


Terminal.resize = counting_resize


finished = False


def handler(_mode, _ctx, message) -> None:
    # Teardown (root context cleared before the window) logs a couple of
    # "Cannot read property 'palette' of null" lines; they are not the app.
    if finished or not message.strip():
        return
    problems.append(message)
    print(message)


def type_text(window, text: str) -> None:
    for ch in text:
        QTest.keyClick(window, Qt.Key_Space if ch == " " else ord(ch), Qt.NoModifier)
    QTest.keyClick(window, Qt.Key_Return)


def tab_items(root) -> list:
    """The tab-strip delegates (children of the Repeater, not of the Row)."""
    for item in root.findChildren(QQuickItem):
        if item.metaObject().className() != "QQuickRow":
            continue
        kids = [k for k in item.childItems() if k.objectName() == "tabButton"]
        if kids:
            return kids
    return []


def click_item(window, item) -> None:
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                     QPoint(int(point.x()), int(point.y())))


def screen_text(view: TerminalView) -> str:
    vt = view.terminal.vt
    rows = ["".join(cell for cell in vt.line_cells(r)).rstrip() for r in range(vt.rows)]
    return "\n".join(rows)


def pty_size(view: TerminalView) -> tuple[int, int]:
    """(rows, cols) the kernel reports for the child, i.e. what it was told."""
    import fcntl
    import struct
    import termios

    buf = fcntl.ioctl(view.terminal.pty.fd, termios.TIOCGWINSZ, b"\0" * 8)
    rows, cols, _xpix, _ypix = struct.unpack("HHHH", buf)
    return rows, cols


def main() -> int:
    qInstallMessageHandler(handler)
    app, engine, _bridge = create([sys.argv[0]],
                                  startup_argv=["/bin/sh", "-i"], cwd="/tmp")
    if not engine.rootObjects():
        print("bootcheck: no root object")
        return 1
    root = engine.rootObjects()[0]
    root.resize(800, 480)

    state = {"view": None}

    def call(name: str, *args) -> None:
        if not QMetaObject.invokeMethod(root, name, *args):
            problems.append(f"bootcheck: {name}() is not invokable")

    def visible_view() -> TerminalView | None:
        for view in root.findChildren(TerminalView):
            if view.isVisible():
                return view
        return None

    def first() -> None:
        view = visible_view()
        if view is None:
            problems.append("bootcheck: no visible TerminalView after startup")
            return finish()
        state["view"] = view
        # QML resolves calls through the meta-object: a method without @Slot is
        # invisible there and the action silently does nothing (that is how
        # copy/paste/zoom/close-tab were dead in 0.2.8 and earlier).
        for signature in (
            "copy()", "paste()", "selectAll()", "clearSelection()",
            "clearScrollback()", "scrollToBottom()", "zoom(double)",
            "resetZoom()", "sendText(QString)", "focusTerminal()", "kill()",
            "applySettings(QVariant,QVariant)", "selectionText()",
            "searchText()", "scrollLines(int)",
        ):
            if view.metaObject().indexOfMethod(signature) < 0:
                problems.append(
                    f"bootcheck: TerminalView.{signature} is not a slot")
        if view.cols <= 0 or view.rows <= 0:
            problems.append(f"bootcheck: grid is {view.cols}x{view.rows}")
        # The shell must be spawned into the settled grid, and the PTY must
        # agree with the VT. A resize racing the shell's first prompt leaves
        # zsh filling its partial-line marker with more spaces than the grid
        # holds, which strands a stray '%' above the prompt.
        grid = view._grid()
        vt = view.terminal.vt
        if (vt.cols, vt.rows) != grid:
            problems.append(
                f"bootcheck: shell spawned at {vt.cols}x{vt.rows}, grid is "
                f"{grid[0]}x{grid[1]}")
        if pty_size(view) != (vt.rows, vt.cols):
            problems.append(
                f"bootcheck: pty is {pty_size(view)[1]}x{pty_size(view)[0]}, "
                f"vt is {vt.cols}x{vt.rows}")
        QTimer.singleShot(0, resize_burst)

    def resize_burst() -> None:
        # Two sizes a few ms apart are one layout in progress, not two. Each
        # one that reaches the shell is a SIGWINCH, and a SIGWINCH landing
        # while the shell draws its prompt is what strands zsh's '%' marker.
        resizes.clear()
        root.resize(760, 460)
        QTimer.singleShot(10, lambda: root.resize(700, 440))
        QTimer.singleShot(250, resize_settled)

    def resize_settled() -> None:
        if len(resizes) != 1:
            problems.append(
                f"bootcheck: a two-step resize reached the shell {len(resizes)} "
                f"times, expected 1")
        type_text(root, SCRIPT)
        QTimer.singleShot(700, check_output)

    def check_output() -> None:
        view = visible_view()
        text = screen_text(view)
        if "BOOTCHECK-OK" not in text:
            problems.append(f"bootcheck: command output missing, screen={text!r:.200}")
        if "80" not in text:
            problems.append("bootcheck: seq output missing (no scrollback to test)")
        call("newTab")
        QTimer.singleShot(500, second_tab)

    def second_tab() -> None:
        views = [v for v in root.findChildren(TerminalView) if v.isVisible()]
        if len(views) != 1:
            problems.append(f"bootcheck: expected 1 visible view, got {len(views)}")
        if len(root.findChildren(TerminalView)) < 2:
            problems.append("bootcheck: new tab did not create a second terminal")
        call("cycle", Q_ARG("QVariant", -1))
        QTimer.singleShot(250, scrolled)

    def scrolled() -> None:
        view = visible_view()
        state["view"] = view
        view.scrollLines(5)
        if view.scroll_offset != 5:
            problems.append(f"bootcheck: scroll offset is {view.scroll_offset}")
        view.selectAll()
        if not view.selection_text():
            problems.append("bootcheck: select-all produced no text")
        view.clearSelection()
        view.scrollToBottom()
        if view.scroll_offset != 0:
            problems.append("bootcheck: scrollToBottom left an offset")
        QTimer.singleShot(200, tabs_stable)

    def tabs_stable() -> None:
        """A title change must not move the tabs (they used to resize to the title)."""
        state["tabs_before"] = [(round(t.x()), round(t.width())) for t in tab_items(root)]
        key = tab_items(root)[0].property("tabKey")
        call("setLabel", Q_ARG("QVariant", key),
             Q_ARG("QVariant", "vim /home/hyprtk/Projects/notes.md"))
        QTimer.singleShot(200, tabs_check_geometry)

    def tabs_check_geometry() -> None:
        before = state.get("tabs_before") or []
        after = [(round(t.x()), round(t.width())) for t in tab_items(root)]
        if not before or before != after:
            problems.append(f"bootcheck: tabs moved with the title: {before} -> {after}")
        call("setLabel", Q_ARG("QVariant", tab_items(root)[0].property("tabKey")),
             Q_ARG("QVariant", "Terminal"))
        QTimer.singleShot(150, tabs_click)

    def tabs_click() -> None:
        items = tab_items(root)
        if len(items) < 2:
            problems.append(f"bootcheck: expected 2 tabs, found {len(items)}")
            return settings()
        click_item(root, items[0])
        QTimer.singleShot(250, lambda: tabs_verify(items, 0))

    def tabs_verify(items, index: int) -> None:
        expected = items[index].property("tabKey")
        if root.property("activeId") != expected:
            problems.append(
                f"bootcheck: clicking tab {index} gave {root.property('activeId')!r}, "
                f"expected {expected!r}")
        visible = [v for v in root.findChildren(TerminalView) if v.isVisible()]
        if len(visible) != 1:
            problems.append(f"bootcheck: {len(visible)} visible terminals")
        if index + 1 < len(items):
            click_item(root, items[index + 1])
            QTimer.singleShot(250, lambda: tabs_verify(items, index + 1))
        else:
            # back to the tab that owns the BOOTCHECK output for the find test
            click_item(root, items[0])
            QTimer.singleShot(300, settings)

    def settings() -> None:
        root.setProperty("settingsOpen", True)
        QTimer.singleShot(350, settings_layout)

    def settings_layout() -> None:
        """Every stepper button must sit inside the card."""
        cards = [i for i in root.findChildren(QQuickItem) if i.objectName() == "settingsCard"]
        plus = [i for i in root.findChildren(QQuickItem) if i.objectName() == "stepperPlus"]
        if not cards:
            problems.append("bootcheck: settings card not found")
        elif not plus:
            problems.append("bootcheck: no stepper buttons found")
        else:
            card_right = cards[0].mapToScene(QPointF(cards[0].width(), 0)).x()
            for index, button in enumerate(plus):
                right = button.mapToScene(QPointF(button.width(), 0)).x()
                if right > card_right + 0.5:
                    problems.append(
                        f"bootcheck: stepper {index} overflows the card by "
                        f"{round(right - card_right)} px")
        labels = [i for i in root.findChildren(QQuickItem)
                  if i.objectName() == "appVersion"]
        if not labels:
            problems.append("bootcheck: settings has no version label")
        else:
            expected = f"hyprtk-term {__version__}"
            actual = str(labels[0].property("text") or "")
            if actual != expected:
                problems.append(
                    f"bootcheck: version label is {actual!r}, expected {expected!r}")
        QTimer.singleShot(150, settings_close)

    def settings_close() -> None:
        root.setProperty("settingsOpen", False)
        QTimer.singleShot(150, find)

    def find() -> None:
        call("toggleFind")
        view = visible_view()
        found = view.runSearch("BOOTCHECK", False, False)
        if found < 1:
            problems.append(f"bootcheck: search found {found} matches for BOOTCHECK")
        if not view.searchNext():
            problems.append("bootcheck: searchNext reported no match")
        html = view.runSearch("BOOTCHECK", False, True)
        if html < 1:
            problems.append("bootcheck: regex search found nothing")
        view.clearSearch()
        if view.matchCount != 0:
            problems.append("bootcheck: clearSearch left matches")
        call("toggleFind")
        QTimer.singleShot(200, palette)

    def palette() -> None:
        call("applyAll")
        colors = root.property("th")
        if not isinstance(colors, dict) or "ansi" not in colors:
            problems.append(f"bootcheck: palette is {type(colors).__name__}")
        QTimer.singleShot(150, alpha_check)

    def alpha_check() -> None:
        """At <100% opacity the strip and the grid must composite identically."""
        _bridge.setConfig("opacity", 0.58)
        QTimer.singleShot(400, alpha_verify)

    def alpha_verify() -> None:
        image = root.grabWindow()
        header = image.pixelColor(600, 12)
        body = image.pixelColor(600, image.height() - 20)
        if header != body:
            problems.append(
                f"bootcheck: strip {header.name()} != grid {body.name()} at 58% opacity")
        _bridge.setConfig("opacity", 0.98)
        QTimer.singleShot(200, finish)

    def finish() -> None:
        global finished
        finished = True
        warnings = [p for p in problems if not p.startswith("bootcheck:")]
        failures = [p for p in problems if p.startswith("bootcheck:")]
        for failure in failures:
            print(failure)
        print(f"bootcheck: root objects={len(engine.rootObjects())}, "
              f"warnings={len(warnings)}, failures={len(failures)}")
        app.exit(1 if problems else 0)

    QTimer.singleShot(500, first)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
