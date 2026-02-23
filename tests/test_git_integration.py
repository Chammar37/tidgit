from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.helpers import DummyWindow
from tidgit import main as tm


def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.stdout.strip()


def init_repo(path: Path) -> None:
    git(path, "init")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test User")


def test_is_git_repo_detects_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)

    monkeypatch.chdir(tmp_path)
    assert tm.is_git_repo() is False

    monkeypatch.chdir(repo)
    assert tm.is_git_repo() is True


def test_stage_unstage_and_commit_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)

    tracked = repo / "tracked.txt"
    tracked.write_text("line1\n", encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "initial")

    tracked.write_text("line1\nline2\n", encoding="utf-8")

    monkeypatch.chdir(repo)
    app = tm.TidGitApp(DummyWindow())
    app.refresh_data()

    idx = next(i for i, entry in enumerate(app.entries) if entry.path == "tracked.txt")
    app.selected = idx

    app.stage_selected()
    assert any(entry.path == "tracked.txt" and entry.staged for entry in app.entries)

    app.unstage_selected()
    assert any(entry.path == "tracked.txt" and entry.unstaged for entry in app.entries)

    app.stage_selected()
    monkeypatch.setattr(app, "input_prompt", lambda _title: "second")
    app.commit_prompt()
    app.refresh_data()

    assert app.entries == []
    assert git(repo, "rev-list", "--count", "HEAD") == "2"


def test_ahead_count_drives_push_primary_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    remote.mkdir()
    work.mkdir()

    git(remote, "init", "--bare")
    init_repo(work)

    tracked = work / "tracked.txt"
    tracked.write_text("v1\n", encoding="utf-8")
    git(work, "add", "tracked.txt")
    git(work, "commit", "-m", "initial")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "-u", "origin", "HEAD")

    tracked.write_text("v1\nv2\n", encoding="utf-8")
    git(work, "add", "tracked.txt")
    git(work, "commit", "-m", "ahead")

    monkeypatch.chdir(work)
    app = tm.TidGitApp(DummyWindow())
    app.refresh_data()

    assert app.ahead_count == 1
    assert app.primary_action_name() == "push"
