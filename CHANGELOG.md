# Changelog

## 0.1.0 — 2026-11-18

First scaffold. A real shell in a real window, with the parts that make it
usable daily and an honest list of what is not there yet (see PLAN.md).

### Added

- **libvterm core through ctypes.** xterm/DEC parsing, alt screen, reflow,
  scroll regions, 256-colour and truecolor, bold/italic/underline/strike/
  reverse/conceal/blink, wide and combining characters.
- **Theme-following palette.** The 16 ANSI slots come from pywal through the
  bar's theme, the same loader the editor and file manager use. A wallpaper
  change reloads every open tab.
- **Damage-tracked rendering.** libvterm reports damaged rows, the rows are
  re-read through ctypes and cached as styled runs, and QPainter draws runs
  instead of cells. A full 80x24 grid paints in ~3 ms.
- **Scrollback.** A ring of raw `VTermScreenCell` bytes (10,000 lines by
  default) so `sb_popline` can hand libvterm its own cells back; wheel scroll,
  jump to bottom, clear.
- **Tabs** with the OSC title, middle-click close, bell indicator, and one PTY
  per tab.
- **Input.** libvterm's key encoder (arrows, Home/End/Ins/Del/PgUp/PgDn, F1–F12,
  modifiers, control characters, alt prefix), bracketed paste, IME commits,
  mouse reporting with Shift override.
- **Selection and clipboard.** Linear and word selection, select-all, copy/paste,
  and OSC 52 in both directions.
- **Settings sheet** (`Ctrl+,`) for font, size, opacity, scrollback, cursor
  blink and copy-on-select, saved to `~/.config/hyprtk-term/config.json`.
- **Suite integration scaffolding.** v09 icon (`term` glyph added to the brand
  kit), installer with `--system`/`--uninstall`/`--set-default`, desktop entry,
  Symbols Nerd Font chrome.

### Notes

- 93 unit tests, `qmllint` clean, headless boot check, installer round-trip;
  `make qa` runs the lot.
- Not in 0.1: splits, scrollback search, OSC 8 hyperlinks, inline images,
  ligature clamping, session restore. Each is scheduled in PLAN.md.

## Unreleased

- Nothing yet.
