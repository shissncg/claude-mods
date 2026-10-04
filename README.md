# Interesting Claude mods

Small [Claude Code mods](https://claude.com/blog/claude-code-mods): TypeScript hook modules that run before, after or instead of what Claude Code does.

| Mod | What it does |
| --- | --- |
| [`turn-timestamp`](mods/turn-timestamp) | Ends every turn with `✻ 2026-10-03 19:05 CDT · 3s · 1 tool call`, so scrollback in multi-day sessions shows when each turn finished. In the terminal it replaces Claude Code's own end-of-turn line (`✻ Churned for 1s`); where that line isn't drawn (the desktop Code tab) it adds its own. Display only. |
| [`ci-status`](mods/ci-status) | `/ci` opens a pane listing the repo's latest GitHub Actions runs (via `gh`), refreshes every 30s, shows `CI: N running` in the status line and a toast when a run finishes. |

## Install

```bash
claude plugin marketplace add shissncg/claude-mods
claude plugin install turn-timestamp@shissncg-mods
```

Or try one for a session without installing:

```bash
claude --plugin-dir mods/turn-timestamp --plugin-dir mods/ci-status
```

Check one with `claude plugin validate mods/<name>`. Mods need a recent Claude Code build: older CLIs report `"session.start" is not an event`.
