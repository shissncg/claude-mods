# Interesting Claude mods

Small [Claude Code mods](https://claude.com/blog/claude-code-mods): TypeScript hook modules that run before, after or instead of what Claude Code does.

| Mod | What it does |
| --- | --- |
| [`turn-timestamp`](mods/turn-timestamp) | Ends every turn with a dim line like `── Sat 2026-10-03 18:58:04 CDT · took 4s · 1 tool call`, so scrollback in multi-day sessions shows when each turn finished. Display only; the model never sees it. |
| [`ci-status`](mods/ci-status) | `/ci` opens a pane listing the repo's latest GitHub Actions runs (via `gh`), refreshes every 30s, shows `CI: N running` in the status line and a toast when a run finishes. |

## Try one

```bash
claude --plugin-dir mods/turn-timestamp --plugin-dir mods/ci-status
```

Check one with `claude plugin validate mods/<name>`. Mods need a recent Claude Code build: older CLIs report `"session.start" is not an event`.
