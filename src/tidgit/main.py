#!/usr/bin/env python3
"""
tidgit: a minimal git TUI focused on core actions and visual clarity.

Keybindings:
  Up/Down or j/k   Move selection
  Left/Right       Move focus between changes and preview panes
  Enter            Focus preview pane for selected file
  s                Stage selected file
  u                Unstage selected file
  c                Commit (prompt for message)
  p                Pull --rebase
  P                Push
  l                Show recent log
  r                Hard refresh
  n/b              Scroll preview down/up
  q                Quit
"""

from __future__ import annotations

import argparse
import curses
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

APP_NAME = "tidgit"
APP_VERSION = "0.1.0"
DEFAULT_CMD_TIMEOUT_SECONDS = 45


@dataclass
class FileEntry:
    path: str
    x: str
    y: str
    staged: bool
    unstaged: bool
    untracked: bool
    conflict: bool


@dataclass
class DisplayRow:
    section: str
    entry: FileEntry


def run_cmd(args: Sequence[str]) -> Tuple[int, str, str]:
    try:
        timeout_seconds = max(5, int(os.environ.get("TIDGIT_CMD_TIMEOUT_SECONDS", str(DEFAULT_CMD_TIMEOUT_SECONDS))))
    except ValueError:
        timeout_seconds = DEFAULT_CMD_TIMEOUT_SECONDS

    env = os.environ.copy()
    # Avoid hidden credential/GPG prompts freezing the curses UI.
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GCM_INTERACTIVE", "Never")
    try:
        proc = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=env,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        out = exc.output if isinstance(exc.output, str) else ""
        err = exc.stderr if isinstance(exc.stderr, str) else ""
        timeout_msg = f"Command timed out after {timeout_seconds}s: {' '.join(args)}"
        details = "\n".join(part for part in (timeout_msg, err.strip()) if part)
        return 124, out, details


def is_git_repo() -> bool:
    code, out, _ = run_cmd(["git", "rev-parse", "--is-inside-work-tree"])
    return code == 0 and out.strip() == "true"


def parse_status_porcelain() -> Tuple[str, List[FileEntry], Optional[str]]:
    code, out, err = run_cmd(["git", "status", "--porcelain=v1", "--branch"])
    if code != 0:
        return "", [], err.strip() or "Failed to read git status."

    branch = ""
    entries: List[FileEntry] = []
    for raw in out.splitlines():
        if raw.startswith("## "):
            branch = raw[3:].strip()
            continue
        if len(raw) < 4:
            continue
        x = raw[0]
        y = raw[1]
        path = raw[3:]
        if " -> " in path:
            _, path = path.split(" -> ", 1)

        conflict = x == "U" or y == "U" or (x == "A" and y == "A") or (x == "D" and y == "D")
        untracked = x == "?" and y == "?"
        staged = not untracked and x not in (" ", "?")
        unstaged = y not in (" ", "?")

        entries.append(
            FileEntry(
                path=path,
                x=x,
                y=y,
                staged=staged,
                unstaged=unstaged,
                untracked=untracked,
                conflict=conflict,
            )
        )

    entries.sort(key=lambda e: (0 if e.conflict else 1 if (e.unstaged or e.untracked) else 2, e.path.lower()))
    return branch, entries, None


def parse_ahead_behind(branch: str) -> Tuple[int, int]:
    ahead = 0
    behind = 0
    m = re.search(r"\[([^\]]+)\]", branch)
    if not m:
        return ahead, behind
    for part in m.group(1).split(","):
        piece = part.strip()
        if piece.startswith("ahead "):
            try:
                ahead = int(piece.split()[1])
            except (ValueError, IndexError):
                pass
        elif piece.startswith("behind "):
            try:
                behind = int(piece.split()[1])
            except (ValueError, IndexError):
                pass
    return ahead, behind


def safe_truncate(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def try_set_cursor(visibility: int) -> None:
    try:
        curses.curs_set(visibility)
    except curses.error:
        pass


def safe_color_pair(pair_id: int) -> int:
    try:
        return curses.color_pair(pair_id)
    except Exception:
        return 0


def is_enter_key(ch: object) -> bool:
    # Different terminals/curses builds can emit Enter as "\n", "\r",
    # KEY_ENTER, or raw integer codes.
    return ch in ("\n", "\r", curses.KEY_ENTER, 10, 13)


class TidGitApp:
    def __init__(self, stdscr: Any) -> None:
        self.stdscr = stdscr
        self.branch = ""
        self.entries: List[FileEntry] = []
        self.selected = 0
        self.changes_scroll = 0
        self.staged_scroll = 0
        self.preview_scroll = 0
        self.preview_cache: Dict[Tuple[str, str], List[str]] = {}
        self.preview_mode: Dict[str, str] = {}
        self.active_pane = "changes"
        self.pending_focus: Optional[Tuple[str, str]] = None
        self.ahead_count = 0
        self.behind_count = 0
        self.status_text = "Ready"
        self.status_is_error = False
        self.modal_title = ""
        self.modal_lines: List[str] = []
        self.modal_scroll = 0
        self.repo_error: Optional[str] = None

    def set_status(self, text: str, error: bool = False) -> None:
        self.status_text = text
        self.status_is_error = error

    def clear_preview_cache(self) -> None:
        self.preview_cache.clear()

    def hard_refresh(self) -> None:
        # Force curses to redraw and clear in-memory UI state so users can recover
        # quickly from odd rendering/input states.
        self.pending_focus = None
        self.preview_scroll = 0
        self.changes_scroll = 0
        self.staged_scroll = 0
        self.preview_mode.clear()
        self.clear_preview_cache()
        self.close_modal()

        if is_git_repo():
            run_cmd(["git", "update-index", "-q", "--refresh"])
        self.refresh_data()

        try:
            self.stdscr.erase()
            self.stdscr.refresh()
        except curses.error:
            pass

        if self.repo_error:
            self.set_status(self.repo_error, error=True)
        else:
            self.set_status("Hard refreshed")

    def refresh_data(self, keep_selection: bool = True) -> None:
        if not is_git_repo():
            self.branch = ""
            self.ahead_count = 0
            self.behind_count = 0
            self.entries = []
            self.repo_error = "Not inside a git repository."
            self.selected = 0
            self.changes_scroll = 0
            self.staged_scroll = 0
            self.preview_scroll = 0
            self.clear_preview_cache()
            return

        self.repo_error = None
        old_row = self.current_row() if keep_selection else None
        old_key = (old_row.section, old_row.entry.path) if old_row else None
        branch, entries, err = parse_status_porcelain()
        if err:
            self.branch = ""
            self.ahead_count = 0
            self.behind_count = 0
            self.entries = []
            self.repo_error = err
            self.selected = 0
            self.changes_scroll = 0
            self.staged_scroll = 0
            self.preview_scroll = 0
            self.clear_preview_cache()
            return

        self.branch = branch
        self.ahead_count, self.behind_count = parse_ahead_behind(branch)
        self.entries = entries

        display_rows = self.display_rows()
        pending_key = self.pending_focus
        self.pending_focus = None
        if pending_key:
            idx = next((i for i, row in enumerate(display_rows) if (row.section, row.entry.path) == pending_key), None)
            if idx is not None:
                self.selected = idx
            elif old_key:
                idx = next((i for i, row in enumerate(display_rows) if (row.section, row.entry.path) == old_key), 0)
                self.selected = idx
            else:
                self.selected = min(self.selected, max(len(display_rows) - 1, 0))
        elif old_key:
            idx = next((i for i, row in enumerate(display_rows) if (row.section, row.entry.path) == old_key), 0)
            self.selected = idx
        else:
            self.selected = min(self.selected, max(len(display_rows) - 1, 0))

        self.preview_scroll = 0
        self.clear_preview_cache()

    def display_rows(self) -> List[DisplayRow]:
        changes = [entry for entry in self.entries if entry.unstaged or entry.untracked or entry.conflict]
        staged = [entry for entry in self.entries if entry.staged]
        changes.sort(key=lambda entry: entry.path.lower())
        staged.sort(key=lambda entry: entry.path.lower())

        rows = [DisplayRow(section="changes", entry=entry) for entry in changes]
        rows.extend(DisplayRow(section="staged", entry=entry) for entry in staged)
        return rows

    def current_row(self) -> Optional[DisplayRow]:
        rows = self.display_rows()
        if not rows:
            return None
        if self.selected < 0:
            self.selected = 0
        if self.selected >= len(rows):
            self.selected = len(rows) - 1
        return rows[self.selected]

    def current_entry(self) -> Optional[FileEntry]:
        row = self.current_row()
        if not row:
            return None
        return row.entry

    def current_section(self) -> str:
        row = self.current_row()
        if not row:
            return "changes"
        return row.section

    def has_staged_changes(self) -> bool:
        return any(entry.staged for entry in self.entries)

    def has_working_tree_changes(self) -> bool:
        return any(entry.unstaged or entry.untracked or entry.conflict for entry in self.entries)

    def primary_action_name(self) -> str:
        if self.has_staged_changes() or self.has_working_tree_changes():
            return "commit"
        if self.ahead_count > 0:
            return "push"
        return "commit"

    def run_primary_action(self) -> None:
        action = self.primary_action_name()
        if action == "push":
            self.push()
            return
        if self.has_staged_changes():
            self.commit_prompt()
            return
        if self.has_working_tree_changes():
            self.commit_all_prompt()
            return
        self.set_status("No changes to commit.", error=True)

    def current_preview_mode(self, entry: FileEntry) -> str:
        if entry.path not in self.preview_mode:
            if entry.unstaged or entry.untracked:
                self.preview_mode[entry.path] = "unstaged"
            elif entry.staged:
                self.preview_mode[entry.path] = "staged"
            else:
                self.preview_mode[entry.path] = "unstaged"
        mode = self.preview_mode[entry.path]
        if mode == "staged" and not entry.staged:
            mode = "unstaged"
        if mode == "unstaged" and not (entry.unstaged or entry.untracked):
            mode = "staged"
        self.preview_mode[entry.path] = mode
        return mode

    def toggle_preview_mode(self) -> None:
        entry = self.current_entry()
        if not entry:
            return
        if not (entry.staged and (entry.unstaged or entry.untracked)):
            return
        mode = self.current_preview_mode(entry)
        self.preview_mode[entry.path] = "staged" if mode == "unstaged" else "unstaged"
        self.preview_scroll = 0

    def diff_lines_for_entry(self, entry: FileEntry) -> List[str]:
        mode = self.current_preview_mode(entry)
        key = (entry.path, mode)
        if key in self.preview_cache:
            return self.preview_cache[key]

        if mode == "staged":
            code, out, err = run_cmd(["git", "--no-pager", "diff", "--cached", "--", entry.path])
        elif entry.untracked:
            code, out, err = run_cmd(["git", "--no-pager", "diff", "--no-index", "--", "/dev/null", entry.path])
        else:
            code, out, err = run_cmd(["git", "--no-pager", "diff", "--", entry.path])

        if code not in (0, 1):
            lines = [f"(Unable to render diff: {err.strip() or 'unknown error'})"]
        else:
            text = out.strip("\n")
            lines = text.splitlines() if text else ["(No diff output)"]

        self.preview_cache[key] = lines
        return lines

    def run_git_action(self, args: Sequence[str], ok_text: str, err_prefix: str) -> bool:
        code, out, err = run_cmd(["git", *args])
        if code == 0:
            msg = out.strip() or ok_text
            self.set_status(msg, error=False)
            self.refresh_data()
            return True
        details = err.strip() or out.strip() or "unknown error"
        self.set_status(f"{err_prefix}: {details}", error=True)
        return False

    def stage_selected(self) -> None:
        entry = self.current_entry()
        if not entry:
            self.set_status("Nothing selected.", error=True)
            return
        if not (entry.unstaged or entry.untracked):
            self.set_status("Selected file has nothing to stage.", error=True)
            return
        self.pending_focus = ("staged", entry.path)
        ok = self.run_git_action(["add", "--", entry.path], f"Staged {entry.path}", "Stage failed")
        if not ok:
            self.pending_focus = None

    def unstage_selected(self) -> None:
        entry = self.current_entry()
        if not entry:
            self.set_status("Nothing selected.", error=True)
            return
        if not entry.staged:
            self.set_status("Selected file has nothing staged.", error=True)
            return
        self.pending_focus = ("changes", entry.path)
        ok = self.run_git_action(["restore", "--staged", "--", entry.path], f"Unstaged {entry.path}", "Unstage failed")
        if not ok:
            fallback_ok = self.run_git_action(["reset", "HEAD", "--", entry.path], f"Unstaged {entry.path}", "Unstage fallback failed")
            if not fallback_ok:
                self.pending_focus = None

    def pull_rebase(self) -> None:
        self.run_git_action(["pull", "--rebase"], "Pull completed", "Pull failed")

    def push(self) -> None:
        self.run_git_action(["push"], "Push completed", "Push failed")

    def commit_prompt(self) -> None:
        msg = self.input_prompt("Commit message")
        if msg is None:
            self.set_status("Commit canceled.")
            return
        if not msg.strip():
            self.set_status("Commit message cannot be empty.", error=True)
            return
        self.run_git_action(["commit", "-m", msg.strip()], "Commit created", "Commit failed")

    def commit_all_prompt(self) -> None:
        msg = self.input_prompt("Commit message")
        if msg is None:
            self.set_status("Commit canceled.")
            return
        if not msg.strip():
            self.set_status("Commit message cannot be empty.", error=True)
            return
        if not self.run_git_action(["add", "-A"], "Staged all changes", "Stage-all failed"):
            return
        self.run_git_action(["commit", "-m", msg.strip()], "Commit created", "Commit failed")

    def show_log_modal(self) -> None:
        code, out, err = run_cmd(["git", "--no-pager", "log", "--oneline", "--decorate", "-n", "30"])
        if code != 0:
            self.set_status(f"Log failed: {err.strip() or 'unknown error'}", error=True)
            return
        self.modal_title = " Recent Commits [MODAL] "
        self.modal_lines = out.splitlines() if out.strip() else ["(No commits found)"]
        self.modal_scroll = 0
        self.set_status("Log modal open. Press q or Esc to close.")

    def input_prompt(self, title: str) -> Optional[str]:
        buf: List[str] = []
        try_set_cursor(1)
        while True:
            try:
                self.draw()
                h, w = self.stdscr.getmaxyx()
                prompt = f"{title} (Enter submit · Esc cancel · Ctrl+R refresh): "
                value = "".join(buf)
                line = safe_truncate(prompt + value, w - 1)
                self.stdscr.attron(safe_color_pair(4))
                self.stdscr.addstr(h - 1, 0, " " * max(0, w - 1))
                self.stdscr.addstr(h - 1, 0, line)
                self.stdscr.attroff(safe_color_pair(4))

                cursor_x = min(len(prompt) + len(value), max(0, w - 2))
                self.stdscr.move(h - 1, cursor_x)
                self.stdscr.refresh()
            except curses.error:
                pass

            try:
                ch = self.stdscr.get_wch()
            except curses.error:
                continue

            if is_enter_key(ch):
                try_set_cursor(0)
                return "".join(buf)
            if ch == "\x1b":
                try_set_cursor(0)
                return None
            if ch == "\x12":
                self.hard_refresh()
                self.set_status("Hard refreshed. Continue typing commit message.")
                continue
            if ch in ("\b", "\x7f") or ch == curses.KEY_BACKSPACE:
                if buf:
                    buf.pop()
                continue
            if isinstance(ch, str) and ch.isprintable():
                buf.append(ch)

    def move_selection(self, delta: int) -> None:
        rows = self.display_rows()
        if not rows:
            return
        self.selected = max(0, min(len(rows) - 1, self.selected + delta))
        self.preview_scroll = 0

    def adjust_section_scroll(self, current_scroll: int, selected_index: Optional[int], total_items: int, section_height: int) -> int:
        max_scroll = max(0, total_items - section_height)
        scroll = max(0, min(current_scroll, max_scroll))
        if selected_index is None:
            return scroll
        if selected_index < scroll:
            scroll = selected_index
        elif selected_index >= scroll + section_height:
            scroll = selected_index - section_height + 1
        return max(0, min(scroll, max_scroll))

    def adjust_preview_scroll(self, delta: int) -> None:
        entry = self.current_entry()
        if not entry:
            return
        lines = self.diff_lines_for_entry(entry)
        self.preview_scroll = max(0, min(max(len(lines) - 1, 0), self.preview_scroll + delta))

    def close_modal(self) -> None:
        self.modal_title = ""
        self.modal_lines = []
        self.modal_scroll = 0

    def pane_header_attr(self, pane: str) -> int:
        if self.active_pane == pane:
            return safe_color_pair(5) | curses.A_BOLD
        return safe_color_pair(6) | curses.A_DIM

    def pane_border_attr(self, pane: str) -> int:
        if self.active_pane == pane:
            return safe_color_pair(5) | curses.A_BOLD
        return safe_color_pair(6)

    def focus_chip_attr(self) -> int:
        if self.active_pane == "preview":
            return safe_color_pair(8) | curses.A_BOLD
        return safe_color_pair(5) | curses.A_BOLD

    def draw_header(self, w: int) -> None:
        title = f" {APP_NAME} "
        focus = f" focus:{self.active_pane} "
        right = focus + " q quit · r hard-refresh · l log "
        left_part = title + ("| " + self.branch if self.branch else "| no branch")
        content = safe_truncate(left_part, max(1, w - len(right) - 1))
        line = content + right
        line = safe_truncate(line, w - 1)
        self.stdscr.attron(safe_color_pair(6))
        self.stdscr.addstr(0, 0, " " * max(0, w - 1))
        self.stdscr.addstr(0, 0, line)
        self.stdscr.attroff(safe_color_pair(6))

    def draw_footer(self, w: int, h: int) -> None:
        if self.status_is_error:
            color = safe_color_pair(3)
        else:
            color = safe_color_pair(2)
        status = safe_truncate(self.status_text, w - 1)
        self.stdscr.attron(color)
        self.stdscr.addstr(h - 1, 0, " " * max(0, w - 1))
        self.stdscr.addstr(h - 1, 0, status)
        self.stdscr.attroff(color)

    def format_entry(self, e: FileEntry) -> str:
        tags: List[str] = []
        if e.conflict:
            tags.append("CONFLICT")
        if e.staged:
            tags.append("staged")
        if e.unstaged:
            tags.append("unstaged")
        if e.untracked:
            tags.append("new")
        suffix = f"[{','.join(tags)}]" if tags else ""
        return f"{e.path} {suffix}".strip()

    def draw_left_panel(self, top: int, left_w: int, body_h: int) -> None:
        title = " files "
        title_attr = safe_color_pair(6) | curses.A_DIM
        self.stdscr.attron(title_attr)
        self.stdscr.addstr(top, 0, safe_truncate(title + "-" * max(0, left_w - len(title)), left_w))
        self.stdscr.attroff(title_attr)

        if self.repo_error:
            self.stdscr.addstr(top + 1, 0, safe_truncate(self.repo_error, left_w - 1))
            return

        rows = self.display_rows()
        changes = [row for row in rows if row.section == "changes"]
        staged = [row for row in rows if row.section == "staged"]
        selected_row = self.current_row()
        selected_section = selected_row.section if selected_row else "changes"

        selected_changes_idx: Optional[int] = None
        selected_staged_idx: Optional[int] = None
        if selected_row and selected_section == "changes":
            selected_changes_idx = next((i for i, row in enumerate(changes) if row.entry.path == selected_row.entry.path), None)
        if selected_row and selected_section == "staged":
            selected_staged_idx = next((i for i, row in enumerate(staged) if row.entry.path == selected_row.entry.path), None)

        list_top = top + 1
        list_h = max(1, body_h - 1)
        if list_h < 4:
            top_h = list_h
            bottom_h = 0
        else:
            top_h = max(2, list_h // 2)
            bottom_h = max(2, list_h - top_h)
            if top_h + bottom_h > list_h:
                top_h = list_h - bottom_h

        changes_body_h = max(1, top_h - 1)
        staged_body_h = max(1, bottom_h - 1) if bottom_h > 0 else 0

        self.changes_scroll = self.adjust_section_scroll(
            self.changes_scroll,
            selected_changes_idx,
            len(changes),
            changes_body_h,
        )
        self.staged_scroll = self.adjust_section_scroll(
            self.staged_scroll,
            selected_staged_idx,
            len(staged),
            staged_body_h if staged_body_h > 0 else 1,
        )

        changes_header_row = list_top
        if self.active_pane == "changes":
            if selected_section == "changes":
                changes_header_attr = safe_color_pair(5) | curses.A_BOLD
            else:
                changes_header_attr = safe_color_pair(6)
        else:
            changes_header_attr = safe_color_pair(6) | curses.A_DIM
        self.stdscr.attron(changes_header_attr)
        self.stdscr.addstr(changes_header_row, 0, " " * max(0, left_w - 1))
        self.stdscr.addstr(changes_header_row, 0, safe_truncate(" CHANGES", left_w - 1))
        self.stdscr.attroff(changes_header_attr)

        for i in range(changes_body_h):
            row_num = changes_header_row + 1 + i
            idx = self.changes_scroll + i
            if idx < len(changes):
                line = safe_truncate(f"  {self.format_entry(changes[idx].entry)}", left_w - 1)
                is_selected = selected_changes_idx == idx
                if is_selected:
                    if self.active_pane == "changes":
                        selected_attr = safe_color_pair(1)
                    else:
                        selected_attr = safe_color_pair(7) | curses.A_DIM
                    self.stdscr.attron(selected_attr)
                    self.stdscr.addstr(row_num, 0, " " * max(0, left_w - 1))
                    self.stdscr.addstr(row_num, 0, line)
                    self.stdscr.attroff(selected_attr)
                else:
                    if self.active_pane != "changes":
                        self.stdscr.attron(curses.A_DIM)
                    self.stdscr.addstr(row_num, 0, line)
                    if self.active_pane != "changes":
                        self.stdscr.attroff(curses.A_DIM)
            elif i == 0:
                self.stdscr.attron(curses.A_DIM)
                self.stdscr.addstr(row_num, 0, safe_truncate("  (no unstaged changes)", left_w - 1))
                self.stdscr.attroff(curses.A_DIM)

        if bottom_h <= 0:
            return

        staged_header_row = list_top + top_h
        if self.active_pane == "changes":
            if selected_section == "staged":
                staged_header_attr = safe_color_pair(5) | curses.A_BOLD
            else:
                staged_header_attr = safe_color_pair(2) | curses.A_BOLD
        else:
            staged_header_attr = safe_color_pair(2) | curses.A_DIM
        self.stdscr.attron(staged_header_attr)
        self.stdscr.addstr(staged_header_row, 0, " " * max(0, left_w - 1))
        self.stdscr.addstr(staged_header_row, 0, safe_truncate(" STAGED", left_w - 1))
        self.stdscr.attroff(staged_header_attr)

        for i in range(staged_body_h):
            row_num = staged_header_row + 1 + i
            idx = self.staged_scroll + i
            if idx < len(staged):
                line = safe_truncate(f"  {self.format_entry(staged[idx].entry)}", left_w - 1)
                is_selected = selected_staged_idx == idx
                if is_selected:
                    if self.active_pane == "changes":
                        selected_attr = safe_color_pair(1)
                    else:
                        selected_attr = safe_color_pair(7) | curses.A_DIM
                    self.stdscr.attron(selected_attr)
                    self.stdscr.addstr(row_num, 0, " " * max(0, left_w - 1))
                    self.stdscr.addstr(row_num, 0, line)
                    self.stdscr.attroff(selected_attr)
                else:
                    staged_attr = safe_color_pair(2)
                    if self.active_pane != "changes":
                        staged_attr |= curses.A_DIM
                    self.stdscr.attron(staged_attr)
                    self.stdscr.addstr(row_num, 0, line)
                    self.stdscr.attroff(staged_attr)
            elif i == 0:
                placeholder_attr = safe_color_pair(2) | curses.A_DIM
                self.stdscr.attron(placeholder_attr)
                self.stdscr.addstr(row_num, 0, safe_truncate("  (no staged changes)", left_w - 1))
                self.stdscr.attroff(placeholder_attr)

    def draw_right_panel(self, top: int, left_w: int, w: int, body_h: int) -> None:
        x0 = left_w + 1
        right_w = max(1, w - x0 - 1)
        border_attr = self.pane_border_attr("preview")
        self.stdscr.attron(border_attr)
        for row in range(top, top + body_h):
            self.stdscr.addstr(row, left_w, "│")
        self.stdscr.attroff(border_attr)

        title = " [ PREVIEW ] " if self.active_pane == "preview" else "   preview   "
        self.stdscr.attron(self.pane_header_attr("preview"))
        self.stdscr.addstr(top, x0, safe_truncate(title + "-" * max(0, right_w - len(title)), right_w))
        self.stdscr.attroff(self.pane_header_attr("preview"))

        entry = self.current_entry()
        if self.repo_error:
            return
        if not entry:
            self.stdscr.addstr(top + 1, x0, safe_truncate("No changes to preview.", right_w - 1))
            return

        mode = self.current_preview_mode(entry)
        mode_hint = f"mode: {mode}"
        if self.active_pane == "preview":
            self.stdscr.attron(safe_color_pair(8) | curses.A_BOLD)
            self.stdscr.addstr(top + 1, x0, " " * max(0, right_w - 1))
            self.stdscr.addstr(top + 1, x0, safe_truncate(mode_hint, right_w - 1))
            self.stdscr.attroff(safe_color_pair(8) | curses.A_BOLD)
        else:
            self.stdscr.addstr(top + 1, x0, safe_truncate(mode_hint, right_w - 1))

        lines = self.diff_lines_for_entry(entry)
        content_top = top + 2
        content_h = max(1, body_h - 2)
        max_scroll = max(0, len(lines) - content_h)
        self.preview_scroll = max(0, min(max_scroll, self.preview_scroll))
        visible = lines[self.preview_scroll : self.preview_scroll + content_h]

        for i, raw in enumerate(visible):
            row = content_top + i
            line = raw.replace("\t", "    ")
            color = 0
            if line.startswith("+") and not line.startswith("+++"):
                color = 2
            elif line.startswith("-") and not line.startswith("---"):
                color = 3
            if color:
                self.stdscr.attron(safe_color_pair(color))
            self.stdscr.addstr(row, x0, safe_truncate(line, right_w - 1))
            if color:
                self.stdscr.attroff(safe_color_pair(color))

    def draw_key_hint(self, h: int, w: int) -> None:
        row = max(1, h - 2)
        self.stdscr.addstr(row, 0, " " * max(0, w - 1))
        focus_chip = f" [{self.active_pane.upper()}] "
        primary = "[C push]" if self.primary_action_name() == "push" else "[C commit]"
        if self.current_section() == "staged":
            actions = f" [U unstage] {primary}"
        else:
            actions = f" [S stage] [U unstage] {primary}"
        rest = (
            f" [<- changes] [-> preview]{actions}"
            " · j/k move/scroll · Enter preview · p pull · P push · q quit "
        )
        chip = safe_truncate(focus_chip, w - 1)
        self.stdscr.attron(self.focus_chip_attr())
        self.stdscr.addstr(row, 0, chip)
        self.stdscr.attroff(self.focus_chip_attr())
        if len(chip) < w - 1:
            self.stdscr.addstr(row, len(chip), safe_truncate(rest, w - 1 - len(chip)))

    def draw_modal(self, h: int, w: int) -> None:
        if not self.modal_lines:
            return
        modal_w = max(30, min(w - 6, 100))
        modal_h = max(10, min(h - 4, 28))
        x0 = (w - modal_w) // 2
        y0 = (h - modal_h) // 2

        shadow_attr = curses.A_REVERSE | curses.A_DIM
        if x0 + modal_w < w - 1:
            for y in range(y0 + 1, min(h - 1, y0 + modal_h + 1)):
                self.stdscr.attron(shadow_attr)
                self.stdscr.addstr(y, x0 + modal_w, " ")
                self.stdscr.attroff(shadow_attr)
        if y0 + modal_h < h - 1:
            self.stdscr.attron(shadow_attr)
            self.stdscr.addstr(y0 + modal_h, x0 + 1, " " * max(0, min(modal_w, w - x0 - 2)))
            self.stdscr.attroff(shadow_attr)

        modal_bg = safe_color_pair(7)
        for y in range(y0 + 1, y0 + modal_h - 1):
            self.stdscr.attron(modal_bg)
            self.stdscr.addstr(y, x0 + 1, " " * max(0, modal_w - 2))
            self.stdscr.attroff(modal_bg)

        frame_attr = safe_color_pair(4) | curses.A_BOLD
        self.stdscr.attron(frame_attr)
        self.stdscr.addstr(y0, x0, "┌" + "─" * (modal_w - 2) + "┐")
        for y in range(y0 + 1, y0 + modal_h - 1):
            self.stdscr.addstr(y, x0, "│")
            self.stdscr.addstr(y, x0 + modal_w - 1, "│")
        self.stdscr.addstr(y0 + modal_h - 1, x0, "└" + "─" * (modal_w - 2) + "┘")
        self.stdscr.attroff(frame_attr)

        self.stdscr.attron(frame_attr)
        self.stdscr.addstr(y0, x0 + 2, safe_truncate(self.modal_title, modal_w - 6))
        self.stdscr.attroff(frame_attr)

        content_h = modal_h - 3
        max_scroll = max(0, len(self.modal_lines) - content_h)
        self.modal_scroll = max(0, min(max_scroll, self.modal_scroll))
        visible = self.modal_lines[self.modal_scroll : self.modal_scroll + content_h]

        for i, line in enumerate(visible):
            row = y0 + 1 + i
            self.stdscr.attron(modal_bg)
            self.stdscr.addstr(row, x0 + 1, safe_truncate(line, modal_w - 2))
            self.stdscr.attroff(modal_bg)

        footer = " j/k scroll · q/esc close · modal focus locked "
        self.stdscr.attron(frame_attr)
        self.stdscr.addstr(y0 + modal_h - 1, x0 + 2, safe_truncate(footer, modal_w - 4))
        self.stdscr.attroff(frame_attr)

    def draw(self) -> None:
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        if h < 10 or w < 50:
            self.stdscr.addstr(0, 0, "Resize terminal to at least 50x10.")
            self.stdscr.refresh()
            return

        self.draw_header(w)
        body_top = 1
        body_h = max(1, h - 3)
        left_w = max(30, min(w // 2, 56))
        self.draw_left_panel(body_top, left_w, body_h)
        self.draw_right_panel(body_top, left_w, w, body_h)
        self.draw_key_hint(h, w)
        self.draw_footer(w, h)
        self.draw_modal(h, w)
        self.stdscr.refresh()

    def handle_modal_input(self, ch: object) -> None:
        if ch in ("q", "\x1b", "l") or is_enter_key(ch):
            self.close_modal()
            return
        if ch in ("j", curses.KEY_DOWN):
            self.modal_scroll += 1
            return
        if ch in ("k", curses.KEY_UP):
            self.modal_scroll = max(0, self.modal_scroll - 1)
            return

    def run(self) -> int:
        try_set_cursor(0)
        self.stdscr.keypad(True)
        try:
            curses.start_color()
        except curses.error:
            pass
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        for pair_id, fg, bg in (
            (1, curses.COLOR_BLACK, curses.COLOR_BLUE),
            (2, curses.COLOR_GREEN, -1),
            (3, curses.COLOR_RED, -1),
            (4, curses.COLOR_BLUE, -1),
            (5, curses.COLOR_BLACK, curses.COLOR_GREEN),
            (6, curses.COLOR_WHITE, -1),
            (7, curses.COLOR_BLACK, curses.COLOR_WHITE),
            (8, curses.COLOR_BLACK, curses.COLOR_BLUE),
        ):
            try:
                curses.init_pair(pair_id, fg, bg)
            except (curses.error, ValueError):
                pass

        self.refresh_data(keep_selection=False)
        if self.repo_error:
            self.set_status(self.repo_error, error=True)
        else:
            self.set_status("Ready")

        while True:
            try:
                self.draw()
            except curses.error:
                continue
            try:
                ch = self.stdscr.get_wch()
            except curses.error:
                continue

            if self.modal_lines:
                self.handle_modal_input(ch)
                continue

            if ch in ("q", "Q"):
                return 0
            if ch in ("j", curses.KEY_DOWN):
                if self.active_pane == "changes":
                    self.move_selection(1)
                else:
                    self.adjust_preview_scroll(1)
                continue
            if ch in ("k", curses.KEY_UP):
                if self.active_pane == "changes":
                    self.move_selection(-1)
                else:
                    self.adjust_preview_scroll(-1)
                continue
            if ch in (curses.KEY_NPAGE, "n"):
                self.adjust_preview_scroll(10)
                continue
            if ch in (curses.KEY_PPAGE, "b"):
                self.adjust_preview_scroll(-10)
                continue
            if is_enter_key(ch):
                self.active_pane = "preview"
                self.set_status("Focus: preview")
                continue
            if ch in ("r", "R"):
                self.hard_refresh()
                continue
            if ch == curses.KEY_RIGHT:
                self.active_pane = "preview"
                self.set_status("Focus: preview")
                continue
            if ch == curses.KEY_LEFT:
                self.active_pane = "changes"
                self.set_status("Focus: changes")
                continue
            if self.repo_error:
                continue
            if ch in ("s", " "):
                self.stage_selected()
                continue
            if ch == "u":
                self.unstage_selected()
                continue
            if ch in ("c", "C"):
                self.run_primary_action()
                continue
            if ch == "p":
                self.pull_rebase()
                continue
            if ch == "P":
                self.push()
                continue
            if ch == "l":
                self.show_log_modal()
                continue


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Minimal git terminal UI with core commands.",
    )
    parser.add_argument("--version", action="store_true", help="Print tidgit version and exit.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.version:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0

    if "TERM" not in os.environ:
        print("TERM is not set. Start from a real terminal.")
        return 1

    try:
        return curses.wrapper(lambda stdscr: TidGitApp(stdscr).run())
    except KeyboardInterrupt:
        return 130
    except curses.error as exc:
        print(f"Terminal UI error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
