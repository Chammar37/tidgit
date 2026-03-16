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

# ── Main ─────────────────────────────────────────────────────────────

main() {
    echo ""
    echo "  Installing tidgit"
    echo "  ─────────────────"
    echo ""

    PYTHON=$(find_python) || die "Python >= ${MIN_PY_MAJOR}.${MIN_PY_MINOR} is required. Install it first."
    PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    ok "Found Python $PY_VER ($PYTHON)"

    # Prefer pipx for isolated install
    if command -v pipx >/dev/null 2>&1; then
        info "Installing with pipx ..."
        pipx install "git+https://github.com/${REPO}.git" --force --python "$PYTHON"
        ok "Installed with pipx"

    # Fall back to pip --user
    elif "$PYTHON" -m pip --version >/dev/null 2>&1; then
        info "pipx not found, using pip install --user ..."
        "$PYTHON" -m pip install --user "git+https://github.com/${REPO}.git" --quiet --force-reinstall
        ok "Installed with pip --user"

    else
        die "Neither pipx nor pip found. Install one of them first."
    fi

    # Verify
    if command -v tidgit >/dev/null 2>&1; then
        ok "tidgit $(tidgit --version 2>/dev/null || echo '') is ready — run: tidgit"
    else
        echo ""
        err "tidgit was installed but isn't on your PATH."
        info "If you used pip --user, add this to your shell profile:"
        info "  export PATH=\"\$($PYTHON -m site --user-base)/bin:\$PATH\""
        echo ""
    fi
}

main
