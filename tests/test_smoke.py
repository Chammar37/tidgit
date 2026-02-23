from __future__ import annotations

from tidgit.main import parse_ahead_behind, safe_truncate


def test_parse_ahead_behind_simple() -> None:
    assert parse_ahead_behind("main...origin/main [ahead 2]") == (2, 0)


def test_parse_ahead_behind_mixed() -> None:
    assert parse_ahead_behind("main...origin/main [ahead 1, behind 3]") == (1, 3)


def test_safe_truncate_keeps_short() -> None:
    assert safe_truncate("abc", 4) == "abc"


def test_safe_truncate_ellipsizes() -> None:
    assert safe_truncate("abcdef", 4) == "abc…"
