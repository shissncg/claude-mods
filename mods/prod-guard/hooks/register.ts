import type { Register } from 'claude-code'

// Each rule names why a command counts as risky.
const RULES: ReadonlyArray<[RegExp, string]> = [
  [/\b(prod|production)\b/i, 'mentions production'],
  [/\bterraform\s+(apply|destroy)\b/, 'changes infrastructure'],
  [/\bkubectl\b.*\b(apply|delete|scale|rollout|edit|patch)\b/, 'changes a cluster'],
  [/\bgit\s+push\b.*(--force\b|-f\b|\s\+)/, 'force-pushes'],
  [/\bgit\s+push\b.*\b(main|master)\b/, 'pushes to the default branch'],
  [/\b(DROP|TRUNCATE)\s+(TABLE|DATABASE)\b/i, 'drops data'],
]

const RUN = 'Run it'
const BLOCK = 'Block it'

export const register: Register = on => {
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const hit = RULES.find(([pattern]) => pattern.test(e.command))
    if (hit === undefined) {
      return next(e)
    }

    const reason = hit[1]
    const preview = e.command.length > 80 ? `${e.command.slice(0, 77)}...` : e.command
    let answer: string
    try {
      answer = await $.ui.ask(`This command ${reason}: \`${preview}\`. Run it?`, {
        header: 'Prod guard',
        options: [BLOCK, RUN],
      })
    } catch {
      return { deny: `${$.plugin.name}: no one confirmed a command that ${reason}.` }
    }

    if (answer === RUN) {
      $.ui.toast(`Allowed: ${reason}`)
      return next(e)
    }

    const note = answer === BLOCK ? '' : ` The user said: ${answer}`
    return { deny: `${$.plugin.name}: the user blocked a command that ${reason}.${note}` }
  })
}
