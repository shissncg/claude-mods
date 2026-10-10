#!/bin/sh
# Make this machine report its AI coding sessions to an SI Somewhere hub.
#
# For a Coder workspace startup script, a second laptop, or any Linux/macOS box:
#
#   export SISOMEWHERE_HUB_URL=https://api.sisomewhere.cc
#   export SISOMEWHERE_HUB_TOKEN=<the hub's WRITE_TOKEN>
#   export SISOMEWHERE_MACHINE=<optional label; default: CODER_WORKSPACE_NAME or hostname>
#   curl -fsSL https://raw.githubusercontent.com/shissncg/claude-mods/main/mods/sisomewhere-agents/bootstrap.sh | sh
#
# It writes ~/.config/sisomewhere/hub.json (mode 600), installs the
# hook script, adds hooks for Codex, Grok and Antigravity (whether or not
# they are installed yet), and installs the Claude Code plugin when `claude`
# is on PATH, so run it after the harnesses are installed.
# Idempotent: safe to run on every workspace start. Needs python3 and curl.
set -eu

: "${SISOMEWHERE_HUB_URL:?set SISOMEWHERE_HUB_URL}"
: "${SISOMEWHERE_HUB_TOKEN:?set SISOMEWHERE_HUB_TOKEN (the hub write token)}"
RAW="${SISOMEWHERE_RAW:-https://raw.githubusercontent.com/shissncg/claude-mods/main/mods/sisomewhere-agents}"
CONF="$HOME/.config/sisomewhere"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$CONF/hooks"
umask 077
python3 - "$CONF/hub.json" <<'EOF'
import json, os, sys
conf = {"url": os.environ["SISOMEWHERE_HUB_URL"], "write_token": os.environ["SISOMEWHERE_HUB_TOKEN"]}
if os.environ.get("SISOMEWHERE_MACHINE"):
    conf["machine"] = os.environ["SISOMEWHERE_MACHINE"]
open(sys.argv[1], "w").write(json.dumps(conf, indent=2) + "\n")
EOF
umask 022

# The hook script and the installer for the other CLIs' hook configs.
mkdir -p "$TMP/hooks"
curl -fsSL "$RAW/hooks/agent_state.py" -o "$TMP/hooks/agent_state.py"
curl -fsSL "$RAW/install_other_tools.py" -o "$TMP/install_other_tools.py"
# Every CLI, present or not: in a Coder template this can run before they are
# installed, and a hook file for a missing CLI is harmless. It also replaces
# hook entries from before the SI Somewhere rename.
python3 "$TMP/install_other_tools.py"

# Before the rename this lived in ~/.config/claude-usage-monitor; drop the old
# copies of the token and the hook script (nothing points at them any more).
OLD="$HOME/.config/claude-usage-monitor"
rm -f "$OLD/hub.json" "$OLD/hooks/agent_state.py"
rmdir "$OLD/hooks" 2>/dev/null || true

# Claude Code: the plugin carries the same hooks. Benchmark images link it as
# claude-benchmark; it's the same binary and the same ~/.claude.
CLAUDE=""
for name in claude claude-benchmark; do
    if command -v "$name" >/dev/null 2>&1; then CLAUDE="$name"; break; fi
done
if [ -n "$CLAUDE" ]; then
    "$CLAUDE" plugin marketplace add shissncg/claude-mods >/dev/null 2>&1 || true
    "$CLAUDE" plugin marketplace update shissncg-mods >/dev/null 2>&1 || true
    "$CLAUDE" plugin uninstall ai-meter-agents@shissncg-mods >/dev/null 2>&1 || true   # its old name
    "$CLAUDE" plugin install sisomewhere-agents@shissncg-mods >/dev/null 2>&1 \
        && echo "claude: sisomewhere-agents plugin installed" \
        || echo "claude: plugin install failed; run: $CLAUDE plugin install sisomewhere-agents@shissncg-mods"
fi
echo "SI Somewhere: reporting to $SISOMEWHERE_HUB_URL as ${SISOMEWHERE_MACHINE:-${CODER_WORKSPACE_NAME:-$(hostname -s)}}"
