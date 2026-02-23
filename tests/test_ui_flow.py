from __future__ import annotations

import curses

import pytest

from tests.helpers import DummyWindow
from tidgit import main as tm


def test_draw_handles_small_terminal() -> None:
    window = DummyWindow(height=8, width=30)
    app = tm.TidGitApp(window)

    app.draw()

    assert any("Resize terminal" in text for text in window.writes)


def test_draw_renders_with_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    window = DummyWindow(height=30, width=120)
    app = tm.TidGitApp(window)
    app.repo_error = None
    app.entries = [
        tm.FileEntry(
            path="a.txt",
            x="M",
            y="M",
            staged=True,
            unstaged=True,
            untracked=False,
            conflict=False,
        )
    ]
    app.selected = 0

    monkeypatch.setattr(app, "diff_lines_for_entry", lambda _entry: ["+new", "-old"])  # no git call

    app.draw()

    rendered = "\n".join(window.writes)
    assert "CHANGES" in rendered
    assert "preview" in rendered.lower()


def test_run_loop_quits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    window = DummyWindow(inputs=["q"])
    app = tm.TidGitApp(window)

    monkeypatch.setattr(curses, "start_color", lambda: None)
    monkeypatch.setattr(curses, "use_default_colors", lambda: None)
    monkeypatch.setattr(curses, "init_pair", lambda _pid, _fg, _bg: None)
    monkeypatch.setattr(tm, "try_set_cursor", lambda _visibility: None)

    def fake_refresh_data(keep_selection: bool = True) -> None:
        del keep_selection
        app.repo_error = None
        app.entries = []

    monkeypatch.setattr(app, "refresh_data", fake_refresh_data)

    assert app.run() == 0


def test_run_loop_focus_switch_and_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    window = DummyWindow(inputs=[curses.KEY_RIGHT, curses.KEY_LEFT, "s", "q"])
    app = tm.TidGitApp(window)

    monkeypatch.setattr(curses, "start_color", lambda: None)
    monkeypatch.setattr(curses, "use_default_colors", lambda: None)
    monkeypatch.setattr(curses, "init_pair", lambda _pid, _fg, _bg: None)
    monkeypatch.setattr(tm, "try_set_cursor", lambda _visibility: None)

    def fake_refresh_data(keep_selection: bool = True) -> None:
        del keep_selection
        app.repo_error = None
        app.entries = [
            tm.FileEntry(
                path="a.txt",
                x=" ",
                y="M",
                staged=False,
                unstaged=True,
                untracked=False,
                conflict=False,
            )
        ]
        app.selected = 0

    calls: list[str] = []
    monkeypatch.setattr(app, "refresh_data", fake_refresh_data)
    monkeypatch.setattr(app, "diff_lines_for_entry", lambda _entry: ["+line"])
    monkeypatch.setattr(app, "stage_selected", lambda: calls.append("stage"))

    assert app.run() == 0
    assert calls == ["stage"]
    assert app.status_text == "Focus: changes"


def test_run_loop_uses_hard_refresh_for_r(monkeypatch: pytest.MonkeyPatch) -> None:
    window = DummyWindow(inputs=["r", "q"])
    app = tm.TidGitApp(window)

    monkeypatch.setattr(curses, "start_color", lambda: None)
    monkeypatch.setattr(curses, "use_default_colors", lambda: None)
    monkeypatch.setattr(curses, "init_pair", lambda _pid, _fg, _bg: None)
    monkeypatch.setattr(tm, "try_set_cursor", lambda _visibility: None)
    monkeypatch.setattr(app, "refresh_data", lambda keep_selection=False: setattr(app, "repo_error", None))

    calls: list[str] = []
    monkeypatch.setattr(app, "hard_refresh", lambda: calls.append("hard_refresh"))

    assert app.run() == 0
    assert calls == ["hard_refresh"]


def test_left_panel_splits_and_scrolls_both_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    window = DummyWindow(height=22, width=120)
    app = tm.TidGitApp(window)
    app.repo_error = None
    app.entries = [
        tm.FileEntry(
            path=f"c{i:02d}.txt",
            x=" ",
            y="M",
            staged=False,
            unstaged=True,
            untracked=False,
            conflict=False,
        )
        for i in range(12)
    ] + [
        tm.FileEntry(
            path=f"s{i:02d}.txt",
            x="M",
            y=" ",
            staged=True,
            unstaged=False,
            untracked=False,
            conflict=False,
        )
        for i in range(12)
    ]

    monkeypatch.setattr(app, "diff_lines_for_entry", lambda _entry: ["+line"])

    app.selected = len([e for e in app.entries if e.unstaged]) + 9
    app.draw()
    assert app.staged_scroll > 0
    rendered = "\n".join(window.writes)
    assert "CHANGES" in rendered
    assert "STAGED" in rendered

    window.writes.clear()
    app.selected = 9
    app.draw()
    assert app.changes_scroll > 0


def test_modal_has_explicit_modal_text() -> None:
    window = DummyWindow(height=30, width=120)
    app = tm.TidGitApp(window)
    app.repo_error = None
    app.entries = []
    app.modal_title = " Recent Commits [MODAL] "
    app.modal_lines = ["abc123 Initial commit"]

    app.draw()

    rendered = "\n".join(window.writes)
    assert "Recent Commits [MODAL]" in rendered
    assert "modal focus locked" in rendered
