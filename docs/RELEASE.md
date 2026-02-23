# Release And Homebrew Distribution

## Prerequisites

- A GitHub repository for this project (example: `marcchami/tidgit`)
- CI permissions to create releases from tags
- Homebrew installed locally for formula checks

## Local release validation

```bash
make check
make formula REPO=marcchami/tidgit
make release-artifacts REPO=marcchami/tidgit
brew style Formula/tidgit.rb
```

Note: newer Homebrew versions do not support `brew audit` on local formula paths. Run `brew audit --strict <tap>/<formula>` after publishing your tap formula.

## Publish to web (GitHub Releases)

1. Commit and push all release-ready changes.
2. Create and push a semver tag (example: `v0.1.0`):

```bash
git tag v0.1.0
git push origin v0.1.0
```

3. `.github/workflows/release.yml` publishes:

- `dist/*.whl`
- `dist/*.tar.gz`
- `dist/SHA256SUMS.txt`
- `Formula/tidgit.rb`

All are downloadable from the GitHub Release page.

## Homebrew install from the web

```bash
brew install https://raw.githubusercontent.com/marcchami/tidgit/main/Formula/tidgit.rb
```

Then verify:

```bash
tidgit --version
```
