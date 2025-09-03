#!/usr/bin/env bash
set -euo pipefail

# =========================
# Config — EDIT THESE if needed
# =========================
# You said you don't need auto-deploy, so default action is "serve".
POST_BUILD_ACTION="${1:-serve}"

# Set this ONLY if you already have a Quartz clone you want to use.
# Otherwise we'll use ./.quartz-site and clone Quartz v4 there if needed.
QUARTZ_DIR="${QUARTZ_DIR:-}"

# Set base URL used by Quartz when you later deploy (project vs user page).
# For a project page like https://thoroftroy.github.io/Eyum-TTRPG, use:
BASE_URL="/Eyum-TTRPG"

# =========================
# Paths
# =========================
VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_DIR="${QUARTZ_DIR:-$VAULT_DIR/.quartz-site}"
CONTENT_DIR="$SITE_DIR/content"
PUBLIC_DIR="$SITE_DIR/public"

need_cmd() { command -v "$1" >/dev/null 2>&1; }

ensure_nvm_loaded() {
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
  [ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion" || true
}

ensure_node22() {
  if ! need_cmd nvm; then
    echo "nvm not found. Installing nvm (one time)..."
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  fi
  ensure_nvm_loaded
  echo "Ensuring Node 22..."
  nvm install 22 >/dev/null
  nvm use 22 >/dev/null
  nvm install-latest-npm >/dev/null || true
  echo "Using: node $(node -v), npm $(npm -v)"
}

force_clone_quartz() {
  echo "Cloning Quartz v4 into $SITE_DIR ..."
  rm -rf "$SITE_DIR"
  git clone --depth=1 --branch v4 https://github.com/jackyzha0/quartz.git "$SITE_DIR"
}

ensure_quartz_project() {
  if [ -n "$QUARTZ_DIR" ]; then
    echo "Using existing Quartz at $QUARTZ_DIR"
  else
    if [ ! -d "$SITE_DIR" ]; then
      force_clone_quartz
    elif [ ! -f "$SITE_DIR/package.json" ]; then
      echo "No package.json in $SITE_DIR — not a valid Quartz project. Re-cloning."
      force_clone_quartz
    fi
  fi
}

install_deps() {
  echo "Installing Quartz dependencies..."
  pushd "$SITE_DIR" >/dev/null
    if [ -f pnpm-lock.yaml ] && need_cmd pnpm; then
      pnpm i
    elif [ -f package-lock.json ]; then
      npm ci
    else
      npm i
    fi
  popd >/dev/null
}

sync_content() {
  echo "Syncing vault → Quartz content..."
  mkdir -p "$CONTENT_DIR"
  rsync -av --delete \
    --exclude ".git/" \
    --exclude ".obsidian/" \
    --exclude ".quartz-site/" \
    --exclude "node_modules/" \
    --exclude "public/" \
    --exclude "*.DS_Store" \
    "$VAULT_DIR/" "$CONTENT_DIR/"
}

ensure_index() {
  if [ ! -f "$CONTENT_DIR/index.md" ]; then
    cat > "$CONTENT_DIR/index.md" <<'EOF'
---
title: The World of Eyum
---

# Eyum Handbook (Wiki)

Welcome. Start here or browse the sidebar.

- [[Chapter 1 - Introduction]]
- [[Chapter 2 - Core Rules]]
- [[Chapter 3 - Character Creation]]
EOF
  fi
}

set_base_url() {
  local CFG="$SITE_DIR/quartz.config.ts"
  if [ -f "$CFG" ]; then
    echo "Setting baseUrl to \"$BASE_URL\" in quartz.config.ts"
    if grep -q 'baseUrl:' "$CFG"; then
      sed -i "s|baseUrl: [\"'][^\"']*[\"']|baseUrl: \"$BASE_URL\"|g" "$CFG"
    else
      sed -i "0,/export default defineConfig({/s//export default defineConfig({\n  baseUrl: \"$BASE_URL\",/}" "$CFG"
    fi
  fi
}

build_site() {
  echo "Building site..."
  pushd "$SITE_DIR" >/dev/null
    if jq -re '.scripts.build' package.json >/dev/null 2>&1; then
      npm run build
    else
      npx quartz build
    fi
  popd >/dev/null
  echo "Built to $PUBLIC_DIR"
}

serve_site() {
  echo "Starting local server..."
  pushd "$SITE_DIR" >/dev/null
    if jq -re '.scripts["build:serve"]' package.json >/dev/null 2>&1; then
      npm run build:serve
    else
      npx quartz build --serve
    fi
  popd >/dev/null
  # Quartz prints the local URL (usually http://localhost:8080)
}

# ===== Main =====
ensure_node22
ensure_quartz_project
install_deps
sync_content
ensure_index
set_base_url
build_site

case "$POST_BUILD_ACTION" in
  serve)  serve_site ;;
  none)   echo "Done. Static files at: $PUBLIC_DIR" ;;
  *)      echo "Usage: $0 [serve|none]"; exit 1 ;;
esac
