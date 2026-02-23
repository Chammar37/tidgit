class Tidgit < Formula
  include Language::Python::Virtualenv

  desc "Minimal terminal Git TUI focused on core workflows"
  homepage "https://github.com/marcchami/tidgit"
  url "https://github.com/marcchami/tidgit/releases/download/v0.1.0/tidgit-0.1.0.tar.gz"
  sha256 "d73747db7ee7127d52ab9489546e31c18a91b8f1b4117cc175376857fa5d80f7"
  license "MIT"
  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "0.1.0", shell_output("#{bin}/tidgit --version")
  end
end
