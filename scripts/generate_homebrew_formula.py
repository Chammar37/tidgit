#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import tomllib


def read_version(pyproject_path: Path) -> str:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def render_formula(version: str, repo: str, sha256: str) -> str:
    return f'''class Tidgit < Formula
  include Language::Python::Virtualenv

  desc "Minimal terminal Git TUI focused on core workflows"
  homepage "https://github.com/{repo}"
  url "https://github.com/{repo}/releases/download/v{version}/tidgit-{version}.tar.gz"
  sha256 "{sha256}"
  license "MIT"
  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "{version}", shell_output("#{{bin}}/tidgit --version")
  end
end
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Homebrew formula for tidgit release artifacts.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "marcchami/tidgit"), help="GitHub owner/repo")
    parser.add_argument("--version", default="", help="Version override (defaults to pyproject version)")
    parser.add_argument("--dist-dir", default="dist", help="Directory containing source dist")
    parser.add_argument("--output", default="Formula/tidgit.rb", help="Output formula path")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    pyproject_path = project_root / "pyproject.toml"
    version = args.version or read_version(pyproject_path)

    dist_dir = (project_root / args.dist_dir).resolve()
    sdist = dist_dir / f"tidgit-{version}.tar.gz"
    if not sdist.exists():
        raise SystemExit(f"Missing source distribution: {sdist}. Run 'make package' first.")

    sha = sha256_file(sdist)
    output_path = (project_root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_formula(version, args.repo, sha), encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"SHA256: {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
