"""Documentation links: every relative link and image must exist.

This exists because `docs/search.png` was added to the README while `.gitignore`
still ignored `docs/*.png`; the file was in the working tree and in the vendored
copy, but never in the repository, so the image was broken on GitHub and nothing
noticed.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)")
HTML_SRC = re.compile(r"<(?:img|a)[^>]+(?:src|href)=\"([^\"]+)\"")
EXTERNAL = ("http://", "https://", "mailto:", "#", "data:")


def targets(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    for pattern in (LINK, HTML_SRC):
        for match in pattern.finditer(text):
            target = match.group(1)
            if target.startswith(EXTERNAL):
                continue
            yield target.split("#", 1)[0]


class LocalLinks(unittest.TestCase):
    def test_every_relative_link_resolves(self) -> None:
        missing = []
        for doc in sorted(ROOT.glob("*.md")):
            for target in targets(doc):
                if not target:
                    continue
                if not (ROOT / target).exists():
                    missing.append(f"{doc.name} -> {target}")
        self.assertEqual(missing, [], "broken relative links: " + ", ".join(missing))

    def test_readme_images_are_tracked(self) -> None:
        """A file that exists but is git-ignored is just as broken on GitHub."""
        readme = ROOT / "README.md"
        images = [t for t in targets(readme) if t.lower().endswith((".png", ".jpg", ".svg"))]
        self.assertTrue(images, "README should show at least the icon")
        try:
            tracked = subprocess.run(
                ["git", "-C", str(ROOT), "ls-files", "--", *images],
                capture_output=True, text=True, timeout=10,
            ).stdout.split()
        except (OSError, subprocess.SubprocessError):   # pragma: no cover - no git
            self.skipTest("git unavailable")
        untracked = sorted(set(images) - set(tracked))
        self.assertEqual(untracked, [], f"README images not committed: {untracked}")


if __name__ == "__main__":
    unittest.main()
