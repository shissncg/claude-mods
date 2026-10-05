#!/bin/sh
# Make this machine report its AI coding sessions to an ai-monitor hub.
#
# For a Coder workspace startup script, a second laptop, or any Linux/macOS box:
#
#   export AI_METER_HUB_URL=https://ai-monitor.practicalai.cc
#   export AI_METER_HUB_TOKEN=<the hub's WRITE_TOKEN>
#   export AI_METER_MACHINE=<optional label; default: CODER_WORKSPACE_NAME or hostname>
#   curl -fsSL https://raw.githubusercontent.com/shissncg/claude-mods/main/mods/ai-meter-agents/bootstrap.sh | sh
#
# It writes ~/.config/claude-usage-monitor/hub.json (mode 600), installs the
# hook script, adds hooks for Codex, Grok and Antigravity (whether or not
# they are installed yet), and installs the Claude Code plugin when `claude`
# is on PATH, so run it after the harnesses are installed.
# Idempotent: safe to run on every workspace start. Needs python3 and curl.
set -eu

: "${AI_METER_HUB_URL:?set AI_METER_HUB_URL}"
: "${AI_METER_HUB_TOKEN:?set AI_METER_HUB_TOKEN (the hub write token)}"
RAW="${AI_METER_RAW:-https://raw.githubusercontent.com/shissncg/claude-mods/main/mods/ai-meter-agents}"
CONF="$HOME/.config/claude-usage-monitor"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$CONF/hooks"
umask 077
python3 - "$CONF/hub.json" <<'EOF'
import json, os, sys
conf = {"url": os.environ["AI_METER_HUB_URL"], "write_token": os.environ["AI_METER_HUB_TOKEN"]}
if os.environ.get("AI_METER_MACHINE"):
    conf["machine"] = os.environ["AI_METER_MACHINE"]
open(sys.argv[1], "w").write(json.dumps(conf, indent=2) + "\n")
EOF
umask 022

# The hook script and the installer for the other CLIs' hook configs.
mkdir -p "$TMP/hooks"
curl -fsSL "$RAW/hooks/agent_state.py" -o "$TMP/hooks/agent_state.py"
curl -fsSL "$RAW/install_other_tools.py" -o "$TMP/install_other_tools.py"
# Every CLI, present or not: in a Coder template this can run before they are
# installed, and a hook file for a missing CLI is harmless.
python3 "$TMP/install_other_tools.py"

# Claude Code: the plugin carries the same hooks.
if command -v claude >/dev/null 2>&1; then
    claude plugin marketplace add shissncg/claude-mods >/dev/null 2>&1 || true
    claude plugin install ai-meter-agents@shissncg-mods >/dev/null 2>&1 \
        && echo "claude: ai-meter-agents plugin installed" \
        || echo "claude: plugin install failed; run: claude plugin install ai-meter-agents@shissncg-mods"
fi
echo "ai-meter: reporting to $AI_METER_HUB_URL as ${AI_METER_MACHINE:-${CODER_WORKSPACE_NAME:-$(hostname -s)}}"
