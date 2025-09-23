#!/usr/bin/env bash
# Setup: Git, Rust, Astral uv, Node.js + npm (Ubuntu repo), PM2
# Then clone + checkout + run miner setup (auto-answer single 'y')
# Usage: bash setup_env.sh

set -euo pipefail

#================= CONFIG =================
REPO_URL="https://github.com/SmartDever02/candles-james4u.git"
REPO_NAME="candles-james4u"
REPO_BRANCH="james4u"
CHECKOUT_DIR="$HOME/apps"          # change where you want the repo cloned
MINER_SCRIPT="./setup_miner.sh"
MINER_ARGS=("ghost1" "miner3140")  # args to pass to setup_miner.sh
#=========================================

log() { printf "\n\e[1;36m[SETUP]\e[0m %s\n" "$*"; }
need_sudo() { [ "$(id -u)" -ne 0 ] && echo "sudo" || true; }
append_once() { local line="$1" file="$2"; grep -qxF -- "$line" "$file" 2>/dev/null || echo "$line" >>"$file"; }

SUDO="$(need_sudo)"
export DEBIAN_FRONTEND=noninteractive

RC_FILE="$HOME/.bashrc"
[ -n "${ZSH_VERSION-}" ] && RC_FILE="$HOME/.zshrc"

#--- APT basics ------------------------------------------------------------
log "Updating apt & installing base build tools"
$SUDO apt update -y
$SUDO apt install -y \
  git curl ca-certificates build-essential pkg-config \
  libssl-dev zlib1g-dev libffi-dev

#--- Git -------------------------------------------------------------------
if command -v git >/dev/null 2>&1; then
  log "Git already installed: $(git --version)"
else
  log "Installing Git"
  $SUDO apt install -y git
fi

#--- Rust (rustup) ---------------------------------------------------------
if command -v rustup >/dev/null 2>&1; then
  log "Rustup already installed"
else
  log "Installing Rust (rustup)"
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
fi

# Make Rust available now & later
