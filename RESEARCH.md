# Research: terminal emulators, and what hyprtk-term borrows

Survey done 2026-11-18. The goal was not to write a new VT parser from scratch
and not to fork an existing terminal: it was to find the smallest honest core
that can render a real shell, match the suite's theme, and stay packageable on
all six distro families the installer supports.

## The field, 2026

| Terminal | Stack | Render | Ideas worth taking |
|---|---|---|---|
| Ghostty | Zig, GTK4 / SwiftUI | Metal / Vulkan / OpenGL | `libghostty` as an embeddable core; native per-OS UI; theme pairs; instant resize; zero input lag |
| Kitty | C + Python | OpenGL | Graphics protocol, kittens (scriptable extensions), remote control, keyboard protocol, best sustained frame rate |
| Alacritty | Rust, winit | OpenGL | Deliberate minimalism — the WM/tmux owns tabs and splits; toml config |
| WezTerm | Rust | WebGPU/OpenGL | Lua config, multiplexer in-binary, panes that survive disconnects |
| foot | C, Wayland-only | CPU (pixman) | 251 ms on an 11 MB dump and 15 ms latency, beating every GPU terminal; client/server mode |
| Konsole / QTermWidget | C++ / Qt | QPainter | `TerminalDisplay` split from the emulator; KDE's sixel + profile handling |
| cool-retro-term | QML | Qt Quick | A terminal UI can be pure QML chrome around another emulator |
| iTerm2 | Obj-C | Metal | Inline images, shell-integration marks, semantic prompts |
| VTE (GNOME Terminal, Tilix, Terminator) | C / GTK | Cairo | The `vte` widget: mature, but a GTK dependency and no Qt integration |

Benchmarks that shaped the thinking (vizenc/terminal-benchmark, ThinkPad T430,
Hyprland, default configs):

| Metric | Alacritty | foot | Ghostty | Kitty | WezTerm |
|---|---|---|---|---|---|
| Input latency (ms) | 16.7 | 15.0 | 38.3* | 18.3 | 30.8 |
| 11 MB `cat` (ms) | 404 | 251 | 407 | 401 | 1246 |
| DOOM-fire (fps) | 164 | 199 | 135 | 273 | 64 |
| Idle RAM (MB) | 75 | 43 | 174 | 91 | 130 |

\* suspected measurement artifact (GTK under XWayland).

Two conclusions that matter here:

1. **CPU rendering is not a disadvantage for a grid terminal.** foot is the
   fastest on both latency and bulk I/O with no GPU path at all. A terminal
   draws text runs, not a game engine; the win comes from damage tracking, not
   from a GPU pipeline.
2. **Nobody wins on features any more.** Ghostty/Kitty/WezTerm all have tabs,
   splits, graphics protocols and shell integration. The differentiators are
   config style, platform nativity and how the thing integrates with *your*
   desktop.

## What a terminal emulator actually is

Five pieces, in dependency order:

1. **PTY** — `fork` + `setsid` + `TIOCSCTTY`, `TIOCSWINSZ` for size, read the
   master. Pure OS work; Python's `pty` module covers it.
2. **VT parser + screen state** — ECMA-48 / xterm / DEC private modes, SGR,
   scroll regions, alt screen, cursor shapes, wide and combining characters,
   256/truecolor. This is where terminals live or die.
3. **Renderer** — a grid of cells to pixels, with damage tracking.
4. **Input encoder** — Qt key events to the byte sequences the running app
   expects (`xterm-256color`, modifier-encoded arrows/F-keys, bracketed paste,
   mouse reporting).
5. **Chrome** — tabs, splits, scrollback, search, selection, clipboard, URL
   handling, profiles.

Only (2) and (4) are hard to get right, and both have been solved in reusable
C libraries. (5) is exactly what QML is good at, and the suite already has a
visual language for it.

## Options for (2), with the suite's constraints

The installer must resolve every package on **Arch, Debian/Ubuntu, Fedora,
openSUSE, Void and Alpine**. That rules out anything Arch-only, and it rules
out "build from source at install time" (no compiler on the target, no AUR).

| Option | VT correctness | Dependency cost | Verdict |
|---|---|---|---|
| **libvterm** (C, ~0.3.3) | Neovim's `:terminal` parser, xterm + DEC modes, 256/truecolor, OSC 52, reflow, scrollback hooks | `libvterm` is in every family's archive; already installed here | **chosen** |
| pyte (pure Python) | 256 colours, no truecolor, no mouse reporting, slow | `python3-pyte` everywhere | good as a test oracle, not as the renderer |
| libghostty-vt (C API 1.0) | Modern and complete | Not packaged anywhere yet; needs Zig to build | revisit when distros ship it |
| qtermwidget (Konsole core) | Excellent | Qt Widgets only, no PySide6 bindings; would need a C++ shim + build step | rejected |
| qmltermwidget | Konsole core in QML | Arch `extra` only (Qt6 build of a Qt5-era port) | rejected |
| VTE | Excellent | GTK in a Qt app, plus a GTK event loop | rejected |
| Own parser | — | 6–12 months to reach xterm parity | rejected |

`libvterm` also gives us (4) for free: `vterm_keyboard_key` and
`vterm_keyboard_unichar` emit the right sequences for arrows, Home/End, F1–F12,
modifiers, control characters and bracketed paste — no hand-maintained table.

## Probes (all run on this machine, Qt 6.12 / libvterm 0.3.3)

Before committing, every risky assumption was tested. Numbers are real.

### ctypes binding to libvterm works

```
CELL SIZE 40 (matches C: chars[6] + int8 width + pad + uint32 attrs + 2x VTermColor)
cells: 中(20013,w=2) <cont 0xFFFFFFFF> 文(25991,w=2) ... truecolor fg=(10,200,90) reverse=1
```

Three traps found and written into the binding:

- **UTF-8 is off by default.** `vterm_set_utf8(vt, 1)` is mandatory or every
  multibyte character arrives as `byte - 0x80` (`中` became `d`, `8`, `-`).
- **`vterm_keyboard_*` segfaults unless a screen has been obtained.** Obtain the
  screen first, then encode keys.
- **`vterm_obtain_state` must be given a `restype`.** Without it ctypes
  truncates the pointer to 32 bits and `vterm_state_get_cursorpos` crashes the
  process.

### Key encoding is correct out of the box

```
ENTER \r   TAB \t   BS \x7f   ESC \x1b
UP \x1b[A  DOWN \x1b[B  LEFT \x1b[D  RIGHT \x1b[C
shift+up \x1b[1;2B   ctrl+up \x1b[1;5B   shift+tab \x1b[Z
F1 \x1bOP  F5 \x1b[15~  HOME \x1b[H  END \x1b[F
ctrl+a \x01  ctrl+c \x03  ctrl+d \x04  ctrl+space \x00  alt+b \x1bb
```

The `VTermKey` enum is **not** 1-based the way the header reads at a glance:
`ENTER=1, TAB=2, BACKSPACE=3, ESCAPE=4, UP=5 … PAGEDOWN=14, F1=257`. Reading it
off by one turns Tab into `\x7f` and Up into Down.

### Throughput is fine for a shell

```
feed 0.28 MB of SGR-coloured text        -> 12.0 MB/s
read a full 200x50 grid (10,000 cells)   -> 10.6 ms
read a full 80x24 grid (1,920 cells)     -> ~2.0 ms
```

12 MB/s is below Kitty's ~134 MB/s and roughly foot-class for interactive work;
it is not the bottleneck for anything but `yes | cat`. The 10.6 ms full-grid
read is the real constraint, and it is why the renderer caches **runs per row**
and only re-reads rows the damage callback marked.

### Callbacks and scrollback work

```
20 lines into a 5-row screen -> 16 sb_pushline calls, 146 damage rects
OSC 0 / OSC 2 title          -> ('my title', initial=1, final=1)
```

`VTermValue.string` is a `VTermStringFragment` with `size_t` bitfields
(`len:30, initial:1, final:1`); declaring them as `uint32` silently yields
empty titles.

### Python painting inside QML works, end to end

A `QQuickPaintedItem` subclass registers as a QML type and paints a live
`/bin/sh` session (PTY → libvterm → QPainter) with colours, bold, italic,
underline, reverse video, truecolor, CJK, emoji, `ls --color` and a cursor.
The probe image is `docs/probe.png`.

The software-backend render of an 18x78 grid takes ~3 ms, so painting is not the
problem; reading cells is.

## What hyprtk-term takes

| Borrowed | From | How it appears here |
|---|---|---|
| CPU grid rendering with damage tracking | foot | Row-run cache, repaint only dirty rows |
| Embedded emulator core instead of a fork | Ghostty / libghostty | libvterm through ctypes, ~400 lines of binding |
| Deliberate minimal chrome | Alacritty | Tabs and a settings sheet, nothing else |
| Theme-follows-the-wallpaper | (suite requirement) | pywal/bar palette → the 16 ANSI slots |
| Tabs that keep their process | Kitty / GNOME Terminal | One `TerminalView` (own PTY) per tab |
| Bracketed paste, OSC 52, mouse reporting | kitty / foot | Delegated to libvterm, wired to the Qt clipboard |
| Shell title (OSC 0/2) | every modern terminal | Tab label follows the running program |

## Deliberately out of scope

- **GPU rendering.** The probe shows CPU paints a grid in single-digit ms;
  a scene-graph glyph atlas is a rewrite of the renderer for no user-visible
  gain at 80x24.
- **Sixel / Kitty graphics / iTerm2 inline images.** Requires an image pipeline
  and a protocol layer libvterm does not provide. Revisit if it becomes the
  reason to use something else.
- **OSC 8 hyperlinks.** libvterm 0.3.3 has no hyperlink field on the cell, so
  this needs a parallel parser. URL detection over the text is the v0.3 answer.
- **Built-in multiplexer.** Hyprland + tmux already own that; splits arrive as
  a UI feature in v0.3, not as a session server.
- **Ligatures.** QPainter shapes a run at a time, so they appear when the font
  has them; there is no per-cell ligature clamp in v0.1 (it can look wrong in
  sparse runs — tracked in PLAN).
