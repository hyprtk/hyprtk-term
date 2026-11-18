# hyprtk-term — plan

Status: **v0.1.0 scaffold**, committed locally at `~/Projects/AI-Projects/hyprtk-term`
(`main`, tag `v0.1.0` pending the first publish). The core is proven end to end
(PTY → libvterm → QML), the app opens a real shell on Wayland, and the pieces
that are deliberately missing are listed below rather than half-built.

## Decisions (and why)

| Decision | Rationale |
|---|---|
| **libvterm (C) for the VT core, via ctypes** | Neovim's parser: xterm + DEC modes, 256/truecolor, alt screen, reflow, scrollback hooks, OSC 52 and the key encoder. Packaged on all six families; already in Arch `extra`. ~400 lines of binding instead of a parser. |
| **PySide6 + Qt Quick/QML, not Quickshell** | A terminal is a document app, not a bar: it needs a window, input focus and a text surface. PySide6 is already a suite dependency (editor, usb, iso). QML gives the chrome the same visual language as bar-qt and hyprtk-fm. |
| **`QQuickPaintedItem` painted from Python** | Probed: a grid paints in ~3 ms. A QML `Canvas` would be slower and a scene-graph glyph atlas is a rewrite for no gain. QPainter also shapes text per run, so CJK/emoji/ligature shaping comes from Qt. |
| **Damage-driven row cache** | Reading a 200x50 grid through ctypes costs 10.6 ms; re-reading every frame would make scrolling visibly heavy. libvterm's damage callback marks rows, and only those rows are re-read. |
| **One `TerminalView` per tab, each with its own PTY** | Matches how every real terminal does tabs (Kitty, GNOME Terminal). Closing a tab kills its process tree; no multiplexer state to leak. |
| **Scrollback stored as raw `VTermScreenCell` bytes** | `sb_popline` needs the exact cells back, and reconstructing them from styled runs is lossy. Trimming trailing blanks keeps a 10k-line history near 3 MB instead of 80 MB. |
| **`SIGWINCH` on every geometry change, coalesced** | TUI apps redraw on every resize; a drag generates dozens. The grid resize is idempotent, so only a changed `(rows, cols)` is pushed to the PTY. |
| **No GPU, no images, no multiplexer** | See RESEARCH.md. The measurable cost of skipping them is zero at this size; the cost of building them now is the whole release. |

## Architecture

```
hyprtk_term/
  vtcapi.py    ctypes structs, signatures, enums for libvterm (no state)
  vt.py        VTerminal: feed, row runs, scrollback ring, title, cursor,
               key/ mouse encoding, OSC 52 hooks
  ptyproc.py   Pty: fork/exec, winsize, non-blocking read, reaping
  terminal.py  Terminal(QObject): VT + PTY + QSocketNotifier, signals for
               title / bell / exit / repaint
  view.py      TerminalView(QQuickPaintedItem): paint runs, keys, mouse,
               selection, wheel, focus
  palette.py   pywal + bar theme -> UI tokens and the 16 ANSI slots
  settings.py  ~/.config/hyprtk-term/config.json
  bridge.py    QML facade: config, palette, actions, clipboard, spawn
  app.py       QGuiApplication + QQmlApplicationEngine
  qml/         Main.qml, components/ (TabStrip, SettingsSheet), theme/
```

Python owns everything that touches the OS or the grid; QML owns chrome. The
only object crossing the boundary per tab is `TerminalView`, which exposes
`title`, `cols`, `rows` and `exited` as QML properties.

## v0.1.0 — what this scaffold does

- [x] PTY spawn (login shell), exit detection, `SIGWINCH` on resize
- [x] libvterm core: SGR/256/truecolor, bold/italic/underline/reverse/strike,
      alt screen, wide + combining characters, cursor shape and blink
- [x] Damage-tracked rendering with a per-row run cache
- [x] Scrollback ring (10k lines default) with mouse-wheel scroll and
      "jump to bottom" on input
- [x] Keyboard: printable, control, alt, arrows, Home/End/Ins/Del/PgUp/PgDn,
      F1–F12, modifier-encoded, bracketed paste
- [x] Mouse reporting for TUI apps, local selection when they do not ask
- [x] Linear selection (drag, double-click word), copy / paste, OSC 52 both ways
- [x] Tabs: new, close, switch, title from OSC 0/2, close guard for a running
      process
- [x] pywal/bar palette → ANSI 16, live reload on wallpaper change
- [x] Settings sheet: font family, size, opacity, scrollback, shell
- [x] 93 unit tests, qmllint clean, headless boot check, installer round-trip

## Not in v0.1 (deliberate)

| Missing | Why | Planned |
|---|---|---|
| Splits / panes | A layout model on top of tabs; needs a focus ring and resize maths | v0.3 |
| Scrollback search | Needs a text index over the ring and a highlight overlay | v0.2 |
| OSC 8 hyperlinks | libvterm 0.3.3 has no hyperlink cell attribute | v0.3 (regex URL detection) |
| Inline images (sixel/Kitty) | Separate protocol + image cache | unplanned |
| Ligature clamping | QPainter shapes per run; sparse runs can form accidental ligatures | v0.2 |
| Profiles / per-app themes | One theme that follows the wallpaper is the suite's whole idea | v0.4 (only if asked) |
| IME (compose, CJK input) | `inputMethodEvent` needs a pre-edit overlay | v0.2 |
| Session restore | Nice, but a terminal is cheap to reopen; needs window geometry + cwd capture | v0.4 |
| Shell integration (prompt marks) | OSC 133 parsing + a mark gutter | v0.3 |

## Roadmap

**v0.2 — daily driver.** Scrollback search, IME pre-edit, ligature clamp,
per-tab cwd broadcasting, "open in cwd" for hyprtk-fm, font zoom per tab,
context menu (copy/paste/select all/clear), bell indicator, config hot reload.

**v0.3 — shape.** Splits (H/V, focus ring, drag dividers), keyboard protocol
negotiation (kitty `CSI u`) advertised via terminfo, OSC 133 prompt marks,
URL detection and open, `--working-directory`/`-e CMD` flags.

**v0.4 — suite.** Session restore, drop-down mode (single instance, Hyprland
special workspace), SSH-aware title, `hyprtk-term --list-tabs` for the bar.

## Suite integration checklist

Follows the hyprtk-fm / hyprtk-editor pattern; nothing below is done yet.

1. **Repo** — `hyprtk/hyprtk-term`, tag `v0.1.0`; vendor byte-identically into
   `hyprtk-merged/installer/hyprtk-term/`.
2. **Installer** — `1-install.sh` runs it after hyprtk-fm; `--system` mode for
   the ISO (payload under `/usr/local/share/hyprtk-term`, launcher in
   `/usr/local/bin`).
3. **Packages** — add `libvterm` to `hypr/packages/terminaltools.sh` for all six
   families (`libvterm` on Arch/Fedora/Void/Alpine, `libvterm0` on Debian,
   `libvterm0` on openSUSE — verify per family with the T1 resolver).
4. **Icon** — done in the brand kit (`term` glyph in `gen/brand.py`,
   `hyprtk-term` in `gen/v09.py`, `v09/hyprtk-term*.svg` + PNG ladder) and
   shipped in the payload with an absolute `Icon=` in `install.sh`; the merged
   copy still has to be vendored.
5. **Defaults** — `hl.env("TERMINAL", "hyprtk-term")` in `hypr/environment.lua`
   (alacritty stays installed as the fallback), `Super+Return` keybind, bar
   quick link, `hyprtk-fm` "Open terminal here", editor "Open terminal".
6. **XDG** — `.desktop` with `Categories=System;TerminalEmulator;`,
   `StartupWMClass=hyprtk-term`, `QS_APP_ID` is not needed (Qt sets the app id
   from `setDesktopFileName`).
7. **Docs** — README/CHANGELOG suite banner, wiki row, landing-page table row
   (seven components becomes eight).
8. **Gate** — T1, T2, package audit, then `push-all`.

## Known risks

- **ctypes pointer truncation** silently crashes: every function that returns a
  pointer needs `restype` set. `tests/test_vt.py` boots the binding, but the
  real guard is that all signatures live in one dict (`vtcapi.SIGNATURES`).
- **Damage merge granularity.** `VTERM_DAMAGE_ROW` is used for simplicity. If a
  full-screen TUI (btop, vim) ever repaints slower than ~45 fps, the fix is
  `VTERM_DAMAGE_CELL` plus rect-based paint.
- **Scrollback correctness** depends on `sb_popline` returning the exact cells;
  that is why raw cell bytes are stored. `tests/test_vt.py` covers the reverse
  scroll case.
- **Font metrics drift.** Cell width comes from `QFontMetricsF`; fractional
  widths leave a seam on the right edge. The renderer rounds the grid width up
  and paints the remainder with the background colour.
- **Wayland clipboard on focus loss.** `QClipboard.text()` can be empty if the
  source app closed; paste falls back to the primary selection.
- **Field test (2026-11-18).** Launched under Hyprland on the live session: the
  toplevel reports `class=hyprtk-term` (so `setDesktopFileName` is doing its
  job), the OSC title from the user's zsh prompt becomes the tab label, and
  fastfetch/`eza`/`git --color` render with the wallpaper palette. No Qt
  warnings, no crash.
- **QML `text` bounds.** A `QQuickPaintedItem` does not clip by default in print
  mode; `paint()` sets `setClipRect` to the grid. Anything drawn outside it
  (long run, odd font fallback) is cut rather than overflowing the chrome.
