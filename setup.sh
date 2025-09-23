
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
