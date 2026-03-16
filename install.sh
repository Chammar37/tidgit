#!/bin/sh
set -e

REPO="Chammar37/tidgit"
MIN_PY_MAJOR=3
MIN_PY_MINOR=11

# ── Helpers ──────────────────────────────────────────────────────────

info()  { printf '  \033[1;34m>\033[0m %s\n' "$*"; }
ok()    { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
err()   { printf '  \033[1;31m✗\033[0m %s\n' "$*" >&2; }
die()   { err "$@"; exit 1; }

# ── Find Python ≥ 3.11 ──────────────────────────────────────────────

find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null) || continue
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [ "$major" -ge "$MIN_PY_MAJOR" ] && [ "$minor" -ge "$MIN_PY_MINOR" ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

# ── Ensure pipx is available ─────────────────────────────────────────

ensure_pipx() {
    if command -v pipx >/dev/null 2>&1; then
        return 0
    fi

    # On macOS with Homebrew, install pipx via brew
    if command -v brew >/dev/null 2>&1; then
        info "pipx not found — installing via brew ..."
        brew install pipx >/dev/null 2>&1
        pipx ensurepath >/dev/null 2>&1 || true
        if command -v pipx >/dev/null 2>&1; then
            return 0
        fi
        # brew may put pipx somewhere not yet on PATH in this shell
        BREW_PREFIX=$(brew --prefix)
        if [ -x "${BREW_PREFIX}/bin/pipx" ]; then
            export PATH="${BREW_PREFIX}/bin:${PATH}"
            return 0
        fi
    fi

    # Try pip-installing pipx as a last resort
    if "$PYTHON" -m pip install --user pipx >/dev/null 2>&1; then
        "$PYTHON" -m pipx ensurepath >/dev/null 2>&1 || true
        if command -v pipx >/dev/null 2>&1; then
            return 0
        fi
    fi

    return 1
}

# ── Main ─────────────────────────────────────────────────────────────

main() {
    echo ""
    echo "  Installing tidgit"
    echo "  ─────────────────"
    echo ""

    PYTHON=$(find_python) || die "Python >= ${MIN_PY_MAJOR}.${MIN_PY_MINOR} is required. Install it first."
    PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    ok "Found Python $PY_VER ($PYTHON)"

    ensure_pipx || die "Could not install pipx. Install it manually: brew install pipx"

    info "Installing with pipx ..."
    pipx install "git+https://github.com/${REPO}.git" --force --python "$PYTHON"
    ok "Installed with pipx"

    # Verify
    if command -v tidgit >/dev/null 2>&1; then
        ok "tidgit $(tidgit --version 2>/dev/null || echo '') is ready — run: tidgit"
    else
        echo ""
        err "tidgit was installed but isn't on your PATH."
        info "Run: pipx ensurepath"
        info "Then restart your shell."
        echo ""
    fi
}

main
