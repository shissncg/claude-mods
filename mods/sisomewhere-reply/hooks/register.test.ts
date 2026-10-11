import { expect, test } from 'claude-code/testing'
import { texts } from './register'

test('each whole line is one reply, in order', () => {
  const inbox = '{"text":"run the tests","at":1}\n\n{"text":"then open a PR","at":2}\n{"text":"half'
  expect(texts(inbox)).toEqual(['run the tests', 'then open a PR'])
})

test('blank and non-text lines are skipped', () => {
  expect(texts('{"text":"  "}\n{"other":1}\nnot json\n')).toEqual([])
})
