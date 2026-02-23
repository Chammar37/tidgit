from __future__ import annotations

import curses
from collections import deque
from typing import Deque, Iterable


class DummyWindow:
    """Minimal curses window stub for deterministic tests."""

    def __init__(self, height: int = 40, width: int = 140, inputs: Iterable[object] = ()) -> None:
        self.height = height
        self.width = width
        self.inputs: Deque[object] = deque(inputs)
        self.writes: list[str] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self.height, self.width

    def keypad(self, _enabled: bool) -> None:
        return None

    def erase(self) -> None:
        return None

    def refresh(self) -> None:
        return None

    def addstr(self, *args: object) -> None:
        if len(args) == 1 and isinstance(args[0], str):
            self.writes.append(args[0])
            return
        if len(args) >= 3 and isinstance(args[2], str):
            self.writes.append(args[2])
            return
        self.writes.append("")

    def attron(self, _attr: int) -> None:
        return None

    def attroff(self, _attr: int) -> None:
        return None

    def move(self, _y: int, _x: int) -> None:
        return None

    def get_wch(self) -> object:
        if self.inputs:
            return self.inputs.popleft()
        raise curses.error("no input")
