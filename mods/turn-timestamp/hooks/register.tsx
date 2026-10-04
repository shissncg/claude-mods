import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Stamp } from '../types'

// Each main-loop turn's end, matched to its end-of-turn row by duration.
const stamps = atom({ plugin: 'turn-timestamp', key: 'stamps' } as const, [])

function took(ms: number): string {
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
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
    // Subagent turns end inside the main turn; stamp only the main one.
    if (e.agentId === undefined) {
      // The host's `date` knows the local time zone; the module's own clock may not.
      let when: string
      try {
        const out = await $.process.run(['date', '+%Y-%m-%d %H:%M %Z'], { timeoutMs: 2000 })
        when = out.exitCode === 0 ? out.stdout.trim() : ''
      } catch {
        when = ''
      }
      if (when === '') {
        when = new Date(await $.clock.now()).toISOString().slice(0, 16).replace('T', ' ') + ' UTC'
      }
      const stamp: Stamp = { durationMs: e.durationMs, when, tools }
      await update($, stamps, list => [...list, stamp].slice(-500))
    }

    return next(e)
  })

  on('ui.render', { component: 'TurnDuration' }, async ($, e, next) => {
    const list = await read($, stamps)
    const stamp = list.findLast(one => one.durationMs === e.props.durationMs)
    if (stamp === undefined) {
      return next(e)
    }

    const { Text } = $.ui.resolve(e)
    const parts = [stamp.when, took(stamp.durationMs)]
    if (stamp.tools > 0) parts.push(`${stamp.tools} tool call${stamp.tools === 1 ? '' : 's'}`)

    return <Text dimColor>✻ {parts.join(' · ')}</Text>
  })
}
