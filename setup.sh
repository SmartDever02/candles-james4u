#!/usr/bin/env bash
# Setup: Git, Rust, Astral uv, Node.js + npm (Ubuntu repo), PM2
# Then clone + checkout + run miner setup (auto-answer single 'y')
# Usage: bash setup_env.sh

set -euo pipefail

#================= CONFIG =================
REPO_URL="https://github.com/SmartDever02/candles-james4u.git"
REPO_NAME="candles-james4u"
REPO_BRANCH="james4u"
CHECKOUT_DIR="$HOME"          # change where you want the repo cloned
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
if [ -f "$HOME/.cargo/env" ]; then
  # shellcheck source=/dev/null
  source "$HOME/.cargo/env"
  append_once 'source "$HOME/.cargo/env"' "$RC_FILE"
fi

log "Ensuring Rust toolchain (stable, rustfmt, clippy)"
rustup install stable >/dev/null 2>&1 || true
rustup default stable >/dev/null 2>&1 || true
rustup component add rustfmt clippy >/dev/null 2>&1 || true

#--- Astral uv -------------------------------------------------------------
if command -v uv >/dev/null 2>&1; then
  log "uv already installed: $(uv --version)"
else
  log "Installing Astral uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Ensure uv PATH & env file
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$HOME/.local/bin"; then
  export PATH="$HOME/.local/bin:$PATH"
fi
append_once 'export PATH="$HOME/.local/bin:$PATH"' "$RC_FILE"

if [ -f "$HOME/.local/bin/env" ]; then
  # shellcheck source=/dev/null
  source "$HOME/.local/bin/env"
  append_once 'source "$HOME/.local/bin/env"' "$RC_FILE"
fi

#--- Node.js + npm (Ubuntu repo) ------------------------------------------
if command -v node >/dev/null 2>&1; then
  log "Node.js already installed: $(node -v)"
else
  log "Installing Node.js and npm (Ubuntu repo)"
  $SUDO apt install -y nodejs npm
fi

#--- PM2 (global) ----------------------------------------------------------
if command -v pm2 >/dev/null 2>&1; then
  log "PM2 already installed: $(pm2 -v)"
else
  log "Installing PM2 globally"
  $SUDO npm install -g pm2
fi

#--- Repo: clone / update / checkout --------------------------------------
log "Preparing checkout directory: $CHECKOUT_DIR"
mkdir -p "$CHECKOUT_DIR"

if [ -d "$CHECKOUT_DIR/$REPO_NAME/.git" ]; then
  log "Repo exists. Updating: $CHECKOUT_DIR/$REPO_NAME"
  git -C "$CHECKOUT_DIR/$REPO_NAME" fetch --all --prune
  git -C "$CHECKOUT_DIR/$REPO_NAME" checkout "$REPO_BRANCH"
  git -C "$CHECKOUT_DIR/$REPO_NAME" pull --rebase --autostash origin "$REPO_BRANCH" || true
else
  log "Cloning $REPO_URL into $CHECKOUT_DIR"
  git clone "$REPO_URL" "$CHECKOUT_DIR/$REPO_NAME"
  git -C "$CHECKOUT_DIR/$REPO_NAME" checkout "$REPO_BRANCH"
fi

#--- Run miner setup script (auto-answer single 'y') -----------------------
log "Running miner setup (auto-confirm once): $MINER_SCRIPT ${MINER_ARGS[*]}"
cd "$CHECKOUT_DIR/$REPO_NAME"
if [ ! -x "$MINER_SCRIPT" ]; then
  chmod +x "$MINER_SCRIPT" || true
fi
if [ -f "$MINER_SCRIPT" ]; then
  # Send exactly one 'y' followed by newline to the script
  printf 'y\n' | bash "$MINER_SCRIPT" "${MINER_ARGS[@]}"
else
  log "WARNING: $MINER_SCRIPT not found in $(pwd). Skipping."
fi

#--- Summary ---------------------------------------------------------------
log "Environment setup complete. Versions:"
echo "  Shell rc file: $RC_FILE"
echo "  Git:        $(git --version | awk '{print $3}')"
echo "  Rustc:      $(rustc --version | awk '{print $2}')"
echo "  Cargo:      $(cargo --version | awk '{print $2}')"
echo "  uv:         $(uv --version | awk '{print $2}')"
echo "  Node:       $(node -v 2>/dev/null || echo 'not found')"
echo "  npm:        $(npm -v 2>/dev/null || echo 'not found')"
echo "  PM2:        $(pm2 -v 2>/dev/null || echo 'not found')"
echo "  Repo dir:   $CHECKOUT_DIR/$REPO_NAME (branch: $REPO_BRANCH)"

log "Tip: run 'source \"$RC_FILE\"' or open a new shell to load PATH updates."
