# Interesting Claude mods

Small [Claude Code mods](https://claude.com/blog/claude-code-mods): TypeScript hook modules that run before, after or instead of what Claude Code does.

| Mod | What it does |
| --- | --- |
| [`turn-timestamp`](mods/turn-timestamp) | Ends every turn with `✻ 2026-10-03 19:05 CDT · 3s · 1 tool call`, so scrollback in multi-day sessions shows when each turn finished. In the terminal it replaces Claude Code's own end-of-turn line (`✻ Churned for 1s`); in the desktop Code tab, which draws no such line, it goes under Claude's last reply block. Display only. |
| [`ci-status`](mods/ci-status) | `/ci` opens a pane listing the repo's latest GitHub Actions runs (via `gh`), refreshes every 30s, shows `CI: N running` in the status line and a toast when a run finishes. |
| [`sisomewhere-agents`](mods/sisomewhere-agents) | Classic command hooks (no TypeScript) that record each session's state (working and on which tool, needs you, done) to `~/.config/sisomewhere/agents/`, one file per session. The [SI Somewhere](https://github.com/CyberStreamStudios/SISomewhere) daemon shows them on the desk display's Agents page. The same script feeds Codex, Grok and Antigravity sessions: `python3 mods/sisomewhere-agents/install_other_tools.py` adds it to their hook configs (`--uninstall` removes it). Silent: never blocks a tool call. Superseded on machines that run the SI Somewhere Go agent (`sisomewhere install`, in that repo's `agent/`), which hooks every harness itself and switches this plugin off. |
| [`sisomewhere-usage`](mods/sisomewhere-usage) | Saves Claude Code's plan limits (the 5-hour and weekly windows: percent used, when each resets) to `~/.config/sisomewhere/usage/` whenever a window moves, one file per Claude config folder. The SI Somewhere agent sends them to app.sisomewhere.cc and the desk display. Claude Code hands these figures to mods only, so this needs no login, token or API call. No UI. |

## Set up a machine

Installs every mod in [`setup/mods.conf`](setup/mods.conf) (mine and the community ones I use) and restores their saved settings, such as the neon-cyber skin:

```bash
git clone https://github.com/shissncg/claude-mods ~/Dev/claude-mods
~/Dev/claude-mods/setup.sh
```

- `./setup.sh --dev` registers this checkout as the marketplace instead of GitHub, so edits under `mods/` load without pushing.
- `./setup.sh save` copies this machine's mod settings into `setup/store/`; commit them to carry them to other machines.
- To add a mod, add a line to `setup/mods.conf`. Running the script again only installs what's missing.

Plugins turned on at claude.ai sync by themselves and don't need to be listed.

To install just one of mine:

```bash
claude plugin marketplace add shissncg/claude-mods
claude plugin install turn-timestamp@shissncg-mods
```

Or try one for a session without installing:

```bash
claude --plugin-dir mods/turn-timestamp --plugin-dir mods/ci-status
```

Check one with `claude plugin validate mods/<name>`. Mods need a recent Claude Code build: older CLIs report `"session.start" is not an event`.
