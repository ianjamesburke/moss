#!/usr/bin/env bash
# Moss installer.
#
# What it does:
#   1. Makes sure Rust and Python 3 are present (fails with a link if not)
#   2. Clones (or updates) the Moss repo at ~/.moss/src
#   3. Puts a `moss` command on your PATH at ~/.local/bin/moss
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ianjamesburke/moss/main/install.sh | bash
# or, from a local clone:
#   ./install.sh

set -euo pipefail

REPO_URL="https://github.com/ianjamesburke/moss.git"
MOSS_HOME="${MOSS_HOME:-$HOME/.moss}"
SRC_DIR="$MOSS_HOME/src"
BIN_TARGET="$HOME/.local/bin"

say() { printf "\033[1;32m%s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m%s\033[0m\n" "$*" >&2; }
die() { printf "\033[1;31m%s\033[0m\n" "$*" >&2; exit 1; }

# --- dependencies ---

if ! command -v python3 >/dev/null 2>&1; then
    die "python3 is required. Install it from https://www.python.org/downloads/"
fi

if ! command -v cargo >/dev/null 2>&1; then
    die "Rust (cargo) is required. Install it from https://rustup.rs"
fi

# --- fetch source ---

mkdir -p "$MOSS_HOME"
if [ -d "$SRC_DIR/.git" ]; then
    say "Updating Moss at $SRC_DIR"
    git -C "$SRC_DIR" pull --ff-only
else
    say "Cloning Moss to $SRC_DIR"
    git clone --depth 1 "$REPO_URL" "$SRC_DIR"
fi

# --- install CLI ---

mkdir -p "$BIN_TARGET"
ln -sf "$SRC_DIR/moss" "$BIN_TARGET/moss"
chmod +x "$SRC_DIR/moss"

say "Installed moss -> $BIN_TARGET/moss"

# --- PATH check ---

case ":$PATH:" in
    *":$BIN_TARGET:"*)
        ;;
    *)
        warn ""
        warn "$BIN_TARGET is not on your PATH."
        warn "Add this line to your shell config (~/.zshrc or ~/.bashrc):"
        warn ""
        warn "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        warn ""
        ;;
esac

# --- warm the Rust cache ---

say "Warming up the Rust build cache (one-time, ~15s)..."
"$SRC_DIR/moss" run "$SRC_DIR/examples/01_hello.moss" >/dev/null

say ""
say "Moss is installed."
say ""
say "Try it:"
say "    moss run $SRC_DIR/examples/TEACHING.moss"
say "    moss run $SRC_DIR/examples/07_plexi_poc.moss"
