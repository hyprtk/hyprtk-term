#!/usr/bin/env python3
"""Render the app offscreen with a scripted terminal session and save a PNG."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer                      # noqa: E402
from PySide6.QtGui import QGuiApplication              # noqa: E402

from hyprtk_term.app import create                     # noqa: E402

SCRIPT = r'''
printf '\033[38;5;140m~/Projects/AI-Projects\033[0m \033[38;5;44mgit:(main)\033[0m\n'
eza --color=always --icons --group-directories-first -l ~/Projects/AI-Projects 2>/dev/null | head -10
printf '\n'
git -C ~/Projects/AI-Projects/hyprtk-editor log --stat --color=always -1 | head -12
printf '\n\033[1mhyprtk-term\033[0m  libvterm 0.3.3 · 93 tests · \033[38;2;2;222;222mtruecolor\033[0m \033[38;2;253;79;182mpalette\033[0m\n'
sleep 3
'''


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "shot.png"
    app, engine, _bridge = create(["hyprtk-term", "-name", "hyprtk-term"],
                                  startup_argv=["/bin/sh", "-c", SCRIPT], cwd=os.path.expanduser("~"))
    window = engine.rootObjects()[0]
    window.resize(940, 580)

    def grab() -> None:
        image = window.grabWindow()
        image.save(out)
        print(f"saved {out} ({image.width()}x{image.height()})")
        QGuiApplication.quit()

    QTimer.singleShot(1400, grab)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
