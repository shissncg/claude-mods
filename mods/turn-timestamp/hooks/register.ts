import type { Register } from 'claude-code'

function took(ms: number): string {
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m${String(seconds % 60).padStart(2, '0')}s`
  return `${Math.floor(minutes / 60)}h${String(minutes % 60).padStart(2, '0')}m`
}

export const register: Register = on => {
  let tools = 0

  on('prompt.submit', ($, e, next) => {
    tools = 0

    return next(e)
  })

  on('tool.call', ($, e, next) => {
    tools += 1

    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    // Subagent turns end inside the main turn; stamp only the main one.
    if (e.agentId !== undefined) {
      return done
    }

    // The host's `date` knows the local time zone; the module's own clock may not.
    let when: string
    try {
      const out = await $.process.run(['date', '+%a %Y-%m-%d %H:%M:%S %Z'], { timeoutMs: 2000 })
      when = out.exitCode === 0 ? out.stdout.trim() : new Date(await $.clock.now()).toISOString()
    } catch {
      when = new Date(await $.clock.now()).toISOString()
    }

    const parts = [when, `took ${took(e.durationMs)}`]
    if (tools > 0) parts.push(`${tools} tool call${tools === 1 ? '' : 's'}`)
    if (e.isAborted) parts.push('interrupted')
    $.ui.log(`── ${parts.join(' · ')}`)

    return done
  })
}
