#!/usr/bin/env python3
"""Record what this Claude Code session is doing, for the ai-meter board.

Every hook event rewrites one JSON file per session in AGENTS_DIR. The ai-meter
daemon (github.com/shissncg/ai-meter, daemon/agent_feed.py) reads the files and
shows them on the board's Agents page. File fields:

  id       session id
  cwd      working directory of the session
  state    working | needs | done | idle
  detail   what the state is about: the current tool, or why it needs you
  prompt   the last prompt you sent, shortened
  since    epoch seconds when the session entered its current state
  updated  epoch seconds of the last hook event
  pid      the Claude Code process, so the daemon can drop dead sessions

Prints nothing and always exits 0: SessionStart and UserPromptSubmit stdout
would be added to the model's context, and a failing hook must never get in
the session's way. Runs on the system python3 (3.9 on macOS).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

AGENTS_DIR = Path.home() / ".config" / "claude-usage-monitor" / "agents"


def shorten(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def tool_label(name: str, tool_input: dict) -> str:
    """A short "Tool: target" line, e.g. "Bash: Build firmware" or "Edit: ui.cpp"."""
    def field(key: str) -> str:
        value = tool_input.get(key)
        return value if isinstance(value, str) else ""

    if name.startswith("mcp__"):
        # mcp__<server>__<tool>: server names are often opaque ids, so keep the tool.
        return name.split("__")[-1]
    if name == "Bash":
        target = field("description") or field("command")
    elif name in ("Read", "Edit", "Write", "NotebookEdit"):
        target = os.path.basename(field("file_path") or field("notebook_path"))
    elif name in ("Grep", "Glob"):
        target = field("pattern")
    elif name == "WebFetch":
        target = urlparse(field("url")).netloc
    elif name == "WebSearch":
        target = field("query")
    elif name in ("Agent", "Task"):
        target = field("description")
    elif name == "Skill":
        target = field("skill")
    else:
        target = ""
    return f"{name}: {target}" if target else name


def claude_pid() -> int | None:
    """The nearest ancestor process named claude, i.e. the session's own process."""
    pid = os.getppid()
    for _ in range(6):
        if pid <= 1:
            return None
        try:
            out = subprocess.run(
                ["ps", "-o", "ppid=,comm=", "-p", str(pid)],
                capture_output=True, text=True, timeout=2,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
        if not out:
            return None
        ppid, _, comm = out.partition(" ")
        if os.path.basename(comm.strip()).lower().startswith("claude"):
            return pid
        try:
            pid = int(ppid)
        except ValueError:
            return None
    return None


def apply_event(state: dict, event: dict, now: float) -> dict | None:
    """Return the session's new state for one hook event, or None to delete it."""
    name = event.get("hook_event_name", "")
    if name == "SessionEnd":
        return None

    def enter(new_state: str, detail: str) -> None:
        if state.get("state") != new_state:
            state["state"] = new_state
            # Working counts from the prompt, so a permission stop doesn't reset it.
            state["since"] = state.get("turn", now) if new_state == "working" else now
        state["detail"] = detail

    if name == "SessionStart":
        # A compaction restarts the session mid-turn; keep whatever it was doing.
        if event.get("source") != "compact" or "state" not in state:
            enter("idle", "")
    elif name == "UserPromptSubmit":
        state["prompt"] = shorten(event.get("prompt", ""), 120)
        state["turn"] = now
        state["tool"] = "Thinking"
        state.pop("state", None)
        enter("working", "Thinking")
    elif name == "PreToolUse":
        tool = event.get("tool_name", "")
        if tool == "AskUserQuestion":
            enter("needs", "Question for you")
        elif tool == "ExitPlanMode":
            enter("needs", "Plan ready for review")
        else:
            state["tool"] = tool_label(tool, event.get("tool_input") or {})
            enter("working", state["tool"])
    elif name == "PostToolUse":
        if state.get("state") == "needs":
            enter("working", state.get("tool", ""))
    elif name == "Notification":
        kind = event.get("notification_type", "")
        message = event.get("message", "")
        if kind == "permission_prompt" or "permission" in message.lower():
            match = re.search(r"permission to use (.+)$", message)
            enter("needs", f"Allow {match.group(1)}?" if match else "Permission needed")
        elif kind == "elicitation_dialog":
            enter("needs", "Input requested")
    elif name == "Stop":
        enter("done", "")
    else:
        return state

    state["updated"] = now
    return state


def main() -> None:
    event = json.load(sys.stdin)
    session_id = re.sub(r"[^A-Za-z0-9_-]", "", str(event.get("session_id", "")))
    if not session_id:
        return
    path = AGENTS_DIR / f"{session_id}.json"
    try:
        state = json.loads(path.read_text())
    except (OSError, ValueError):
        state = {}

    new_state = apply_event(state, event, time.time())
    if new_state is None:
        path.unlink(missing_ok=True)
        return

    new_state["id"] = session_id
    if event.get("cwd"):
        new_state["cwd"] = event["cwd"]
    if "pid" not in new_state:
        new_state["pid"] = claude_pid()

    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(new_state))
    os.replace(tmp, path)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
