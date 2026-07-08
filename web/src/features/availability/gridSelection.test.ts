import { describe, expect, test } from 'vitest'
import { emptyState, paintReducer, toVector } from './gridSelection'

describe('paint reducer', () => {
  test('stroke starting on empty cell paints additively across cells', () => {
    let s = emptyState()
    s = paintReducer(s, { type: 'start', cell: 3 })
    s = paintReducer(s, { type: 'enter', cell: 4 })
    s = paintReducer(s, { type: 'enter', cell: 5 })
    s = paintReducer(s, { type: 'end' })
    expect([...s.selected].sort()).toEqual([3, 4, 5])
  })

  test('stroke starting on filled cell erases along its path', () => {
    let s = emptyState([1, 2, 3])
    s = paintReducer(s, { type: 'start', cell: 2 })
    s = paintReducer(s, { type: 'enter', cell: 3 })
    s = paintReducer(s, { type: 'end' })
    expect([...s.selected]).toEqual([1])
  })

  test('erase stroke does not re-add empty cells it crosses', () => {
    let s = emptyState([2])
    s = paintReducer(s, { type: 'start', cell: 2 }) // erase mode
    s = paintReducer(s, { type: 'enter', cell: 5 }) // empty already
    s = paintReducer(s, { type: 'end' })
    expect(s.selected.size).toBe(0)
  })

  test('re-entering a cell in the same stroke is a no-op', () => {
    let s = emptyState()
    s = paintReducer(s, { type: 'start', cell: 1 })
    s = paintReducer(s, { type: 'enter', cell: 2 })
    const after = paintReducer(s, { type: 'enter', cell: 1 })
    expect(after).toBe(s)
  })

  test('keyboard toggle flips a single cell', () => {
    let s = emptyState()
    s = paintReducer(s, { type: 'toggle', cell: 7 })
    expect(s.selected.has(7)).toBe(true)
    s = paintReducer(s, { type: 'toggle', cell: 7 })
    expect(s.selected.has(7)).toBe(false)
  })

  test('toVector builds the exact boolean vector the API expects', () => {
    expect(toVector(new Set([0, 2]), 4)).toEqual([true, false, true, false])
  })
})
