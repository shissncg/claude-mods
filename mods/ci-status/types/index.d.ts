export type Run = {
  id: number
  name: string
  branch: string
  status: string
  conclusion: string
  createdAt: string
}

export type Snapshot = { runs: Run[]; error: string | null; checkedAt: number }

declare module 'claude-code' {
  interface PluginState {
    'ci-status': { snapshot: Snapshot | null }
  }
}
