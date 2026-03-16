# tidgit

A minimal terminal Git TUI focused on core workflows and clear terminal UX. Zero dependencies — just Python and curses.

## Install

```sh
curl -sSL https://raw.githubusercontent.com/Chammar37/tidgit/master/install.sh | sh
```

Requires Python 3.11+. Installs via **pipx** (preferred) or **pip**.

### Other install methods

```sh
# pipx (isolated environment)
pipx install git+https://github.com/Chammar37/tidgit.git

# pip
pip install git+https://github.com/Chammar37/tidgit.git
```

## Usage

Run inside any git repository:

```sh
tidgit
```

## Features

- Split-pane layout: **Changes** (left) and **Diff preview** (right)
- Separate sections for unstaged/untracked and staged files
- Stage and unstage individual files
- Commit with inline message prompt
- Pull with rebase / Push
- Discard working-tree changes (with confirmation)
- Reset view — soft and hard reset to any recent commit or file
- View recent commit log
- Color-coded file labels: added, deleted, modified, conflict
- Keyboard-driven — no mouse needed

## Keybindings

| Key | Action |
|-----|--------|
| `j` / `k` or `Up` / `Down` | Move selection |
| `Right` / `Left` | Switch focus between changes and preview |
| `Enter` | Focus preview pane |
| `s` | Stage selected file |
| `u` | Unstage selected file |
| `d` | Discard changes to selected file (confirm with Enter) |
| `c` | Commit (or push, when branch is ahead) |
| `p` | Pull with rebase |
| `P` | Push |
| `l` | Show recent commits |
| `x` | Open reset view |
| `r` | Refresh |
| `n` / `b` | Scroll preview down / up |
| `q` | Quit |

### Reset view

| Key | Action |
|-----|--------|
| `Up` / `Down` | Navigate commits or files |
| `Left` / `Right` or `Tab` | Switch between commits and files |
| `Enter` | Soft reset |
| `H` | Hard reset (with confirmation) |
| `Esc` | Back to main view |

## Development

```sh
make install-dev   # editable install with dev deps
make check         # lint + typecheck + test
make smoke         # quick sanity check
make package       # build wheel + sdist
```

## Requirements

- Python 3.11+
- A terminal with curses support
- Must be run inside a git repository

## License

MIT
