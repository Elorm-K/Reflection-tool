/* Pure paint-selection logic for the availability grid (unit-tested). */

export type PaintMode = 'add' | 'remove'

export interface PaintState {
  selected: Set<number>
  /** Active stroke, or null when not painting. */
  stroke: { mode: PaintMode; painted: Set<number> } | null
}

export function emptyState(initial?: Iterable<number>): PaintState {
  return { selected: new Set(initial ?? []), stroke: null }
}

export type PaintAction =
  | { type: 'start'; cell: number }
  | { type: 'enter'; cell: number }
  | { type: 'end' }
  | { type: 'toggle'; cell: number }
  | { type: 'clear' }

export function paintReducer(state: PaintState, action: PaintAction): PaintState {
  switch (action.type) {
    case 'start': {
      // Stroke starting on an empty cell paints; on a filled cell, erases.
      const mode: PaintMode = state.selected.has(action.cell) ? 'remove' : 'add'
      const selected = new Set(state.selected)
      if (mode === 'add') selected.add(action.cell)
      else selected.delete(action.cell)
      return { selected, stroke: { mode, painted: new Set([action.cell]) } }
    }
    case 'enter': {
      if (!state.stroke || state.stroke.painted.has(action.cell)) return state
      const selected = new Set(state.selected)
      if (state.stroke.mode === 'add') selected.add(action.cell)
      else selected.delete(action.cell)
      const painted = new Set(state.stroke.painted)
      painted.add(action.cell)
      return { selected, stroke: { ...state.stroke, painted } }
    }
    case 'end':
      return state.stroke ? { ...state, stroke: null } : state
    case 'toggle': {
      const selected = new Set(state.selected)
      if (selected.has(action.cell)) selected.delete(action.cell)
      else selected.add(action.cell)
      return { selected, stroke: null }
    }
    case 'clear':
      return emptyState()
  }
}

export function toVector(selected: Set<number>, numSlots: number): boolean[] {
  return Array.from({ length: numSlots }, (_, i) => selected.has(i))
}
