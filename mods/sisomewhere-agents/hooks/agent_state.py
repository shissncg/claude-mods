#!/usr/bin/env python3
"""Record what an AI coding session is doing, for the SI Somewhere board.

Every hook event rewrites one JSON file per session in AGENTS_DIR. The SI Somewhere
daemon (github.com/CyberStreamStudios/SISomewhere, daemon/agent_feed.py) reads the files and
shows them on the board's Agents page. File fields:

  id        session id
  provider  claude | codex | grok | gemini (Antigravity)
  cwd       working directory of the session
  state     working | needs | done | idle
  detail    what the state is about: the current tool, or why it needs you
  prompt    the last prompt you sent, shortened
  since     epoch seconds when the session entered its current state
  updated   epoch seconds of the last hook event
  pid       the session's CLI process, so the daemon can drop dead sessions

One script serves every CLI; they differ only in spelling:

  claude   Claude Code plugin hooks, snake_case fields, event in hook_event_name
  codex    ~/.codex/hooks.json, Claude-style fields, plus PermissionRequest
  grok     ~/.grok/hooks/*.json, camelCase fields (sessionId, toolName, toolInput)
  gemini   Antigravity ~/.gemini/config/hooks.json: camelCase (conversationId,
           workspacePaths, toolCall with a ready-made toolSummary), no event
           name in the payload (pass --event). Only PreInvocation, PostToolUse
           and Stop are hooked: Antigravity reads any PreToolUse answer as a
           decision and has no "no opinion" one, so even {} would deny every
           tool call. The tool is therefore named after it runs.

Usage: agent_state.py [--provider NAME] [--event NAME]

Hub: when a hub is configured (~/.config/sisomewhere/hub.json with
"url" and "write_token", or SISOMEWHERE_HUB_URL / SISOMEWHERE_HUB_TOKEN), each
visible change is also sent to it from a detached background process, so a
slow network never holds up the session. Only the project folder's name, the
state, the tool label and a 40-character prompt snippet leave the machine.
The machine is named by SISOMEWHERE_MACHINE, else CODER_WORKSPACE_NAME, else the
short hostname.

Always exits 0, and prints nothing except "{}" for Antigravity, whose hooks
must answer with a JSON object ({} = no decision). SessionStart and
UserPromptSubmit stdout would reach the model, and exit 2 means "block" in
these CLIs, so a failing hook must never get in a session's way. Runs on the
system python3 (3.9 on macOS).
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

AGENTS_DIR = Path.home() / ".config" / "sisomewhere" / "agents"
HUB_CONFIG = Path.home() / ".config" / "sisomewhere" / "hub.json"
# Before the SI Somewhere rename (machines not yet re-bootstrapped).
LEGACY_HUB_CONFIG = Path.home() / ".config" / "claude-usage-monitor" / "hub.json"
HUB_RESEND_S = 300      # keep a quiet session alive on the hub
HUB_TIMEOUT_S = 5
HUB_PROMPT_CHARS = 40
PROVIDERS = ("claude", "codex", "grok", "gemini")
# Process names to look for when finding the session's own CLI process.
PROCESS_NAMES = {"claude": ("claude",), "codex": ("codex",), "grok": ("grok", "agent"),
                 "gemini": ("agy",)}
# Tool names each CLI uses, mapped onto Claude Code's.
TOOL_ALIASES = {
    "run_terminal_command": "Bash", "run_command": "Bash", "shell": "Bash",
    "exec_command": "Bash", "local_shell": "Bash",
    "read_file": "Read", "view_file": "Read",
    "write": "Write", "write_to_file": "Write",
    "search_replace": "Edit", "apply_patch": "Edit", "replace_file_content": "Edit",
    "list_dir": "LS", "grep_search": "Grep", "find_by_name": "Glob",
    "web_fetch": "WebFetch", "read_url_content": "WebFetch", "search_web": "WebSearch",
    "multi_replace_file_content": "Edit", "invoke_subagent": "Agent",
}


def shorten(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def tool_label(name: str, tool_input: dict) -> str:
    """A short "Tool: target" line, e.g. "Bash: Build firmware" or "Edit: ui.cpp"."""
    def field(*keys: str) -> str:
        for key in keys:
            value = tool_input.get(key)
            if isinstance(value, list):
                value = " ".join(str(v) for v in value)
            if isinstance(value, str) and value.strip():
                return value
        return ""

    summary = tool_input.get("toolSummary")      # Antigravity: "Read ROADMAP.md"
    if isinstance(summary, str) and summary.strip():
        return summary
    if name.startswith("mcp__"):
        # mcp__<server>__<tool>: server names are often opaque ids, so keep the tool.
        return name.split("__")[-1]
    name = TOOL_ALIASES.get(name, name)
    if name == "Bash":
        target = field("description", "command", "CommandLine", "cmd")
    elif name in ("Read", "Edit", "Write", "NotebookEdit"):
        target = os.path.basename(field("file_path", "path", "notebook_path", "AbsolutePath",
                                        "TargetFile", "filename"))
    elif name in ("Grep", "Glob"):
        target = field("pattern", "Query", "query")
    elif name == "WebFetch":
        target = urlparse(field("url", "Url")).netloc
    elif name == "WebSearch":
        target = field("query", "Query")
    elif name in ("Agent", "Task"):
        target = field("description")
    elif name == "Skill":
        target = field("skill")
    else:
        target = ""
    return f"{name}: {target}" if target else name


def normalize(event: dict, provider: str, event_name: str | None) -> dict:
    """The fields this script uses, whichever spelling the CLI sent."""
    tool = event.get("toolCall") if isinstance(event.get("toolCall"), dict) else {}
    paths = event.get("workspacePaths")
    return {
        "event": event_name or event.get("hook_event_name") or "",
        "session": event.get("session_id") or event.get("sessionId") or event.get("conversationId") or "",
        "cwd": event.get("cwd") or event.get("workspaceRoot")
               or (paths[0] if isinstance(paths, list) and paths else ""),
        "tool": event.get("tool_name") or event.get("toolName") or tool.get("name") or "",
        "input": event.get("tool_input") or event.get("toolInput") or tool.get("args") or {},
        "prompt": event.get("prompt") or "",
        "source": event.get("source") or "",
        "kind": event.get("notification_type") or event.get("notificationType") or "",
        "message": event.get("message") or "",
        # Antigravity has no passive PreToolUse, so PostToolUse names the tool.
        "label_after": provider == "gemini",
    }


def session_pid(provider: str) -> int | None:
    """The nearest ancestor process named like the provider's CLI."""
    names = PROCESS_NAMES.get(provider, ())
    pid = os.getppid()
    for _ in range(8):
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
        if os.path.basename(comm.strip()).lower().startswith(names):
            return pid
        try:
            pid = int(ppid)
        except ValueError:
            return None
    return None


def apply_event(state: dict, ev: dict, now: float) -> dict | None:
    """Return the session's new state for one hook event, or None to delete it."""
    name = ev["event"]
    if name == "SessionEnd":
        return None

    def enter(new_state: str, detail: str) -> None:
        if state.get("state") != new_state:
            state["state"] = new_state
            # Working counts from the prompt, so a permission stop doesn't reset it.
            state["since"] = state.get("turn", now) if new_state == "working" else now
        state["detail"] = detail

    def start_turn() -> None:
        state["turn"] = now
        state["tool"] = "Thinking"
        state.pop("state", None)
        enter("working", "Thinking")

    if name == "SessionStart":
        # A compaction restarts the session mid-turn; keep whatever it was doing.
        if ev["source"] != "compact" or "state" not in state:
            enter("idle", "")
    elif name == "UserPromptSubmit":
        state["prompt"] = shorten(ev["prompt"], 120)
        start_turn()
    elif name == "PreInvocation":
        # Antigravity has no prompt event; a model call outside a turn starts one.
        if state.get("state") != "working":
            start_turn()
    elif name == "PreToolUse":
        tool = ev["tool"]
        if tool == "AskUserQuestion":
            enter("needs", "Question for you")
        elif tool == "ExitPlanMode":
            enter("needs", "Plan ready for review")
        else:
            if state.get("state") != "working" and "turn" not in state:
                state["turn"] = now
            state["tool"] = tool_label(tool, ev["input"] if isinstance(ev["input"], dict) else {})
            enter("working", state["tool"])
    elif name == "PostToolUse":
        if state.get("state") == "needs":
            enter("working", state.get("tool", ""))
        elif ev["label_after"] and ev["tool"]:
            state["tool"] = tool_label(ev["tool"], ev["input"] if isinstance(ev["input"], dict) else {})
            enter("working", state["tool"])
    elif name == "PermissionRequest":
        label = TOOL_ALIASES.get(ev["tool"], ev["tool"])
        enter("needs", f"Allow {label}?" if label else "Permission needed")
    elif name == "Notification":
        if ev["kind"] == "permission_prompt" or "permission" in ev["message"].lower():
            match = re.search(r"permission to use (.+)$", ev["message"])
            enter("needs", f"Allow {match.group(1)}?" if match else "Permission needed")
        elif ev["kind"] == "elicitation_dialog":
            enter("needs", "Input requested")
    elif name == "Stop":
        state.pop("turn", None)
        enter("done", "")
    else:
        return state

    state["updated"] = now
    return state


def hub_config() -> dict | None:
    """{"url", "token", "machine"} when a hub is configured, else None."""
    try:
        conf = json.loads((HUB_CONFIG if HUB_CONFIG.exists() else LEGACY_HUB_CONFIG).read_text())
    except (OSError, ValueError):
        conf = {}
    env = lambda name: os.environ.get("SISOMEWHERE_" + name) or os.environ.get("AI_METER_" + name)
    url = env("HUB_URL") or conf.get("url")
    token = env("HUB_TOKEN") or conf.get("write_token")
    if not url or not token:
        return None
    machine = (env("MACHINE") or conf.get("machine")
               or os.environ.get("CODER_WORKSPACE_NAME") or socket.gethostname().split(".")[0])
    return {"url": url.rstrip("/"), "token": token, "machine": machine}


def hub_update(state: dict | None, file_id: str, machine: str, now: float) -> dict:
    """What the hub gets for one session: no paths, a short prompt."""
    if state is None:
        return {"id": file_id, "machine": machine, "deleted": True, "updated": now}
    return {
        "id": file_id, "machine": machine,
        "provider": state.get("provider", "claude"),
        "project": os.path.basename(str(state.get("cwd", "")).rstrip("/")),
        "state": state["state"], "detail": state.get("detail", ""),
        "prompt": shorten(state.get("prompt", ""), HUB_PROMPT_CHARS),
        "since": state.get("since", now), "updated": state.get("updated", now),
    }


def send_to_hub(hub: dict, update: dict) -> None:
    """POST from a detached child so the hook returns at once."""
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--send", hub["url"], json.dumps(update)],
        env={**os.environ, "SISOMEWHERE_HUB_TOKEN": hub["token"]},
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True)


def post_update(url: str, body: str) -> None:
    request = urllib.request.Request(
        f"{url}/v1/sessions", data=body.encode(), method="POST",
        headers={"Authorization": f"Bearer {os.environ.get('SISOMEWHERE_HUB_TOKEN', '')}",
                 "Content-Type": "application/json", "User-Agent": "sisomewhere-agents"})
    urllib.request.urlopen(request, timeout=HUB_TIMEOUT_S).read()


def parse_args(argv: list[str]) -> tuple[str, str | None]:
    provider, event = "claude", None
    for flag, value in zip(argv, argv[1:]):
        if flag == "--provider" and value in PROVIDERS:
            provider = value
        elif flag == "--event":
            event = value
    return provider, event


def main(provider: str, event_name: str | None) -> None:
    ev = normalize(json.load(sys.stdin), provider, event_name)
    session_id = re.sub(r"[^A-Za-z0-9_-]", "", str(ev["session"]))
    if not session_id:
        return
    # Prefix non-Claude ids so a session id can't collide across CLIs.
    file_id = session_id if provider == "claude" else f"{provider}-{session_id}"
    path = AGENTS_DIR / f"{file_id}.json"
    try:
        state = json.loads(path.read_text())
    except (OSError, ValueError):
        state = {}

    now = time.time()
    hub = hub_config()
    shown_before = (state.get("state"), state.get("detail"), state.get("prompt"))
    new_state = apply_event(state, ev, now)
    if new_state is None:
        path.unlink(missing_ok=True)
        if hub:
            send_to_hub(hub, hub_update(None, file_id, hub["machine"], now))
        return
    if "state" not in new_state:
        return  # an event this script doesn't track, for a session it hasn't seen

    new_state["id"] = file_id
    new_state["provider"] = provider
    if ev["cwd"]:
        new_state["cwd"] = ev["cwd"]
    if "pid" not in new_state:
        new_state["pid"] = session_pid(provider)

    # Tell the hub when something visible changed, or to keep a quiet session alive.
    shown_now = (new_state.get("state"), new_state.get("detail"), new_state.get("prompt"))
    if hub and (shown_now != shown_before or now - new_state.get("hub_sent", 0) > HUB_RESEND_S):
        new_state["hub_sent"] = now
        send_to_hub(hub, hub_update(new_state, file_id, hub["machine"], now))

    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(new_state))
    os.replace(tmp, path)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--send"]:
        # The detached child: one POST, errors ignored.
        try:
            post_update(sys.argv[2], sys.argv[3])
        except Exception:
            pass
        sys.exit(0)
    provider, event_name = parse_args(sys.argv[1:])
    try:
        main(provider, event_name)
    except Exception:
        pass
    if provider == "gemini":
        print("{}")
    sys.exit(0)
