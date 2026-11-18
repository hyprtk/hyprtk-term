"""Selection geometry and text extraction (no Qt, no display)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyprtk_term import select  # noqa: E402


class FakeVT:
    """Just the bit of the VT that selection needs."""

    def __init__(self, lines):
        self.lines = lines

    def line_cells(self, index):
        return list(self.lines[index]) if 0 <= index < len(self.lines) else []


def cells(text, width=12):
    out = list(text)
    while len(out) < width:
        out.append(" ")
    return out


class WordBounds(unittest.TestCase):
    def test_inside_a_word(self):
        row = cells("git checkout main")
        self.assertEqual(select.word_bounds(row, 1), (0, 3))
        self.assertEqual(select.word_bounds(row, 0), (0, 3))

    def test_whitespace_selects_one_cell(self):
        row = cells("a b")
        self.assertEqual(select.word_bounds(row, 1), (1, 2))

    def test_punctuation_selects_one_cell(self):
        row = cells("a+b")
        self.assertEqual(select.word_bounds(row, 1), (1, 2))

    def test_underscore_is_part_of_a_word(self):
        row = cells("my_var = 1")
        self.assertEqual(select.word_bounds(row, 2), (0, 6))

    def test_edges_and_empty_rows(self):
        self.assertEqual(select.word_bounds([], 3), (0, 0))
        self.assertEqual(select.word_bounds(cells("ab", 2), 99), (0, 2))
        self.assertEqual(select.word_bounds(cells("ab"), 11), (11, 12))   # clamped to padding

    def test_is_word(self):
        self.assertTrue(select.is_word("a"))
        self.assertTrue(select.is_word("9"))
        self.assertTrue(select.is_word("_"))
        self.assertFalse(select.is_word(" "))
        self.assertFalse(select.is_word(""))


class Text(unittest.TestCase):
    def test_line_text_drops_trailing_blanks(self):
        self.assertEqual(select.line_text(cells("hi")), "hi")

    def test_single_line_selection(self):
        vt = FakeVT([cells("hello world")])
        self.assertEqual(select.selection_text(vt, (0, 0, 0, 5)), "hello")

    def test_multi_line_selection(self):
        vt = FakeVT([cells("one"), cells("two"), cells("three")])
        self.assertEqual(select.selection_text(vt, (0, 1, 2, 3)), "ne\ntwo\nthr")

    def test_reversed_selection_is_normalized(self):
        vt = FakeVT([cells("abc"), cells("def")])
        self.assertEqual(select.selection_text(vt, (1, 1, 0, 2)), "c\nd")

    def test_empty_selection(self):
        vt = FakeVT([cells("abc")])
        self.assertEqual(select.selection_text(vt, None), "")
        self.assertEqual(select.selection_text(vt, (0, 2, 0, 2)), "")

    def test_wide_glyph_continuation_is_skipped(self):
        vt = FakeVT([["中", "", "a", " "]])
        self.assertEqual(select.selection_text(vt, (0, 0, 0, 3)), "中a")

    def test_normalize(self):
        self.assertEqual(select.normalize((2, 3, 1, 4)), (1, 4, 2, 3))
        self.assertEqual(select.normalize((1, 4, 2, 3)), (1, 4, 2, 3))


if __name__ == "__main__":
    unittest.main()
