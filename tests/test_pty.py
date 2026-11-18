"""The PTY: spawn, read, write, resize, reap.

These spawn real children (``/bin/sh``), so they are the slowest tests here --
still milliseconds.
"""

from __future__ import annotations

import fcntl
import os
import struct
import sys
import termios
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyprtk_term.ptyproc import Pty, PtyError, default_argv  # noqa: E402


def wait_for(pty: Pty, needle: bytes, timeout: float = 3.0) -> bytes:
    out = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        chunk = pty.read()
        if chunk:
            out += chunk
            if needle in out:
                return out
        elif pty.poll() is not None:
            break
        else:
            time.sleep(0.01)
    return out


class Spawn(unittest.TestCase):
    def test_output_is_readable(self):
        p = Pty(["/bin/sh", "-c", "printf hello"])
        try:
            self.assertIn(b"hello", wait_for(p, b"hello"))
        finally:
            p.close()

    def test_exit_status(self):
        p = Pty(["/bin/sh", "-c", "exit 7"])
        try:
            deadline = time.time() + 3
            while p.poll() is None and time.time() < deadline:
                time.sleep(0.01)
            self.assertEqual(p.poll(), 7)
        finally:
            p.close()

    def test_missing_command_exits_127(self):
        p = Pty(["/definitely/not/here"])
        try:
            deadline = time.time() + 3
            while p.poll() is None and time.time() < deadline:
                time.sleep(0.01)
            self.assertEqual(p.poll(), 127)
        finally:
            p.close()

    def test_input_reaches_the_child(self):
        p = Pty(["/bin/cat"])
        try:
            p.write(b"ping\n")
            self.assertIn(b"ping", wait_for(p, b"ping"))
        finally:
            p.terminate()
            p.close()

    def test_empty_command_is_rejected(self):
        with self.assertRaises(PtyError):
            Pty([])


class Sizing(unittest.TestCase):
    def test_winsize_is_applied(self):
        p = Pty(["/bin/cat"], rows=30, cols=100)
        try:
            packed = fcntl.ioctl(p.fd, termios.TIOCGWINSZ, b"\0" * 8)
            rows, cols, _, _ = struct.unpack("HHHH", packed)
            self.assertEqual((rows, cols), (30, 100))
        finally:
            p.terminate()
            p.close()

    def test_resize_updates_winsize(self):
        p = Pty(["/bin/cat"], rows=10, cols=20)
        try:
            p.resize(40, 120)
            rows, cols, _, _ = struct.unpack(
                "HHHH", fcntl.ioctl(p.fd, termios.TIOCGWINSZ, b"\0" * 8))
            self.assertEqual((rows, cols), (40, 120))
        finally:
            p.terminate()
            p.close()


class Environment(unittest.TestCase):
    def test_term_is_set(self):
        p = Pty(["/bin/sh", "-c", "printf '%s' \"$TERM\""])
        try:
            self.assertIn(b"xterm-256color", wait_for(p, b"256color"))
        finally:
            p.close()

    def test_extra_env_is_passed(self):
        p = Pty(["/bin/sh", "-c", "printf '%s' \"$HYPRTK_TEST\""],
                env={"HYPRTK_TEST": "suite"})
        try:
            self.assertIn(b"suite", wait_for(p, b"suite"))
        finally:
            p.close()

    def test_cwd_is_honoured(self):
        p = Pty(["/bin/sh", "-c", "pwd"], cwd="/tmp")
        try:
            self.assertIn(b"/tmp", wait_for(p, b"/tmp"))
        finally:
            p.close()


class ShellChoice(unittest.TestCase):
    def test_login_flag_for_known_shells(self):
        self.assertEqual(default_argv("/bin/bash"), ["/bin/bash", "-l"])
        self.assertEqual(default_argv("/usr/bin/zsh"), ["/usr/bin/zsh", "-l"])

    def test_unknown_shell_gets_no_flag(self):
        self.assertEqual(default_argv("/bin/nu"), ["/bin/nu"])

    def test_falls_back_to_env_shell(self):
        os.environ.setdefault("SHELL", "/bin/sh")
        self.assertTrue(default_argv()[0].endswith(("sh", "bash", "zsh", "fish")))


if __name__ == "__main__":
    unittest.main()
