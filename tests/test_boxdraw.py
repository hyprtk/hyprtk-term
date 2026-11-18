"""The geometry behind box drawing and block elements.

Pure data and arithmetic: a recording canvas stands in for the painter, so
nothing here needs Qt, a display or libvterm.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyprtk_term import boxdraw  # noqa: E402

CW = 9.0
CH = 22.0
EPS = 1e-6


class Recorder:
    """Canvas that keeps every primitive instead of painting it."""

    def __init__(self) -> None:
        self.rects: list[tuple[float, float, float, float, float]] = []
        self.lines: list[tuple[float, float, float, float, float]] = []
        self.arcs: list[tuple[float, float, float, float, float, float]] = []

    def fill_rect(self, x, y, w, h, alpha=1.0):
        self.rects.append((x, y, w, h, alpha))

    def line(self, x0, y0, x1, y1, thickness):
        self.lines.append((x0, y0, x1, y1, thickness))

    def arc(self, cx, cy, radius, start, span, thickness):
        self.arcs.append((cx, cy, radius, start, span, thickness))

    def ops(self) -> int:
        return len(self.rects) + len(self.lines) + len(self.arcs)


def paint(ch: str, w: float = CW, h: float = CH) -> Recorder:
    canvas = Recorder()
    assert boxdraw.draw(canvas, ch, 0.0, 0.0, w, h), ch
    return canvas


class Coverage(unittest.TestCase):
    def test_every_box_and_block_code_point_is_ours(self):
        missing = [f"U+{cp:04X}" for cp in range(0x2500, 0x25A0)
                   if not boxdraw.is_geometric(chr(cp))]
        self.assertEqual(missing, [])

    def test_ordinary_text_is_left_to_the_font(self):
        for ch in ("a", "\u00b7", "\u2026", "\u2192", " ", "\u2588\u2588"):
            self.assertFalse(boxdraw.is_geometric(ch), repr(ch))

    def test_nothing_draws_outside_its_cell(self):
        for cp in range(0x2500, 0x25A0):
            ch = chr(cp)
            canvas = paint(ch)
            self.assertGreater(canvas.ops(), 0, f"U+{cp:04X} drew nothing")
            for x, y, w, h, _alpha in canvas.rects:
                self.assertGreaterEqual(x, -EPS, f"U+{cp:04X} x")
                self.assertGreaterEqual(y, -EPS, f"U+{cp:04X} y")
                self.assertLessEqual(x + w, CW + EPS, f"U+{cp:04X} right")
                self.assertLessEqual(y + h, CH + EPS, f"U+{cp:04X} bottom")
            for x0, y0, x1, y1, _t in canvas.lines:
                for value in (x0, y0):
                    self.assertGreaterEqual(value, -EPS, f"U+{cp:04X} line")
                self.assertLessEqual(x0, CW + EPS, f"U+{cp:04X} line")
                self.assertLessEqual(y0, CH + EPS, f"U+{cp:04X} line")
                self.assertLessEqual(x1, CW + EPS, f"U+{cp:04X} line")
                self.assertLessEqual(y1, CH + EPS, f"U+{cp:04X} line")


class Blocks(unittest.TestCase):
    def test_full_block_covers_the_cell(self):
        canvas = paint("\u2588")
        self.assertEqual(canvas.rects, [(0.0, 0.0, CW, CH, 1.0)])

    def test_half_blocks_meet_on_the_horizontal_midline(self):
        upper = paint("\u2580").rects[0]
        lower = paint("\u2584").rects[0]
        self.assertEqual(upper, (0.0, 0.0, CW, CH / 2, 1.0))
        self.assertEqual(lower, (0.0, CH / 2, CW, CH / 2, 1.0))

    def test_side_blocks_meet_on_the_vertical_midline(self):
        left = paint("\u258c").rects[0]
        right = paint("\u2590").rects[0]
        self.assertEqual(left, (0.0, 0.0, CW / 2, CH, 1.0))
        self.assertEqual(right, (CW / 2, 0.0, CW / 2, CH, 1.0))

    def test_quadrant_chars_fill_the_right_quarters(self):
        self.assertEqual(paint("\u2598").rects,
                         [(0.0, 0.0, CW / 2, CH / 2, 1.0)])
        self.assertEqual(paint("\u259a").rects,
                         [(0.0, 0.0, CW / 2, CH / 2, 1.0),
                          (CW / 2, CH / 2, CW / 2, CH / 2, 1.0)])

    def test_shades_are_washes_of_the_foreground(self):
        for ch, alpha in (("\u2591", 0.25), ("\u2592", 0.5), ("\u2593", 0.75)):
            self.assertEqual(paint(ch).rects, [(0.0, 0.0, CW, CH, alpha)])


class Lines(unittest.TestCase):
    @staticmethod
    def _span(rects):
        """Union extent of a set of rects, as (left, right, top, bottom)."""
        return (min(r[0] for r in rects),
                max(r[0] + r[2] for r in rects),
                min(r[1] for r in rects),
                max(r[1] + r[3] for r in rects))

    def test_horizontal_spans_the_full_cell(self):
        canvas = paint("\u2500")
        left, right, _top, _bottom = self._span(canvas.rects)
        self.assertEqual(left, 0.0)
        self.assertEqual(right, CW)
        # Centred on the row's midline.
        _x, y, _w, h, _a = canvas.rects[0]
        self.assertAlmostEqual(y + h / 2, CH / 2)

    def test_vertical_spans_the_full_cell(self):
        canvas = paint("\u2502")
        _left, _right, top, bottom = self._span(canvas.rects)
        self.assertEqual(top, 0.0)
        self.assertEqual(bottom, CH)

    def test_heavy_is_thicker_than_light(self):
        light = paint("\u2500").rects[0][3]
        heavy = paint("\u2501").rects[0][3]
        self.assertGreater(heavy, light)

    def test_cross_draws_both_axes(self):
        canvas = paint("\u253c")
        left, right, top, bottom = self._span(canvas.rects)
        self.assertEqual((left, right), (0.0, CW))
        self.assertEqual((top, bottom), (0.0, CH))
        # Each arm is drawn from the centre outwards.
        self.assertEqual(len(canvas.rects), 4)

    def test_double_line_is_two_strokes(self):
        canvas = paint("\u2550")
        self.assertEqual(len(canvas.rects), 4)         # two arms x two strokes
        centres = sorted({round(y + h / 2, 6) for _x, y, _w, h, _a in canvas.rects})
        self.assertEqual(len(centres), 2)
        self.assertLess(centres[0], CH / 2)
        self.assertGreater(centres[1], CH / 2)

    def test_double_corner_does_not_cross_its_own_strokes(self):
        # The upper stroke of the top arm reaches the outer vertical; the lower
        # stroke stops at the inner one, so the corner is nested, not crossed.
        canvas = paint("\u2554")
        horizontals = [r for r in canvas.rects if r[2] > r[3]]
        starts = sorted(r[0] for r in horizontals)
        self.assertEqual(len(starts), 2)
        self.assertLess(starts[0], CW / 2)
        self.assertGreater(starts[1], CW / 2)

    def test_stub_arms_stop_at_the_centre(self):
        canvas = paint("\u2574")                        # light left only
        _x, _y, w, _h, _a = canvas.rects[0]
        self.assertAlmostEqual(w, CW / 2)

    def test_dashes_count_matches_the_code_point(self):
        self.assertEqual(len(paint("\u254c").rects), 2)  # double dash
        self.assertEqual(len(paint("\u2504").rects), 3)  # triple dash
        self.assertEqual(len(paint("\u2508").rects), 4)  # quadruple dash
        self.assertEqual(len(paint("\u254e").rects), 2)  # vertical


class ArcsAndDiagonals(unittest.TestCase):
    def test_rounded_corner_is_one_arc_plus_two_straights(self):
        canvas = paint("\u256d")
        self.assertEqual(len(canvas.arcs), 1)
        _cx, _cy, radius, start, span, _t = canvas.arcs[0]
        self.assertAlmostEqual(radius, min(CW, CH) / 2)
        self.assertEqual((start, span), (90, 90))
        self.assertGreaterEqual(len(canvas.rects), 1)

    def test_each_corner_sweeps_its_own_quadrant(self):
        expected = {"\u256d": 90, "\u256e": 0, "\u256f": 270, "\u2570": 180}
        for ch, start in expected.items():
            self.assertEqual(paint(ch).arcs[0][3], start, ch)

    def test_diagonals_use_the_cell_corners(self):
        down = paint("\u2571").lines[0]
        self.assertEqual(down[:4], (CW, 0.0, 0.0, CH))
        up = paint("\u2572").lines[0]
        self.assertEqual(up[:4], (0.0, 0.0, CW, CH))
        self.assertEqual(len(paint("\u2573").lines), 2)


class Fallback(unittest.TestCase):
    def test_unknown_character_is_not_claimed(self):
        canvas = Recorder()
        self.assertFalse(boxdraw.draw(canvas, "a", 0.0, 0.0, CW, CH))
        self.assertFalse(boxdraw.draw(canvas, "\u2500\u2500", 0.0, 0.0, CW, CH))
        self.assertEqual(canvas.ops(), 0)


if __name__ == "__main__":
    unittest.main()
