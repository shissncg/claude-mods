#!/usr/bin/env python3
"""Feed Codex, Grok and Antigravity sessions to the ai-meter Agents page too.

Claude Code gets the feed from this plugin's own hooks. The other CLIs take
hooks from their own config files, so this script:

  1. copies hooks/agent_state.py to ~/.config/claude-usage-monitor/hooks/, a
     path that doesn't move with this checkout's branch;
  2. adds a hook entry per event to each CLI's config, next to whatever is
     already there:
       codex   ~/.codex/hooks.json             (merged; other hooks kept)
       grok    ~/.grok/hooks/ai-meter-agents.json   (its own file)
       agy     ~/.gemini/config/hooks.json     (merged under "ai-meter-agents")

Run it again after editing agent_state.py; it replaces only its own entries.
Every changed file is backed up once to <file>.bak-ai-meter first.

Usage: install_other_tools.py [--uninstall]
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HOME = Path.home()
SOURCE = Path(__file__).resolve().parent / "hooks" / "agent_state.py"
INSTALLED = HOME / ".config" / "claude-usage-monitor" / "hooks" / "agent_state.py"
MARKER = "claude-usage-monitor/hooks/agent_state.py"   # identifies our entries
TIMEOUT = 5

CODEX_FILE = HOME / ".codex" / "hooks.json"
CODEX_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
                "PermissionRequest", "Stop", "SessionEnd")
GROK_FILE = HOME / ".grok" / "hooks" / "ai-meter-agents.json"
GROK_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
               "Notification", "Stop", "SessionEnd")
AGY_FILE = HOME / ".gemini" / "config" / "hooks.json"
AGY_NAME = "ai-meter-agents"
AGY_FLAT = ("PreInvocation", "Stop")
# Never PreToolUse: Antigravity reads its answer as a decision, with no
# "no opinion" value, so even {} denies every tool call. PostToolUse is
# passive and carries the tool call, so the row names the tool after it runs.


def command(provider: str, event: str | None = None) -> str:
    # `|| true`: these CLIs read exit 2 as "block"; a missing script must not.
    extra = f" --event {event}" if event else ""
    return f'/usr/bin/python3 "{INSTALLED}" --provider {provider}{extra} || true'


def handler(provider: str, event: str | None = None) -> dict:
    return {"type": "command", "command": command(provider, event), "timeout": TIMEOUT}


def is_ours(group: dict) -> bool:
    return any(MARKER in str(h.get("command", "")) for h in group.get("hooks", []))


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict):
        raise SystemExit(f"{path} is not a JSON object; leaving it alone")
    return data


def save(path: Path, data: dict) -> None:
    backup = path.with_name(path.name + ".bak-ai-meter")
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def codex(install: bool) -> str:
    data = load(CODEX_FILE)
    hooks = data.setdefault("hooks", {})
    for event in list(hooks):
        hooks[event] = [g for g in hooks[event] if not is_ours(g)]
        if not hooks[event]:
            del hooks[event]
    if install:
        for event in CODEX_EVENTS:
            hooks.setdefault(event, []).append({"matcher": "", "hooks": [handler("codex")]})
    save(CODEX_FILE, data)
    return f"codex: {'added' if install else 'removed'} {len(CODEX_EVENTS)} events in {CODEX_FILE}"


def grok(install: bool) -> str:
    if not install:
        GROK_FILE.unlink(missing_ok=True)
        return f"grok: removed {GROK_FILE}"
    data = {"hooks": {event: [{"hooks": [handler("grok")]}] for event in GROK_EVENTS}}
    save(GROK_FILE, data)
    return f"grok: wrote {GROK_FILE}"


def agy(install: bool) -> str:
    data = load(AGY_FILE)
    data.pop(AGY_NAME, None)
    if install:
        entry: dict = {"PostToolUse": [{"matcher": "*", "hooks": [handler("gemini", "PostToolUse")]}]}
        for event in AGY_FLAT:
            entry[event] = [handler("gemini", event)]
        data[AGY_NAME] = entry
    save(AGY_FILE, data)
    return f"agy: {'added' if install else 'removed'} \"{AGY_NAME}\" in {AGY_FILE}"


def main() -> None:
    install = "--uninstall" not in sys.argv[1:]
    if install:
        INSTALLED.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE, INSTALLED)
        print(f"copied {SOURCE.name} -> {INSTALLED}")
    for step in (codex, grok, agy):
        print(step(install))
    if not install:
        INSTALLED.unlink(missing_ok=True)
        print(f"removed {INSTALLED}")
    print("New sessions pick this up; restart any CLI sessions already running.")


if __name__ == "__main__":
    main()
