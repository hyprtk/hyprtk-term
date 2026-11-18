"""The VT core: parsing, runs, colours, scrollback, key encoding.

No Qt and no display: everything here runs headlessly against libvterm.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyprtk_term.vt import (  # noqa: E402
    A_BOLD, A_ITALIC, A_REVERSE, A_STRIKE, A_UNDERLINE, VTerminal,
    modifier_for,
)
from hyprtk_term.vtcapi import KEY, MOD  # noqa: E402

FG = 0xE5E7EB
BG = 0x1E1E2E
ANSI = [
    0x45475A, 0xF38BA8, 0xA6E3A1, 0xF9E2AF, 0x89B4FA, 0xC084FC, 0x22D3EE, 0xBAC2DE,
    0x585B70, 0xF38BA8, 0xA6E3A1, 0xF9E2AF, 0x89B4FA, 0xC084FC, 0x22D3EE, 0xA6ADCA,
]


def term(rows=6, cols=30, scrollback=50):
    t = VTerminal(rows, cols, scrollback)
    t.set_theme(FG, BG, ANSI)
    return t


def text(t: VTerminal, row: int) -> str:
    return "".join(r.text for r in t.row_runs(row))


class TextAndRuns(unittest.TestCase):
    def test_plain_text(self):
        t = term()
        t.feed(b"hello")
        self.assertEqual(text(t, 0), "hello")
        self.assertEqual(t.cursor.col, 5)

    def test_newline_and_cr(self):
        t = term()
        t.feed(b"one\r\ntwo")
        self.assertEqual(text(t, 0), "one")
        self.assertEqual(text(t, 1), "two")

    def test_long_line_wraps(self):
        t = term(rows=4, cols=10)
        t.feed(b"abcdefghijklm")
        self.assertEqual(text(t, 0), "abcdefghij")
        self.assertEqual(text(t, 1), "klm")

    def test_trailing_blanks_are_dropped(self):
        t = term()
        t.feed(b"ab")
        self.assertEqual(len(t.row_runs(0)), 1)
        self.assertEqual(t.row_runs(0)[0].text, "ab")

    def test_palette_colour_is_resolved_from_theme(self):
        t = term()
        t.feed(b"\x1b[31mX")
        run = t.row_runs(0)[0]
        self.assertEqual(run.text, "X")
        self.assertEqual(run.fg, ANSI[1])

    def test_truecolor(self):
        t = term()
        t.feed(b"\x1b[38;2;2;222;222mX")
        self.assertEqual(t.row_runs(0)[0].fg, 0x02DEDE)

    def test_256_colour_uses_the_cube_for_high_indexes(self):
        t = term()
        t.feed(b"\x1b[38;5;196mX")
        self.assertEqual(t.row_runs(0)[0].fg, 0xFF0000)

    def test_bold_italic_underline_strike(self):
        t = term()
        t.feed(b"\x1b[1;3;4;9mX")
        flags = t.row_runs(0)[0].flags
        for bit in (A_BOLD, A_ITALIC, A_UNDERLINE, A_STRIKE):
            self.assertTrue(flags & bit, hex(flags))

    def test_reverse_swaps_colours(self):
        t = term()
        t.feed(b"\x1b[7mX")
        run = t.row_runs(0)[0]
        self.assertEqual(run.fg, BG)
        self.assertEqual(run.bg, FG)
        self.assertFalse(run.flags & A_REVERSE)

    def test_conceal_draws_text_in_the_background_colour(self):
        t = term()
        t.feed(b"\x1b[8mX")
        run = t.row_runs(0)[0]
        self.assertEqual(run.fg, run.bg)

    def test_default_bg_blank_cells_are_not_runs(self):
        t = term(cols=10)
        t.feed(b"a\x1b[44m \x1b[0m")
        runs = t.row_runs(0)
        self.assertEqual(runs[0].text, "a")
        self.assertEqual(runs[1].text, " ")
        self.assertEqual(runs[1].bg, ANSI[4])

    def test_wide_characters_occupy_two_columns(self):
        t = term()
        t.feed("中文 ok".encode())
        runs = t.row_runs(0)
        self.assertEqual(runs[0].text, "中文 ok")
        self.assertEqual(runs[0].cols, 7)

    def test_combining_marks_are_kept_in_the_cell(self):
        t = term()
        t.feed("e\u0301".encode())
        self.assertEqual(text(t, 0), "e\u0301")


class CursorAndProps(unittest.TestCase):
    def test_cursor_moves(self):
        t = term()
        t.feed(b"abc\x1b[2;5H")
        self.assertEqual((t.cursor.row, t.cursor.col), (1, 4))

    def test_cursor_visibility(self):
        t = term()
        t.feed(b"\x1b[?25l")
        self.assertFalse(t.cursor.visible)
        t.feed(b"\x1b[?25h")
        self.assertTrue(t.cursor.visible)

    def test_cursor_shape(self):
        t = term()
        t.feed(b"\x1b[5 q")
        self.assertEqual(t.cursor.shape, 3)     # bar

    def test_title_from_osc_0_and_osc_2(self):
        t = term()
        t.feed(b"\x1b]0;vim notes\x07")
        self.assertEqual(t.title, "vim notes")
        t.feed(b"\x1b]2;second\x1b\\")
        self.assertEqual(t.title, "second")

    def test_bell_counts(self):
        t = term()
        t.feed(b"\x07\x07")
        self.assertEqual(t.bell_count, 2)

    def test_alt_screen_flag(self):
        t = term()
        t.feed(b"\x1b[?1049h")
        self.assertTrue(t.alt_screen)
        t.feed(b"\x1b[?1049l")
        self.assertFalse(t.alt_screen)

    def test_mouse_mode(self):
        t = term()
        self.assertEqual(t.mouse_mode, 0)
        t.feed(b"\x1b[?1000h")
        self.assertEqual(t.mouse_mode, 1)


class Scrollback(unittest.TestCase):
    def test_lines_are_pushed_into_history(self):
        t = term(rows=3, cols=12)
        t.feed(b"".join(b"line %d\r\n" % i for i in range(10)))
        self.assertEqual(t.scrollback_len, 8)
        self.assertEqual("".join(r.text for r in t.scrollback_runs(0)), "line 0")

    def test_history_is_capped(self):
        t = term(rows=2, cols=10, scrollback=4)
        t.feed(b"".join(b"%d\r\n" % i for i in range(20)))
        self.assertLessEqual(t.scrollback_len, 4)

    def test_clear_scrollback(self):
        t = term(rows=2, cols=10)
        t.feed(b"a\r\nb\r\nc\r\n")
        self.assertGreater(t.scrollback_len, 0)
        t.clear_scrollback()
        self.assertEqual(t.scrollback_len, 0)

    def test_set_scrollback_trims_history(self):
        t = term(rows=2, cols=10, scrollback=100)
        t.feed(b"".join(b"%d\r\n" % i for i in range(20)))
        before = t.scrollback_len
        t.set_scrollback(3)
        self.assertEqual(t.scrollback_len, min(before, 3))

    def test_disabled_scrollback_keeps_nothing(self):
        t = term(rows=2, cols=10, scrollback=0)
        t.feed(b"a\r\nb\r\nc\r\nd\r\n")
        self.assertEqual(t.scrollback_len, 0)

    def test_history_text_joins_lines(self):
        t = term(rows=2, cols=10)
        t.feed(b"one\r\ntwo\r\nthree\r\n")
        self.assertIn("one", t.history_text())


class LineCells(unittest.TestCase):
    def test_cells_are_per_column(self):
        t = term(cols=6)
        t.feed(b"ab")
        self.assertEqual(t.line_cells(0)[:3], ["a", "b", " "])

    def test_wide_glyph_marks_the_continuation_cell(self):
        t = term(cols=6)
        t.feed("中a".encode())
        cells = t.line_cells(0)
        self.assertEqual(cells[0], "中")
        self.assertEqual(cells[1], "")
        self.assertEqual(cells[2], "a")

    def test_out_of_range_is_empty(self):
        t = term(rows=2, cols=4)
        self.assertEqual(t.line_cells(-1), [])
        self.assertEqual(t.line_cells(99), [])


class Resize(unittest.TestCase):
    def test_resize_updates_the_grid(self):
        t = term(rows=6, cols=20)
        self.assertTrue(t.resize(10, 40))
        self.assertEqual((t.rows, t.cols), (10, 40))

    def test_same_size_is_a_noop(self):
        t = term(rows=6, cols=20)
        self.assertFalse(t.resize(6, 20))

    def test_content_survives_a_grow(self):
        t = term(rows=4, cols=20)
        t.feed(b"keep")
        t.resize(8, 30)
        self.assertEqual(text(t, 0), "keep")

    def test_reflow_keeps_long_text(self):
        t = term(rows=4, cols=10)
        t.feed(b"abcdefghij")
        t.resize(4, 5)
        joined = text(t, 0) + text(t, 1)
        self.assertEqual(joined, "abcdefghij")


class Keys(unittest.TestCase):
    def test_special_keys(self):
        t = term()
        self.assertEqual(t.key(KEY["ENTER"]), b"\r")
        self.assertEqual(t.key(KEY["TAB"]), b"\t")
        self.assertEqual(t.key(KEY["BACKSPACE"]), b"\x7f")
        self.assertEqual(t.key(KEY["ESCAPE"]), b"\x1b")
        self.assertEqual(t.key(KEY["UP"]), b"\x1b[A")
        self.assertEqual(t.key(KEY["DOWN"]), b"\x1b[B")
        self.assertEqual(t.key(KEY["FUNCTION_0"] + 1), b"\x1bOP")
        self.assertEqual(t.key(KEY["FUNCTION_0"] + 5), b"\x1b[15~")

    def test_modifiers(self):
        t = term()
        self.assertEqual(t.key(KEY["UP"], MOD["SHIFT"]), b"\x1b[1;2A")
        self.assertEqual(t.key(KEY["UP"], MOD["CTRL"]), b"\x1b[1;5A")
        self.assertEqual(t.key(KEY["TAB"], MOD["SHIFT"]), b"\x1b[Z")

    def test_control_characters(self):
        t = term()
        self.assertEqual(t.unichar(ord("a"), MOD["CTRL"]), b"\x01")
        self.assertEqual(t.unichar(ord("c"), MOD["CTRL"]), b"\x03")
        self.assertEqual(t.unichar(ord("d"), MOD["CTRL"]), b"\x04")

    def test_alt_prefixes_escape(self):
        t = term()
        self.assertEqual(t.unichar(ord("b"), MOD["ALT"]), b"\x1bb")

    def test_plain_text(self):
        t = term()
        self.assertEqual(t.unichar(ord("Z")), b"Z")

    def test_paste_uses_bracketed_mode_when_asked(self):
        t = term()
        t.feed(b"\x1b[?2004h")
        self.assertEqual(t.paste("ab"), b"\x1b[200~ab\x1b[201~")

    def test_paste_without_the_mode_is_plain(self):
        t = term()
        self.assertEqual(t.paste("ab"), b"ab")

    def test_newlines_in_a_paste_become_returns(self):
        t = term()
        self.assertEqual(t.paste("a\nb"), b"a\rb")

    def test_modifier_for(self):
        self.assertEqual(modifier_for(True, False, False), MOD["SHIFT"])
        self.assertEqual(modifier_for(True, True, True), 7)


class Damage(unittest.TestCase):
    def test_dirty_rows_are_reported_and_cleared(self):
        t = term()
        t.take_dirty()
        t.feed(b"x")
        self.assertTrue(t.take_dirty())
        self.assertFalse(t.take_dirty())

    def test_changed_rows_invalidate_the_run_cache(self):
        t = term()
        t.feed(b"one")
        self.assertEqual(text(t, 0), "one")
        t.feed(b"\r\x1b[Ktwo")
        self.assertEqual(text(t, 0), "two")

    def test_theme_change_repaints_everything(self):
        t = term()
        t.feed(b"hello")
        self.assertEqual(t.row_runs(0)[0].fg, FG)
        t.set_theme(0xFFFFFF, 0x000000, ANSI)
        self.assertEqual(t.row_runs(0)[0].fg, 0xFFFFFF)

    def test_selection_clipboard_callback_is_wired(self):
        got = []
        t = term()
        t.on_clipboard = lambda text, primary: got.append((text, primary))
        t.feed(b"\x1b]52;c;SGVsbG8=\x07")
        self.assertEqual(got, [("Hello", False)])


if __name__ == "__main__":
    unittest.main()
