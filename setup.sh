#!/usr/bin/env bash
# Installs the mods in setup/mods.conf and restores their saved settings.
#
#   ./setup.sh           install what's missing, then restore settings from setup/store/
#   ./setup.sh --dev     same, but register this checkout as the shissncg-mods marketplace,
#                        so edits to mods/ load without pushing
#   ./setup.sh save      copy this machine's mod settings into setup/store/ (then commit them)
#
# Safe to run again: it skips marketplaces and plugins that are already there.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
CONF="$REPO/setup/mods.conf"
SAVED="$REPO/setup/store"
STORE="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/store"
MIN_VERSION="2.1.287"

say() { printf '%s\n' "$*"; }

# Each line of mods.conf as "<plugin>@<marketplace> <repo>".
entries() { grep -v '^\s*#' "$CONF" | grep -v '^\s*$' | awk '{print $1, $2}'; }

# A mod's settings file: <plugin>_<marketplace>-<first 12 hex of sha256(id)>.json
store_file() {
  local id="$1" name="${1%@*}" market="${1#*@}"
  printf '%s_%s-%s.json' "$name" "$market" "$(printf '%s' "$id" | shasum -a 256 | cut -c1-12)"
}

save() {
  mkdir -p "$SAVED"
  local id repo file count=0
  while read -r id repo; do
    file="$(store_file "$id")"
    if [[ -f "$STORE/$file" ]]; then
      cp "$STORE/$file" "$SAVED/$file"
      say "saved    $id"
      count=$((count + 1))
    fi
  done < <(entries)
  say "Saved $count settings file(s) to setup/store/. Commit them to carry them to other machines."
}

version_ok() {
  local have
  have="$(claude --version 2>/dev/null | awk '{print $1}')"
  [[ -n "$have" ]] || { say "claude isn't on PATH. Install Claude Code first: https://claude.com/claude-code"; exit 1; }
  if [[ "$(printf '%s\n%s\n' "$MIN_VERSION" "$have" | sort -V | head -1)" != "$MIN_VERSION" ]]; then
    say "Claude Code $have is too old for mods (needs $MIN_VERSION+). Run: claude update"
    exit 1
  fi
}

install() {
  local dev="$1"
  version_ok
  local markets plugins id repo market source
  markets="$(claude plugin marketplace list --json)"
  plugins="$(claude plugin list --json)"

  while read -r id repo; do
    market="${id#*@}"
    source="$repo"
    [[ "$dev" == 1 && "$market" == "shissncg-mods" ]] && source="$REPO"

    if grep -q "\"name\": \"$market\"" <<<"$markets"; then
      say "have     marketplace $market"
    else
      say "add      marketplace $market ($source)"
      claude plugin marketplace add "$source" >/dev/null
      markets="$(claude plugin marketplace list --json)"
    fi

    if grep -q "\"id\": \"$id\"" <<<"$plugins"; then
      say "have     $id"
    else
      say "install  $id"
      claude plugin install "$id" >/dev/null
    fi
  done < <(entries)

  restore
  say "Done. Start a new Claude Code session (or run /reload-plugins) to load them."
}

# Copies saved settings into place, keeping any existing file as <file>.bak.
restore() {
  [[ -d "$SAVED" ]] || return 0
  mkdir -p "$STORE"
  local saved file
  for saved in "$SAVED"/*.json; do
    [[ -e "$saved" ]] || continue
    file="$(basename "$saved")"
    if [[ -f "$STORE/$file" ]] && cmp -s "$saved" "$STORE/$file"; then
      continue
    fi
    [[ -f "$STORE/$file" ]] && cp "$STORE/$file" "$STORE/$file.bak"
    cp "$saved" "$STORE/$file"
    say "restored settings ${file%%_*}"
  done
}

case "${1:-}" in
  save) save ;;
  --dev) install 1 ;;
  "") install 0 ;;
  *) say "usage: ./setup.sh [--dev | save]"; exit 1 ;;
esac
