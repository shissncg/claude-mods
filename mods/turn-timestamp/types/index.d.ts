export type Stamp = { durationMs: number; answer: string; when: string; tools: number }

declare module 'claude-code' {
  interface PluginState {
    'turn-timestamp': { stamps: Stamp[] }
  }
}
