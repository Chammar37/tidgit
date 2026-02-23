from __future__ import annotations

import curses
import os

import pytest

from tidgit import main as tm


def test_parse_args_version_flag() -> None:
    parsed = tm.parse_args(["--version"])
    assert parsed.version is True


def test_main_version_prints(capsys: pytest.CaptureFixture[str]) -> None:
    rc = tm.main(["--version"])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out.strip() == "tidgit 0.1.0"


def test_main_errors_when_term_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("TERM", raising=False)

    rc = tm.main([])
    captured = capsys.readouterr()

    assert rc == 1
    assert "TERM is not set" in captured.out


def test_main_uses_curses_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", os.environ.get("TERM", "xterm-256color"))

    called: list[object] = []

    def fake_wrapper(func: object) -> int:
        called.append(func)
        return 42

    monkeypatch.setattr(curses, "wrapper", fake_wrapper)
    rc = tm.main([])

    assert rc == 42
    assert len(called) == 1
