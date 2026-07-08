import { describe, expect, test } from 'vitest'
import { mutualOverlap, numSlots, perDayDensity, slotIndex, slotLabel, slotsPerDay } from './grid'
import type { GridConfig } from './api/types/common'

const DEFAULT: GridConfig = {
  days: 7,
  start: '08:00',
  end: '20:00',
  slot_minutes: 30,
  num_slots: 168,
}

const SMALL: GridConfig = { days: 1, start: '08:00', end: '10:00', slot_minutes: 30, num_slots: 4 }

describe('grid math mirrors io_parse.Grid', () => {
  test('default grid is 7x24 = 168 slots', () => {
    expect(slotsPerDay(DEFAULT)).toBe(24)
    expect(numSlots(DEFAULT)).toBe(168)
  })

  test('day-major indexing', () => {
    expect(slotIndex(DEFAULT, 0, 0)).toBe(0)
    expect(slotIndex(DEFAULT, 1, 0)).toBe(24)
    expect(slotIndex(DEFAULT, 6, 23)).toBe(167)
  })

  test('slot labels match reflectool format (Sat-18:30 style)', () => {
    // Python: Grid().slot_label(0) == "Mon-08:00"
    expect(slotLabel(DEFAULT, 0)).toBe('Mon-08:00')
    // day 5 (Sat), offset 21 -> 08:00 + 21*30min = 18:30
    expect(slotLabel(DEFAULT, 5 * 24 + 21)).toBe('Sat-18:30')
    expect(slotLabel(DEFAULT, 167)).toBe('Sun-19:30')
    expect(slotLabel(SMALL, 3)).toBe('Mon-09:30')
  })

  test('mutualOverlap counts shared slots', () => {
    expect(
      mutualOverlap([
        [true, true, false, false],
        [true, false, true, false],
      ]),
    ).toBe(1)
    expect(mutualOverlap([])).toBe(0)
  })

  test('perDayDensity', () => {
    expect(perDayDensity(SMALL, [true, true, false, false])).toEqual([0.5])
  })
})
