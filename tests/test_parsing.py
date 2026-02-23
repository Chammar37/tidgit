from __future__ import annotations

from collections.abc import Sequence

import pytest

from tidgit import main as tm


def test_parse_status_porcelain_parses_and_sorts(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = "\n".join(
        [
            "## main...origin/main [ahead 1, behind 2]",
            " M unstaged.txt",
            "M  staged.txt",
            "MM both.txt",
            "?? new.txt",
            "UU conflicted.txt",
            "R  old.txt -> renamed.txt",
        ]
    )

    def fake_run_cmd(_args: Sequence[str]) -> tuple[int, str, str]:
        return 0, sample, ""

    monkeypatch.setattr(tm, "run_cmd", fake_run_cmd)
    branch, entries, err = tm.parse_status_porcelain()

    assert err is None
    assert branch == "main...origin/main [ahead 1, behind 2]"
    assert [entry.path for entry in entries] == [
        "conflicted.txt",
        "both.txt",
        "new.txt",
        "unstaged.txt",
        "renamed.txt",
        "staged.txt",
    ]

    renamed = next(item for item in entries if item.path == "renamed.txt")
    assert renamed.staged is True
    assert renamed.unstaged is False

    conflict = entries[0]
    assert conflict.conflict is True


def test_parse_status_porcelain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_cmd(_args: Sequence[str]) -> tuple[int, str, str]:
        return 128, "", "fatal: not a git repository"

    monkeypatch.setattr(tm, "run_cmd", fake_run_cmd)
    branch, entries, err = tm.parse_status_porcelain()

    assert branch == ""
    assert entries == []
    assert err == "fatal: not a git repository"


@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("main...origin/main [ahead 3]", (3, 0)),
        ("main...origin/main [behind 4]", (0, 4)),
        ("main...origin/main [ahead 2, behind 5]", (2, 5)),
        ("main", (0, 0)),
    ],
)
def test_parse_ahead_behind(branch: str, expected: tuple[int, int]) -> None:
    assert tm.parse_ahead_behind(branch) == expected


@pytest.mark.parametrize(
    ("text", "width", "expected"),
    [
        ("abc", 3, "abc"),
        ("abcdef", 4, "abc…"),
        ("abcdef", 1, "a"),
        ("abcdef", 0, ""),
    ],
)
def test_safe_truncate(text: str, width: int, expected: str) -> None:
    assert tm.safe_truncate(text, width) == expected
