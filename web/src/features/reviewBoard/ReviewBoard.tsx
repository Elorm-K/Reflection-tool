import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragEndEvent, DragOverEvent, DragStartEvent } from '@dnd-kit/core'
import { reviewApi } from '../../lib/api/review'
import type { EditRequest } from '../../lib/api/review'
import type { ReviewBoard as Board, ReviewStudent } from '../../lib/api/types/review'
import type { Proposal } from '../../lib/api/types/common'
import type { ApiError } from '../../lib/api/client'
import { mutualOverlap, perDayDensity } from '../../lib/grid'
import { Badge, Button, Modal, useToast } from '../../components/ui'
import styles from './reviewBoard.module.css'

/* ---------- pure helpers (advisory prechecks; server verdict is authoritative) */

interface Precheck {
  ok: boolean
  needsOversize: boolean
  reason: string | null
}

export function precheckMove(
  board: Board,
  studentId: string,
  toGroup: number,
): Precheck {
  const { config, students } = board
  const target = board.proposal.groups.find((g) => g.group_id === toGroup)
  if (!target) return { ok: false, needsOversize: false, reason: 'no such group' }
  if (target.members.includes(studentId))
    return { ok: false, needsOversize: false, reason: 'already in this group' }

  const source = board.proposal.groups.find((g) => g.members.includes(studentId))
  if (source && source.members.length - 1 < config.min_size) {
    return {
      ok: false,
      needsOversize: false,
      reason: `Group ${source.group_id} would drop below ${config.min_size} members.`,
    }
  }
  const newMembers = [...target.members, studentId]
  const overlap = mutualOverlap(newMembers.map((sid) => students[sid].availability))
  if (overlap < config.min_overlap) {
    const name = students[studentId]?.name || studentId
    return {
      ok: false,
      needsOversize: false,
      reason: `${name}'s schedule does not overlap with this group's meeting time.`,
    }
  }
  if (newMembers.length > config.max_size + 1)
    return { ok: false, needsOversize: false, reason: `Max is ${config.max_size} (+1 with override).` }
  return { ok: true, needsOversize: newMembers.length > config.max_size, reason: null }
}

/* ---------- presentational bits ------------------------------------------- */

function DemographicChips({ s }: { s: ReviewStudent }) {
  // The ONLY render surface for per-student demographics (CLAUDE.md inv. 1).
  return (
    <span className={styles.demoChips}>
      {s.gender} | {s.disability}
    </span>
  )
}

function Sparkline({ board, s }: { board: Board; s: ReviewStudent }) {
  const density = perDayDensity(board.config.grid, s.availability)
  return (
    <span className={styles.spark} aria-label={`${s.free_slot_count} free slots`}>
      {density.map((d, i) =>
        d > 0 ? (
          <span key={i} className={styles.sparkBar} style={{ height: `${Math.max(15, d * 100)}%` }} />
        ) : (
          <span key={i} className={styles.sparkBarEmpty} />
        ),
      )}
    </span>
  )
}

function StudentCard({
  board,
  sid,
  lowOverlap,
}: {
  board: Board
  sid: string
  lowOverlap?: boolean
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: sid })
  const s = board.students[sid]
  if (!s) return null
  return (
    <div
      ref={setNodeRef}
      className={isDragging ? styles.cardDragging : styles.card}
      {...attributes}
      {...listeners}
    >
      <div className={styles.cardTop}>
        <span className={styles.cardName}>
          {s.name || sid} <span className={styles.cardId}>{sid}</span>
        </span>
        {lowOverlap && <Badge variant="alert">Low overlap</Badge>}
      </div>
      <Sparkline board={board} s={s} />
      <DemographicChips s={s} />
    </div>
  )
}

function GroupColumn({
  board,
  groupId,
  blockedReason,
  editable,
}: {
  board: Board
  groupId: number
  blockedReason: string | null
  editable: boolean
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `group-${groupId}`, disabled: !editable })
  const group = board.proposal.groups.find((g) => g.group_id === groupId)!
  const blocked = isOver && blockedReason != null
  return (
    <div ref={setNodeRef} className={blocked ? styles.columnBlocked : styles.column}>
      <div className={styles.columnHeader}>
        <span>Group {group.group_id}</span>
        <span>
          {group.members.length}/{board.config.max_size}
        </span>
      </div>
      <div className={styles.columnMeta}>⏱ {group.meeting_slots.join(', ') || 'no shared slots'}</div>
      <div className={styles.columnBody}>
        {blocked && <div className={styles.conflictCard}>⚠ {blockedReason}</div>}
        {group.members.map((sid) => (
          <StudentCard key={sid} board={board} sid={sid} />
        ))}
        {editable && <div className={styles.dropHint}>Drop student here</div>}
      </div>
    </div>
  )
}

/* ---------- the board ------------------------------------------------------- */

export function ReviewBoard({
  cycleId,
  editable,
  onApprove,
}: {
  cycleId: number
  editable: boolean
  onApprove: () => void
}) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))
  const [active, setActive] = useState<string | null>(null)
  const [hoverBlocked, setHoverBlocked] = useState<Record<number, string | null>>({})
  const [pendingOversize, setPendingOversize] = useState<EditRequest | null>(null)

  const { data: board } = useQuery({
    queryKey: ['reviewBoard', cycleId],
    queryFn: () => reviewApi.board(cycleId),
  })

  const edit = useMutation({
    mutationFn: (req: EditRequest) => reviewApi.edit(cycleId, req),
    onMutate: async (req) => {
      await queryClient.cancelQueries({ queryKey: ['reviewBoard', cycleId] })
      const prev = queryClient.getQueryData<Board>(['reviewBoard', cycleId])
      if (prev) {
        // optimistic: apply the move locally; server response replaces this
        const proposal: Proposal = JSON.parse(JSON.stringify(prev.proposal))
        for (const g of proposal.groups) g.members = g.members.filter((m) => m !== req.student_id)
        proposal.unplaced = proposal.unplaced.filter((u) => u.student_id !== req.student_id)
        proposal.groups.find((g) => g.group_id === req.to_group)?.members.push(req.student_id)
        queryClient.setQueryData(['reviewBoard', cycleId], { ...prev, proposal })
      }
      return { prev }
    },
    onError: (err, _req, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(['reviewBoard', cycleId], ctx.prev)
      toast((err as unknown as ApiError).detail ?? 'edit rejected', true)
    },
    onSuccess: (proposal) => {
      const prev = queryClient.getQueryData<Board>(['reviewBoard', cycleId])
      if (prev) queryClient.setQueryData(['reviewBoard', cycleId], { ...prev, proposal })
      queryClient.invalidateQueries({ queryKey: ['cycles'] })
      // the edit bumped proposal_rev: re-stamp the review by refetching the board
      queryClient.invalidateQueries({ queryKey: ['reviewBoard', cycleId] })
    },
  })

  const lowOverlapIds = useMemo(() => {
    if (!board) return new Set<string>()
    return new Set(
      Object.entries(board.students)
        .filter(([, s]) => s.free_slot_count < board.config.min_overlap * 2)
        .map(([sid]) => sid),
    )
  }, [board])

  if (!board) return <p>Loading review board…</p>

  const unplaced = board.proposal.unplaced

  function onDragStart(e: DragStartEvent) {
    setActive(String(e.active.id))
  }

  function onDragOver(e: DragOverEvent) {
    if (!e.over || !board) return
    const gid = Number(String(e.over.id).replace('group-', ''))
    const check = precheckMove(board, String(e.active.id), gid)
    setHoverBlocked({ [gid]: check.ok ? null : check.reason })
  }

  function onDragEnd(e: DragEndEvent) {
    setActive(null)
    setHoverBlocked({})
    if (!e.over || !board) return
    const sid = String(e.active.id)
    const gid = Number(String(e.over.id).replace('group-', ''))
    const isUnplaced = unplaced.some((u) => u.student_id === sid)
    const req: EditRequest = {
      action: isUnplaced ? 'assign' : 'move',
      student_id: sid,
      to_group: gid,
    }
    const check = precheckMove(board, sid, gid)
    if (!check.ok) {
      if (check.reason !== 'already in this group')
        toast(`Blocked: ${check.reason} The move was not applied.`, true)
      return
    }
    if (check.needsOversize) {
      setPendingOversize(req)
      return
    }
    edit.mutate(req)
  }

  return (
    <>
      <div className={styles.headerBar}>
        <div>
          <Badge variant="outline">
            {unplaced.length} unassigned · {board.proposal.groups.length} groups
          </Badge>{' '}
          {board.proposal.warnings.length > 0 && (
            <Badge variant="alert">{board.proposal.warnings.length} warnings</Badge>
          )}
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          {editable && (
            <Button variant="secondary" onClick={onApprove}>
              Approve →
            </Button>
          )}
        </div>
      </div>

      {board.proposal.warnings.map((w) => (
        <div key={w} className={styles.conflictCard} style={{ marginBottom: 12 }}>
          ⚠ {w}
        </div>
      ))}

      <DndContext
        sensors={sensors}
        onDragStart={onDragStart}
        onDragOver={onDragOver}
        onDragEnd={onDragEnd}
      >
        <div className={styles.board}>
          <aside className={styles.rail}>
            <div className={styles.railTitle}>
              Unassigned <Badge>{unplaced.length}</Badge>
            </div>
            {unplaced.length === 0 && (
              <p style={{ color: 'var(--muted)', fontSize: 13 }}>Everyone is placed.</p>
            )}
            {unplaced.map((u) => (
              <div key={u.student_id} style={{ marginBottom: 8 }}>
                <StudentCard
                  board={board}
                  sid={u.student_id}
                  lowOverlap={lowOverlapIds.has(u.student_id)}
                />
                <div className="mono-label" style={{ marginTop: 2 }}>
                  {u.reason}
                </div>
              </div>
            ))}
          </aside>

          <div className={styles.columns}>
            {board.proposal.groups.map((g) => (
              <GroupColumn
                key={g.group_id}
                board={board}
                groupId={g.group_id}
                blockedReason={hoverBlocked[g.group_id] ?? null}
                editable={editable}
              />
            ))}
          </div>
        </div>

        <DragOverlay>
          {active && (
            <div className={styles.card} style={{ boxShadow: 'var(--shadow)' }}>
              <span className={styles.cardName}>
                {board.students[active]?.name || active}
              </span>
            </div>
          )}
        </DragOverlay>
      </DndContext>

      <Modal open={pendingOversize != null} title="⚠ Override constraint?">
        <p>
          This group will have{' '}
          <strong>
            {(board.proposal.groups.find((g) => g.group_id === pendingOversize?.to_group)?.members
              .length ?? 0) + 1}{' '}
            members
          </strong>{' '}
          (Max {board.config.max_size}). Have you confirmed this with the students?
        </p>
        <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
          <Button
            onClick={() => {
              if (pendingOversize) edit.mutate({ ...pendingOversize, allow_oversize: true })
              setPendingOversize(null)
            }}
          >
            Do it anyway
          </Button>
          <Button variant="ghost" onClick={() => setPendingOversize(null)}>
            Cancel
          </Button>
        </div>
      </Modal>
    </>
  )
}
