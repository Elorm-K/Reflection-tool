import { describe, expect, it } from 'vitest'
import { precheckMove } from './precheck'
import type { ReviewBoard as Board, ReviewStudent } from '../../lib/api/types/review'

/* Minimal board: group 1 on the early block, group 2 on the late block. */
function makeBoard(overrides: { members1?: string[]; members2?: string[] } = {}): Board {
  const students: Record<string, ReviewStudent> = {}
  const early = [true, true, false, false]
  const late = [false, false, true, true]
  const members1 = overrides.members1 ?? ['a1', 'a2', 'a3', 'a4']
  const members2 = overrides.members2 ?? ['b1', 'b2', 'b3', 'b4']
  const student = (name: string, availability: boolean[]): ReviewStudent => ({
    name,
    availability,
    free_slot_count: 2,
    gender: 'undisclosed',
    disability: 'undisclosed',
  })
  for (const sid of members1) students[sid] = student(sid, early)
  for (const sid of members2) students[sid] = student(sid, late)
  return {
    meetings: {},
    config: {
      target_size: 4,
      min_size: 3,
      max_size: 5,
      min_overlap: 1,
      priority: [],
      tiebreak_seed: 0,
      grid: { days: 1, start: '08:00', end: '10:00', slot_minutes: 30, num_slots: 4 },
    },
    students,
    proposal: {
      status: 'proposed',
      groups: [
        { group_id: 1, members: members1, meeting_slots: [] },
        { group_id: 2, members: members2, meeting_slots: [] },
      ],
      unplaced: [],
      warnings: [],
    },
  }
}

describe('precheckMove', () => {
  it('flags a zero-overlap move as needsLowOverlap instead of blocking', () => {
    const check = precheckMove(makeBoard(), 'a1', 2)
    expect(check.ok).toBe(true)
    expect(check.needsLowOverlap).toBe(true)
    expect(check.overlap).toBe(0)
    expect(check.needsOversize).toBe(false)
  })

  it('does not flag a move that keeps min_overlap', () => {
    // b9 is a late-block unplaced student joining the late-block group:
    // full overlap, no flags.
    const board = makeBoard({ members2: ['b1', 'b2', 'b3'] })
    board.students['b9'] = {
      name: 'b9',
      availability: [false, false, true, true],
      free_slot_count: 2,
      gender: 'undisclosed',
      disability: 'undisclosed',
    }
    board.proposal.unplaced.push({ student_id: 'b9', reason: 'test' })
    const check = precheckMove(board, 'b9', 2)
    expect(check.ok).toBe(true)
    expect(check.needsLowOverlap).toBe(false)
    expect(check.overlap).toBe(2)
  })

  it("still blocks a drop onto the student's own group", () => {
    const check = precheckMove(makeBoard(), 'a1', 1)
    expect(check.ok).toBe(false)
    expect(check.reason).toBe('already in this group')
  })

  it('keeps hard blocks: source below min_size', () => {
    const check = precheckMove(makeBoard({ members1: ['a1', 'a2', 'a3'] }), 'a1', 2)
    expect(check.ok).toBe(false)
    expect(check.reason).toContain('below 3')
  })

  it('keeps hard blocks: beyond max_size + 1', () => {
    const check = precheckMove(
      makeBoard({ members2: ['b1', 'b2', 'b3', 'b4', 'b5', 'b6'] }),
      'a1',
      2,
    )
    expect(check.ok).toBe(false)
    expect(check.reason).toContain('Max is 5')
  })

  it('flags oversize and low overlap together', () => {
    const check = precheckMove(makeBoard({ members2: ['b1', 'b2', 'b3', 'b4', 'b5'] }), 'a1', 2)
    expect(check.ok).toBe(true)
    expect(check.needsOversize).toBe(true)
    expect(check.needsLowOverlap).toBe(true)
  })
})
