import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { DndContext, closestCenter } from '@dnd-kit/core'
import type { DragEndEvent } from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { instructorApi } from '../../lib/api/instructor'
import type { ApiError } from '../../lib/api/client'
import { BackLink, Badge, Button, Card, NumberStepper, useToast } from '../../components/ui'
import { DAY_NAMES } from '../../lib/grid'
import { useClassCycle } from './useClassCycle'
import styles from './instructor.module.css'

function PriorityRow({ id, rank }: { id: string; rank: number }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id,
  })
  return (
    <div
      ref={setNodeRef}
      className={styles.priorityItem}
      data-dragging={isDragging}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      {...attributes}
      {...listeners}
    >
      <span className={styles.dragHandle}>⠿</span>
      <span style={{ textTransform: 'capitalize' }}>{id}</span>
      <span style={{ marginLeft: 'auto' }}>
        <Badge variant={rank === 0 ? 'solid' : 'outline'}>
          {rank === 0 ? 'High' : 'Medium'}
        </Badge>
      </span>
    </div>
  )
}

export function ConfigPage() {
  const { cycle, classId } = useClassCycle()
  const toast = useToast()
  const queryClient = useQueryClient()

  const [priority, setPriority] = useState<string[]>([])
  const [targetSize, setTargetSize] = useState(5)
  const [minSize, setMinSize] = useState(3)
  const [maxSize, setMaxSize] = useState(5)
  const [minOverlap, setMinOverlap] = useState(2)
  const [days, setDays] = useState(7)
  const [start, setStart] = useState('08:00')
  const [end, setEnd] = useState('20:00')

  useEffect(() => {
    if (!cycle) return
    setPriority(cycle.config.priority)
    setTargetSize(cycle.config.target_size)
    setMinSize(cycle.config.min_size)
    setMaxSize(cycle.config.max_size)
    setMinOverlap(cycle.config.min_overlap)
    setDays(cycle.config.grid.days)
    setStart(cycle.config.grid.start)
    setEnd(cycle.config.grid.end)
  }, [cycle])

  const save = useMutation({
    mutationFn: () =>
      instructorApi.patchConfig(cycle!.id, {
        priority,
        target_size: targetSize,
        min_size: minSize,
        max_size: maxSize,
        min_overlap: minOverlap,
        grid: {
          days,
          start,
          end,
          slot_minutes: cycle!.config.grid.slot_minutes,
        } as never,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cycles', classId] })
      toast('Configuration saved')
    },
    onError: (err) => toast((err as unknown as ApiError).detail ?? 'could not save', true),
  })

  if (!cycle) return <p>No active cycle — start one from the Overview page first.</p>

  const frozen = cycle.status !== 'collecting'

  function onDragEnd(e: DragEndEvent) {
    const { active, over } = e
    if (over && active.id !== over.id) {
      setPriority((p) => arrayMove(p, p.indexOf(String(active.id)), p.indexOf(String(over.id))))
    }
  }

  return (
    <>
      <BackLink to={`/i/classes/${classId}`}>Overview</BackLink>
      <h2 className={styles.pageTitle}>Instructor Configuration</h2>
      <p className={styles.pageIntro}>
        Define the core parameters for the matching algorithm. Priority order is a strict
        hierarchy — the matcher never trades a higher tier away for a lower one.
      </p>
      {frozen && (
        <div className={styles.warningCard}>
          Configuration is frozen once matching has run — start a new cycle to change it.
        </div>
      )}

      <div className={styles.configGrid}>
        <Card flat>
          <h3 style={{ marginBottom: 12 }}>Matching priority</h3>
          <DndContext collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext items={priority} strategy={verticalListSortingStrategy}>
              {priority.map((p, i) => (
                <PriorityRow key={p} id={p} rank={i} />
              ))}
            </SortableContext>
          </DndContext>
          <p className="mono-label">Drag to reorder · equity safeguards always apply on top</p>
        </Card>

        <Card flat>
          <h3 style={{ marginBottom: 12 }}>Size constraints</h3>
          <div className={styles.sizeRow}>
            <span>Target size</span>
            <NumberStepper value={targetSize} min={minSize} max={maxSize} onChange={setTargetSize} />
          </div>
          <div className={styles.sizeRow}>
            <span>Min size</span>
            <NumberStepper value={minSize} min={2} max={targetSize} onChange={setMinSize} />
          </div>
          <div className={styles.sizeRow}>
            <span>Max size</span>
            <NumberStepper value={maxSize} min={targetSize} max={10} onChange={setMaxSize} />
          </div>
          <div className={styles.sizeRow}>
            <span>
              Min overlap
              <div className="mono-label">shared slots/week</div>
            </span>
            <NumberStepper value={minOverlap} min={1} max={20} onChange={setMinOverlap} />
          </div>
        </Card>
      </div>

      <div style={{ height: 24 }} />

      <Card flat>
        <h3 style={{ marginBottom: 12 }}>Active schedule window</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
          {DAY_NAMES.map((d, i) => (
            <button
              key={d}
              type="button"
              className={i < days ? styles.dayToggleOn : styles.dayToggle}
              onClick={() => setDays(i + 1)}
              title={`Grid covers ${d} when ${i + 1} days are active`}
            >
              {i < days ? '■' : '□'} {d}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'end' }}>
          <div>
            <div className="mono-label">Start time</div>
            <input value={start} onChange={(e) => setStart(e.target.value)} style={{ border: 'var(--border)', padding: 8 }} />
          </div>
          <span>to</span>
          <div>
            <div className="mono-label">End time</div>
            <input value={end} onChange={(e) => setEnd(e.target.value)} style={{ border: 'var(--border)', padding: 8 }} />
          </div>
        </div>
        <p className="mono-label" style={{ marginTop: 12 }}>
          The grid locks once the first student submits availability.
        </p>
      </Card>

      <div className={styles.actions}>
        <Button onClick={() => save.mutate()} disabled={frozen || save.isPending}>
          Save configuration
        </Button>
      </div>
    </>
  )
}
