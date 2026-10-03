import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Run, Snapshot } from '../types'

const PANE = 'ci-status'
const POLL_MS = 30_000
const FIELDS = 'databaseId,displayTitle,headBranch,status,conclusion,createdAt'

const snapshot = atom({ plugin: 'ci-status', key: 'snapshot' } as const, null)

function mark(run: Run): [string, string] {
  if (run.status !== 'completed') return ['●', 'yellow']
  if (run.conclusion === 'success') return ['✔', 'green']
  if (run.conclusion === 'skipped' || run.conclusion === 'cancelled') return ['○', 'gray']
  return ['✘', 'red']
}

function age(createdAt: string, now: number): string {
  const minutes = Math.max(0, Math.round((now - Date.parse(createdAt)) / 60_000))
  if (minutes < 60) return `${minutes}m`
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)}h`
  return `${Math.round(minutes / 60 / 24)}d`
}

export const register: Register = on => {
  let refresh: (() => Promise<void>) | undefined
  let stopPolling: (() => void) | undefined

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'ci',
      description: 'Show the latest GitHub Actions runs for this repo in a pane',
    })

    refresh = async () => {
      const now = await $.clock.now()
      let fresh: Snapshot
      try {
        const out = await $.process.run(['gh', 'run', 'list', '--limit', '15', '--json', FIELDS])
        if (out.exitCode !== 0) {
          fresh = { runs: [], error: out.stderr.trim() || `gh exited ${out.exitCode}`, checkedAt: now }
        } else {
          const raw = JSON.parse(out.stdout) as Array<Record<string, string | number>>
          const runs: Run[] = raw.map(r => ({
            id: Number(r.databaseId),
            name: String(r.displayTitle),
            branch: String(r.headBranch),
            status: String(r.status),
            conclusion: String(r.conclusion ?? ''),
            createdAt: String(r.createdAt),
          }))
          fresh = { runs, error: null, checkedAt: now }
        }
      } catch (err) {
        fresh = { runs: [], error: `could not run gh: ${String(err)}`, checkedAt: now }
      }

      const previous = await read($, snapshot)
      await update($, snapshot, () => fresh)

      // Toast when a run that was in progress has finished.
      for (const run of fresh.runs) {
        const before = previous?.runs.find(one => one.id === run.id)
        if (before !== undefined && before.status !== 'completed' && run.status === 'completed') {
          $.ui.toast(`CI ${run.conclusion}: ${run.name} (${run.branch})`)
        }
      }
      const running = fresh.runs.filter(run => run.status !== 'completed').length
      $.ui.status(running > 0 ? `CI: ${running} running` : undefined)
    }

    return next(e)
  })

  on('command.run', { command: 'ci' }, async $ => {
    await $.ui.open({ id: PANE, title: 'CI runs' })
    void refresh?.()
    stopPolling ??= $.clock.every(POLL_MS, () => void refresh?.())

    return { text: 'CI pane opened; it refreshes every 30s.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const snap = await read($, snapshot)
    const now = await $.clock.now()
    const room = Math.max(1, (e.viewport?.rows ?? 24) - 5)

    return (
      <Box flexDirection="column">
        {snap === null && <Text dimColor>Loading…</Text>}
        {snap?.error != null && <Text color="red">{snap.error}</Text>}
        {snap !== null && snap.error === null && snap.runs.length === 0 && (
          <Text dimColor>No workflow runs in this repo yet.</Text>
        )}
        {snap?.runs.slice(0, room).map(run => {
          const [icon, color] = mark(run)
          return (
            <Box key={String(run.id)}>
              <Text color={color}>{icon} </Text>
              <Text wrap="truncate-end">
                {run.name} <Text dimColor>{run.branch} · {age(run.createdAt, now)}</Text>
              </Text>
            </Box>
          )
        })}
        <Box marginTop={1}>
          <Button key="refresh" label="Refresh" onPress={() => void refresh?.()} />
        </Box>
      </Box>
    )
  })
}
