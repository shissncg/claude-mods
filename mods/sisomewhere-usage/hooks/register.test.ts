import { expect, test } from 'claude-code/testing'
import { fileName } from './register'

test('one file per Claude config folder, safe to put in a path', () => {
  expect(fileName('/Users/me/.claude')).toBe('claude-_Users_me_.claude.json')
  expect(fileName('/Users/me/.claude-work/')).toBe('claude-_Users_me_.claude-work.json')
})
