"""Search: pattern building, matching, column mapping, scrolling."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyprtk_term import search  # noqa: E402


class FakeVT:
    """Lines in, no libvterm."""

    def __init__(self, lines, rows=4):
        self.lines = lines
        self.rows = rows

    @property
    def scrollback_len(self):
        return max(0, len(self.lines) - self.rows)

    def line_text(self, index):
        if not (0 <= index < len(self.lines)):
            return ""
        return "".join(self.lines[index]).rstrip()

    def line_cells(self, index):
        if not (0 <= index < len(self.lines)):
            return []
        return list(self.lines[index])


def cells(text, width=20):
    out = list(text)
    while len(out) < width:
        out.append(" ")
    return out


class Patterns(unittest.TestCase):
    def test_empty_query_has_no_pattern(self):
        self.assertIsNone(search.build_pattern(""))

    def test_plain_query_escapes_specials(self):
        pattern = search.build_pattern("a.b")
        self.assertIsNotNone(pattern.search("xa.by"))
        self.assertIsNone(pattern.search("axb"))

    def test_case_insensitive_by_default(self):
        self.assertIsNotNone(search.build_pattern("Hello").search("hello"))

    def test_case_sensitive(self):
        self.assertIsNone(search.build_pattern("Hello", case_sensitive=True).search("hello"))

    def test_regex(self):
        pattern = search.build_pattern(r"\d+", regex=True)
        self.assertIsNotNone(pattern.search("abc 123"))

    def test_invalid_regex_is_none(self):
        self.assertIsNone(search.build_pattern("(unclosed", regex=True))


class Flatten(unittest.TestCase):
    def test_text_and_columns(self):
        text, cols = search.flatten(list("abc"))
        self.assertEqual(text, "abc")
        self.assertEqual(cols, [0, 1, 2])

    def test_wide_glyph_continuation_is_skipped(self):
        text, cols = search.flatten(["中", "", "a"])
        self.assertEqual(text, "中a")
        self.assertEqual(cols, [0, 2])


class Matches(unittest.TestCase):
    def test_single_line(self):
        vt = FakeVT([cells("alpha beta alpha")])
        out = search.find_matches(vt, "alpha")
        self.assertEqual([(m.line, m.start, m.end) for m in out],
                         [(0, 0, 5), (0, 11, 16)])

    def test_across_history_and_screen(self):
        vt = FakeVT([cells("one"), cells("two"), cells("one again"), cells("x")])
        out = search.find_matches(vt, "one")
        self.assertEqual([m.line for m in out], [0, 2])

    def test_case_option(self):
        vt = FakeVT([cells("Hello hello")])
        self.assertEqual(len(search.find_matches(vt, "hello")), 2)
        self.assertEqual(len(search.find_matches(vt, "hello", case_sensitive=True)), 1)

    def test_regex_mode(self):
        vt = FakeVT([cells("ip 10.0.0.1 and 10.0.0.2")])
        out = search.find_matches(vt, r"10\.0\.0\.\d", regex=True)
        self.assertEqual(len(out), 2)

    def test_column_mapping_after_a_wide_glyph(self):
        vt = FakeVT([["中", "", "a", "b", "c", " "]])
        out = search.find_matches(vt, "ab")
        self.assertEqual((out[0].start, out[0].end), (2, 4))

    def test_no_match(self):
        vt = FakeVT([cells("nothing here")])
        self.assertEqual(search.find_matches(vt, "zebra"), [])

    def test_empty_query(self):
        vt = FakeVT([cells("abc")])
        self.assertEqual(search.find_matches(vt, ""), [])

    def test_match_limit(self):
        vt = FakeVT([cells("x" * 20) for _ in range(5)])
        self.assertEqual(len(search.find_matches(vt, "x", limit=7)), 7)


class Navigation(unittest.TestCase):
    def setUp(self):
        self.matches = [search.Match(0, 0, 1), search.Match(2, 3, 4), search.Match(5, 0, 2)]

    def test_next_wraps(self):
        self.assertEqual(search.line_of_next(self.matches, 0, 1), 1)
        self.assertEqual(search.line_of_next(self.matches, 2, 1), 0)

    def test_previous_wraps(self):
        self.assertEqual(search.line_of_next(self.matches, 0, -1), 2)

    def test_empty(self):
        self.assertEqual(search.line_of_next([], 0, 1), -1)

    def test_scroll_keeps_a_line_near_the_top_third(self):
        self.assertEqual(search.scroll_for_line(1000, 2000, 30), 1010)   # line lands a third down
        self.assertEqual(search.scroll_for_line(5, 2000, 30), 2000)   # clamps to bottom
        self.assertEqual(search.scroll_for_line(0, 0, 30), 0)


if __name__ == "__main__":
    unittest.main()
