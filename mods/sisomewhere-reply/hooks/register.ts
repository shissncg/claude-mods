import type { Register } from 'claude-code'

// SI Everywhere replies: what you send a session from your phone, the web or
// your glasses becomes its next prompt. The SI Everywhere agent (`sisomewhere
// actions on`) checks the reply came from one of your linked devices,
// decrypts it and appends it to this session's inbox file; this mod reads the
// file every 2 seconds and submits each line as a prompt, which Claude Code
// queues until the session is idle.
//
//   ~/.config/sisomewhere/inbox/<session id>.ready   written at start: replies can come here
//   ~/.config/sisomewhere/inbox/<session id>.jsonl   {"text": "...", "at": 1791600000.1} per line
//
// Sessions a person is at only: the terminal REPL, and the Claude desktop app's
// sessions, which run through the SDK (so not `isInteractive`) but are
// attended. A `-p` run is skipped: a closed session gets its reply through a
// background `claude -p --resume`, which the agent starts itself.

const POLL_MS = 2000

/** The lines' texts, in order; blank and broken lines are skipped. */
export function texts(inbox: string): string[] {
  const out: string[] = []
  for (const line of inbox.split('\n')) {
    if (!line.trim()) continue
    try {
      const { text } = JSON.parse(line) as { text?: unknown }
      if (typeof text === 'string' && text.trim()) out.push(text)
    } catch {
      // a half-written line: the agent writes whole lines, so skip it
    }
  }
  return out
}

/** A desktop app session: the app says a person is attending it. */
async function attended($: { env: { get(name: string): Promise<string | undefined> } }): Promise<boolean> {
  const entry = await $.env.get('CLAUDE_CODE_ENTRYPOINT')
  const seen = await $.env.get('CLAUDE_CODE_SESSION_ATTENDED')
  return entry === 'claude-desktop' || seen === '1'
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    try {
      if (!e.isInteractive && !(await attended($))) return result
      const home = await $.env.get('HOME')
      if (!home) return result
      const id = await $.session.id()
      const dir = `${home}/.config/sisomewhere/inbox`
      await $.fs.write(`${dir}/${id}.ready`, `${Math.floor(Date.now() / 1000)}\n`)
      const inbox = `${dir}/${id}.jsonl`
      $.clock.every(POLL_MS, async () => {
        let body = ''
        try {
          body = String(await $.fs.read(inbox))
        } catch {
          return // nothing sent yet
        }
        if (!body.trim()) return
        await $.fs.write(inbox, '')
        for (const text of texts(body)) {
          void $.prompt.submit({ text })
        }
      })
    } catch {
      // replies just won't arrive here; the session itself is unaffected
    }
    return result
  })
}
