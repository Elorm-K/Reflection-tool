import { useReducer, useRef } from 'react'
import type { GridConfig } from '../../lib/api/types/common'
import { DAY_NAMES, rowLabel, slotIndex, slotsPerDay } from '../../lib/grid'
import { emptyState, paintReducer, toVector } from './gridSelection'
import type { PaintState } from './gridSelection'
import styles from './availability.module.css'

interface Props {
  grid: GridConfig
  initial?: number[]
  onChange: (vector: boolean[], count: number) => void
}

function cellFromPoint(x: number, y: number): number | null {
  const el = document.elementFromPoint(x, y)?.closest('[data-index]')
  if (!el) return null
  return Number((el as HTMLElement).dataset.index)
}

export function AvailabilityGrid({ grid, initial, onChange }: Props) {
  const [state, dispatch] = useReducer(
    (s: PaintState, a: Parameters<typeof paintReducer>[1]) => {
      const next = paintReducer(s, a)
      if (next !== s) onChange(toVector(next.selected, grid.num_slots), next.selected.size)
      return next
    },
    initial,
    (init) => emptyState(init),
  )
  const painting = useRef(false)
  const perDay = slotsPerDay(grid)

  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    const cell = cellFromPoint(e.clientX, e.clientY)
    if (cell === null) return
    painting.current = true
    e.currentTarget.setPointerCapture(e.pointerId)
    dispatch({ type: 'start', cell })
  }

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!painting.current) return
    const cell = cellFromPoint(e.clientX, e.clientY)
    if (cell !== null) dispatch({ type: 'enter', cell })
  }

  function endStroke() {
    if (!painting.current) return
    painting.current = false
    dispatch({ type: 'end' })
  }

  return (
    <div className={styles.gridWrap}>
      <div
        className={styles.grid}
        style={{
          gridTemplateColumns: `44px repeat(${grid.days}, 1fr)`,
          gridTemplateRows: `32px repeat(${perDay}, 28px)`,
        }}
        role="grid"
        aria-label="Weekly availability"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endStroke}
        onPointerCancel={endStroke}
      >
        <div className={styles.dayHeader} />
        {Array.from({ length: grid.days }, (_, d) => (
          <div key={`h${d}`} className={d >= 5 ? styles.dayHeaderWeekend : styles.dayHeader}>
            {DAY_NAMES[d][0]}
          </div>
        ))}
        {Array.from({ length: perDay }, (_, row) => (
          <>
            <div key={`t${row}`} className={styles.timeLabel}>
              {rowLabel(grid, row)}
            </div>
            {Array.from({ length: grid.days }, (_, day) => {
              const idx = slotIndex(grid, day, row)
              const on = state.selected.has(idx)
              return (
                <button
                  key={idx}
                  type="button"
                  role="gridcell"
                  data-index={idx}
                  aria-pressed={on}
                  aria-label={`${DAY_NAMES[day]} ${rowLabel(grid, row)}`}
                  className={on ? styles.cellOn : styles.cell}
                  onKeyDown={(e) => {
                    if (e.key === ' ' || e.key === 'Enter') {
                      e.preventDefault()
                      dispatch({ type: 'toggle', cell: idx })
                    }
                  }}
                />
              )
            })}
          </>
        ))}
      </div>
    </div>
  )
}
