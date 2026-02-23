from __future__ import annotations

import curses
from collections.abc import Sequence

import pytest

from tests.helpers import DummyWindow
from tidgit import main as tm


def make_entry(
    path: str,
    *,
    staged: bool = False,
    unstaged: bool = False,
    untracked: bool = False,
    conflict: bool = False,
    x: str = " ",
    y: str = " ",
) -> tm.FileEntry:
    return tm.FileEntry(
        path=path,
        x=x,
        y=y,
        staged=staged,
        unstaged=unstaged,
        untracked=untracked,
        conflict=conflict,
    )


def test_primary_action_name_prefers_commit_when_staged() -> None:
    app = tm.TidGitApp(DummyWindow())
    app.entries = [make_entry("a.txt", staged=True, x="M")]
    app.ahead_count = 5
    assert app.primary_action_name() == "commit"


def test_primary_action_name_push_when_ahead_and_no_staged() -> None:
    app = tm.TidGitApp(DummyWindow())
    app.entries = []
    app.ahead_count = 2
    assert app.primary_action_name() == "push"


def test_primary_action_name_prefers_commit_when_working_tree_dirty_even_if_ahead() -> None:
    app = tm.TidGitApp(DummyWindow())
    app.entries = [make_entry("a.txt", unstaged=True, y="M")]
    app.ahead_count = 2
    assert app.primary_action_name() == "commit"


def test_run_primary_action_commit_path(monkeypatch: pytest.MonkeyPatch) -> None:
    app = tm.TidGitApp(DummyWindow())
    app.entries = [make_entry("a.txt", staged=True, x="M")]

    called: list[str] = []
    monkeypatch.setattr(app, "commit_prompt", lambda: called.append("commit"))
    monkeypatch.setattr(app, "push", lambda: called.append("push"))

    app.run_primary_action()
    assert called == ["commit"]


def test_run_primary_action_push_path(monkeypatch: pytest.MonkeyPatch) -> None:
    app = tm.TidGitApp(DummyWindow())
    app.entries = []
    app.ahead_count = 1

    called: list[str] = []
    monkeypatch.setattr(app, "commit_prompt", lambda: called.append("commit"))
    monkeypatch.setattr(app, "push", lambda: called.append("push"))

    app.run_primary_action()
    assert called == ["push"]


def test_run_primary_action_uses_commit_all_for_unstaged_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    app = tm.TidGitApp(DummyWindow())
    app.entries = [make_entry("a.txt", unstaged=True, y="M")]
    app.ahead_count = 0

    called: list[str] = []
    monkeypatch.setattr(app, "commit_prompt", lambda: called.append("commit"))
    monkeypatch.setattr(app, "commit_all_prompt", lambda: called.append("commit_all"))
    monkeypatch.setattr(app, "push", lambda: called.append("push"))

    app.run_primary_action()

    assert called == ["commit_all"]


def test_run_primary_action_errors_without_changes_or_ahead() -> None:
    app = tm.TidGitApp(DummyWindow())
    app.entries = []
    app.ahead_count = 0

    app.run_primary_action()

    assert app.status_is_error is True
    assert app.status_text == "No changes to commit."


def test_toggle_preview_mode_switches_when_both_staged_and_unstaged() -> None:
    app = tm.TidGitApp(DummyWindow())
    app.entries = [make_entry("a.txt", staged=True, unstaged=True, x="M", y="M")]
    app.selected = 0

    assert app.current_preview_mode(app.entries[0]) == "unstaged"
    app.toggle_preview_mode()
    assert app.current_preview_mode(app.entries[0]) == "staged"


def test_diff_lines_for_entry_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    app = tm.TidGitApp(DummyWindow())
    entry = make_entry("a.txt", unstaged=True, y="M")

    calls: list[list[str]] = []

    def fake_run_cmd(args: Sequence[str]) -> tuple[int, str, str]:
        calls.append(list(args))
        return 0, "line1\nline2\n", ""

    monkeypatch.setattr(tm, "run_cmd", fake_run_cmd)

    first = app.diff_lines_for_entry(entry)
    second = app.diff_lines_for_entry(entry)

    assert first == ["line1", "line2"]
    assert second == ["line1", "line2"]
    assert calls == [["git", "--no-pager", "diff", "--", "a.txt"]]


def test_stage_selected_calls_git_action(monkeypatch: pytest.MonkeyPatch) -> None:
    app = tm.TidGitApp(DummyWindow())
    app.entries = [make_entry("a.txt", unstaged=True, y="M")]
    app.selected = 0

    observed: list[tuple[list[str], str, str]] = []

    def fake_run_git_action(args: Sequence[str], ok_text: str, err_prefix: str) -> bool:
        observed.append((list(args), ok_text, err_prefix))
        return True

    monkeypatch.setattr(app, "run_git_action", fake_run_git_action)
    app.stage_selected()

    assert observed == [(["add", "--", "a.txt"], "Staged a.txt", "Stage failed")]


def test_unstage_selected_uses_restore_then_reset_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    app = tm.TidGitApp(DummyWindow())
    app.entries = [make_entry("a.txt", staged=True, x="M")]
    app.selected = 0

    observed: list[list[str]] = []

    def fake_run_git_action(args: Sequence[str], _ok_text: str, _err_prefix: str) -> bool:
        observed.append(list(args))
        return len(observed) > 1

    monkeypatch.setattr(app, "run_git_action", fake_run_git_action)
    app.unstage_selected()

    assert observed == [
        ["restore", "--staged", "--", "a.txt"],
        ["reset", "HEAD", "--", "a.txt"],
    ]


def test_input_prompt_handles_backspace_and_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    window = DummyWindow(inputs=["h", "i", "\b", "o", "\n"])
    app = tm.TidGitApp(window)

    monkeypatch.setattr(app, "draw", lambda: None)
    monkeypatch.setattr(tm, "try_set_cursor", lambda _visibility: None)

    assert app.input_prompt("Commit message") == "ho"


def test_input_prompt_accepts_key_enter(monkeypatch: pytest.MonkeyPatch) -> None:
    window = DummyWindow(inputs=["o", "k", curses.KEY_ENTER])
    app = tm.TidGitApp(window)

    monkeypatch.setattr(app, "draw", lambda: None)
    monkeypatch.setattr(tm, "try_set_cursor", lambda _visibility: None)

    assert app.input_prompt("Commit message") == "ok"


def test_input_prompt_accepts_int_newline_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    for enter_code in (10, 13):
        window = DummyWindow(inputs=["o", "k", enter_code])
        app = tm.TidGitApp(window)

        monkeypatch.setattr(app, "draw", lambda: None)
        monkeypatch.setattr(tm, "try_set_cursor", lambda _visibility: None)

        assert app.input_prompt("Commit message") == "ok"


def test_input_prompt_ctrl_r_triggers_hard_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    window = DummyWindow(inputs=["\x12", "\n"])
    app = tm.TidGitApp(window)

    calls: list[str] = []
    monkeypatch.setattr(app, "draw", lambda: None)
    monkeypatch.setattr(app, "hard_refresh", lambda: calls.append("hard_refresh"))
    monkeypatch.setattr(tm, "try_set_cursor", lambda _visibility: None)

    assert app.input_prompt("Commit message") == ""
    assert calls == ["hard_refresh"]


def test_commit_prompt_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    app = tm.TidGitApp(DummyWindow())
    monkeypatch.setattr(app, "input_prompt", lambda _title: None)

    app.commit_prompt()

    assert app.status_text == "Commit canceled."


def test_commit_prompt_empty_message(monkeypatch: pytest.MonkeyPatch) -> None:
    app = tm.TidGitApp(DummyWindow())
    monkeypatch.setattr(app, "input_prompt", lambda _title: "   ")

    app.commit_prompt()

    assert app.status_is_error is True
    assert app.status_text == "Commit message cannot be empty."


def test_commit_all_prompt_stages_then_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    app = tm.TidGitApp(DummyWindow())
    monkeypatch.setattr(app, "input_prompt", lambda _title: "message")

    observed: list[list[str]] = []

    def fake_run_git_action(args: Sequence[str], _ok_text: str, _err_prefix: str) -> bool:
        observed.append(list(args))
        return True

    monkeypatch.setattr(app, "run_git_action", fake_run_git_action)
    app.commit_all_prompt()

    assert observed == [["add", "-A"], ["commit", "-m", "message"]]


def test_hard_refresh_resets_ui_state(monkeypatch: pytest.MonkeyPatch) -> None:
    app = tm.TidGitApp(DummyWindow())
    monkeypatch.setattr(app, "pending_focus", ("staged", "a.txt"))
    app.preview_scroll = 5
    app.changes_scroll = 4
    app.staged_scroll = 3
    app.modal_title = "Modal"
    app.modal_lines = ["line"]
    app.modal_scroll = 2
    app.preview_mode = {"a.txt": "staged"}
    app.repo_error = None

    calls: list[str] = []
    monkeypatch.setattr(tm, "is_git_repo", lambda: False)
    monkeypatch.setattr(app, "refresh_data", lambda: calls.append("refresh"))

    app.hard_refresh()

    assert calls == ["refresh"]
    assert app.pending_focus is None
    assert app.preview_scroll == 0
    assert app.changes_scroll == 0
    assert app.staged_scroll == 0
    assert app.preview_mode == {}
    assert app.modal_title == ""
    assert app.modal_lines == []
    assert app.modal_scroll == 0
    assert app.status_text == "Hard refreshed"
