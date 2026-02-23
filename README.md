# tidgit

`tidgit` is a minimal terminal Git TUI inspired by lazygit, focused on core workflows and clear terminal UX.

## Git Functions

- View branch/status and changed files
- Preview diffs for staged, unstaged, and untracked files
- Stage selected file (`git add -- <file>`)
- Unstage selected file (`git restore --staged -- <file>`)
- Commit staged changes (`git commit -m "..."`)
- Pull latest changes with rebase (`git pull --rebase`)
- Push local commits (`git push`)
- View recent commit history (`git log --oneline --decorate -n 30`)
- Refresh working tree status

## Run

```bash
./tidgit
```

Optional:

```bash
./tidgit --version
./tidgit --help
```

## Keybindings

- `j` / `k` or `Up` / `Down`: move selection
- `Right Arrow`: focus preview pane
- `Left Arrow`: focus changes pane
- `Enter`: toggle preview mode when a file has both staged and unstaged changes
- `s`: stage selected file
- `u`: unstage selected file
- `c`: primary action button (commit when staged changes exist, push when branch is ahead)
- `p`: pull with rebase
- `P`: push
- `l`: show recent commits
- `r`: refresh
- `n` / `b`: scroll preview down/up
- `q`: quit

## Production Validation

```bash
make install-dev
make check
make smoke
make package
```

Validation gates included out of the box:

- Lint: `ruff`
- Type checking: `mypy --strict`
- Test suite: `pytest` (unit + integration)
- Coverage gate: fail under 70%
- Packaging checks: `python -m build` + `twine check`

## Homebrew Formula

Generate a release formula from the built source tarball:

```bash
make formula REPO=marcchami/tidgit
```

This writes `Formula/tidgit.rb` with the correct SHA256 for the current `dist/tidgit-<version>.tar.gz`.

## Web Download + Brew Install

Release publishing is automated by `.github/workflows/release.yml` on tags like `v0.1.0`.

Release assets uploaded to GitHub Releases:

- `dist/*.whl`
- `dist/*.tar.gz`
- `dist/SHA256SUMS.txt`
- `Formula/tidgit.rb`

After release, install from the web:

```bash
brew install https://raw.githubusercontent.com/marcchami/tidgit/main/Formula/tidgit.rb
```

## Notes

- Run inside a git repository.
- If not in a git repo, the UI shows an explicit error state.
- For untracked files, preview uses a no-index diff against `/dev/null`.
- Active pane focus is high-contrast (lazygit-inspired accents).
