import type { Register } from 'claude-code'

// Claude Code's plan limits (the 5-hour and weekly windows, percent used and
// when each resets), saved to ~/.config/sisomewhere/usage/ whenever a window
// moves, so the SI Somewhere agent can show them on every screen. Claude Code
// hands these figures to mods and status lines only; reading them here needs
// no login, token or API call. One file per Claude config folder, so a second
// account (CLAUDE_CONFIG_DIR) keeps its own:
//
//   {"config_dir": "/Users/me/.claude", "updated": 1791600000,
//    "limits": [{"kind": "five_hour", "percent_used": 23.5, "resets_at": "2026-10-10T03:00:00Z"}]}
//
// Display only: it never blocks or changes anything, and a failed write is dropped.

type Limit = { kind: string; percent_used: number; resets_at: string | null }

export function fileName(configDir: string): string {
  return `claude-${configDir.replace(/\/+$/, '').replace(/[^A-Za-z0-9._-]/g, '_')}.json`
}

export const register: Register = on => {
  on('session.measure', async ($, e, next) => {
    const result = await next(e)
    if (!e.changed.includes('rateLimits') || e.rateLimits.length === 0) {
      return result
    }
    try {
      const home = await $.env.get('HOME')
      if (!home) {
        return result
      }
      const configDir = (await $.env.get('CLAUDE_CONFIG_DIR')) || `${home}/.claude`
      const limits: Limit[] = e.rateLimits.map(limit => ({
        kind: limit.kind,
        percent_used: limit.percentUsed,
        resets_at: limit.resetsAt ?? null,
      }))
      const body = { config_dir: configDir, updated: Math.floor(Date.now() / 1000), limits }
      await $.fs.write(`${home}/.config/sisomewhere/usage/${fileName(configDir)}`, JSON.stringify(body) + '\n')
    } catch {
      // the next measurement writes again
    }
    return result
  })
}
