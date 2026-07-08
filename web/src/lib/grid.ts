/* Slot index <-> day/time math, mirroring reflectool's io_parse.Grid:
 * day-major indexing, index = day * slotsPerDay + offset. */

import type { GridConfig } from './api/types/common'

export const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const

function minutes(hhmm: string): number {
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + m
}

export function slotsPerDay(grid: GridConfig): number {
  return Math.floor((minutes(grid.end) - minutes(grid.start)) / grid.slot_minutes)
}

export function numSlots(grid: GridConfig): number {
  return grid.days * slotsPerDay(grid)
}

export function slotIndex(grid: GridConfig, day: number, row: number): number {
  return day * slotsPerDay(grid) + row
}

export function slotLabel(grid: GridConfig, index: number): string {
  const perDay = slotsPerDay(grid)
  const day = Math.floor(index / perDay)
  const offset = index % perDay
  const total = minutes(grid.start) + offset * grid.slot_minutes
  const h = String(Math.floor(total / 60)).padStart(2, '0')
  const m = String(total % 60).padStart(2, '0')
  return `${DAY_NAMES[day]}-${h}:${m}`
}

export function rowLabel(grid: GridConfig, row: number): string {
  const total = minutes(grid.start) + row * grid.slot_minutes
  const h = String(Math.floor(total / 60)).padStart(2, '0')
  const m = String(total % 60).padStart(2, '0')
  return `${h}:${m}`
}

/** Count of slots where every member is available (mutual overlap). */
export function mutualOverlap(availabilities: boolean[][]): number {
  if (availabilities.length === 0) return 0
  const n = availabilities[0].length
  let count = 0
  for (let i = 0; i < n; i++) {
    if (availabilities.every((a) => a[i])) count++
  }
  return count
}

/** Per-day free-slot density, for the availability sparkline. */
export function perDayDensity(grid: GridConfig, availability: boolean[]): number[] {
  const perDay = slotsPerDay(grid)
  return Array.from({ length: grid.days }, (_, day) => {
    let free = 0
    for (let row = 0; row < perDay; row++) {
      if (availability[day * perDay + row]) free++
    }
    return perDay === 0 ? 0 : free / perDay
  })
}
