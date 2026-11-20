# Written by scripts/packaging/render_formula.py (repository
# habhabhabs/inventag-aws) from the SHA256SUMS file of a release. Do not edit
# it by hand: the next release writes it again.
#
# It installs the executable that the release workflow builds, a directory made
# by PyInstaller that brings its own runtime. Nothing is compiled and nothing
# but the archive is downloaded.
#
# The executable bundles GNU libiconv inside lxml under LGPL-2.1. The notices
# file THIRD-PARTY-LICENSES.txt in the archive names where its source is.
class Inventag < Formula
  desc "Read-only AWS inventory, tag checks and BOM reports"
  homepage "https://habhabhabs.github.io/inventag-aws/"
  license "MIT"

  on_macos do
    # Only the Apple Silicon archive exists. brew style wants url and sha256
    # inside on_arm or on_intel. An Intel Mac gets the same archive declared so
    # that the formula loads; install then stops with a message on its first line.
    on_arm do
      url "{{BASE_URL}}/inventag-{{VERSION}}-darwin-arm64.tar.gz"
      sha256 "{{SHA256_DARWIN_ARM64}}"
    end
    on_intel do
      url "{{BASE_URL}}/inventag-{{VERSION}}-darwin-arm64.tar.gz"
      sha256 "{{SHA256_DARWIN_ARM64}}"
    end
  end

  on_linux do
    on_intel do
      url "{{BASE_URL}}/inventag-{{VERSION}}-linux-x86_64.tar.gz"
      sha256 "{{SHA256_LINUX_X86_64}}"
    end
    on_arm do
      url "{{BASE_URL}}/inventag-{{VERSION}}-linux-arm64.tar.gz"
      sha256 "{{SHA256_LINUX_ARM64}}"
    end
  end

  def install
    if OS.mac? && Hardware::CPU.intel?
      odie "There is no executable for Intel Macs: a library InvenTag needs " \
           "(cryptography, from version 50) publishes no ready-made build for them. " \
           "Other ways to install are on " \
           "https://habhabhabs.github.io/inventag-aws/docs/getting-started/installation"
    end

    libexec.install Dir["*"]
    bin.install_symlink libexec/"inventag"
    bash_completion.install libexec/"share/completions/inventag.bash" => "inventag"
    zsh_completion.install libexec/"share/completions/_inventag"
    fish_completion.install libexec/"share/completions/inventag.fish"
    man1.install libexec/"share/man/man1/inventag.1"
  end

  def caveats
    <<~EOS
      Third-party licences: see THIRD-PARTY-LICENSES.txt in the installation directory
    EOS
  end

  test do
    assert_match "inventag #{version}", shell_output("#{bin}/inventag --version")
    system bin/"inventag", "selftest"
  end
end
