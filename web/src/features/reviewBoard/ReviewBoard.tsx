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
import { instructorApi } from '../../lib/api/instructor'
import type { ChosenMeeting } from '../../lib/api/types/common'
import type { ReviewBoard as Board, ReviewStudent } from '../../lib/api/types/review'
import type { Proposal } from '../../lib/api/types/common'
import type { ApiError } from '../../lib/api/client'
import { perDayDensity } from '../../lib/grid'
import { Badge, Button, Modal, useToast } from '../../components/ui'
import { precheckMove } from './precheck'
import styles from './reviewBoard.module.css'

/** A drop that needs explicit instructor confirmation before it is sent. */
interface PendingOverride {
  req: EditRequest
  needsOversize: boolean
  needsLowOverlap: boolean
  overlap: number
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
  onSetMeeting,
}: {
  board: Board
  groupId: number
  blockedReason: string | null
  editable: boolean
  onSetMeeting?: () => void
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `group-${groupId}`, disabled: !editable })
  const group = board.proposal.groups.find((g) => g.group_id === groupId)!
  const blocked = isOver && blockedReason != null
  const meeting: ChosenMeeting | undefined = board.meetings[String(groupId)]
  return (
    <div ref={setNodeRef} className={blocked ? styles.columnBlocked : styles.column}>
      <div className={styles.columnHeader}>
        <span>Group {group.group_id}</span>
        <span>
          {group.members.length}/{board.config.max_size}
        </span>
      </div>
      <div className={styles.columnMeta}>
        ⏱ {group.meeting_slots.join(', ') || 'no shared slots'}
        {meeting && (
          <div>
            📌 {meeting.label} <span title={`set by ${meeting.set_by}`}>({meeting.set_by})</span>
          </div>
        )}
        {onSetMeeting && (
          <button type="button" className={styles.metaAction} onClick={onSetMeeting}>
            {meeting ? 'update time' : 'set time'}
          </button>
        )}
      </div>
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
  live = false,
  onApprove,
}: {
  cycleId: number
  editable: boolean
  /** Cycle is published: every edit needs explicit confirmation and notifies students. */
  live?: boolean
  onApprove: () => void
}) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))
  const [active, setActive] = useState<string | null>(null)
  const [hoverBlocked, setHoverBlocked] = useState<Record<number, string | null>>({})
  const [pendingOverride, setPendingOverride] = useState<PendingOverride | null>(null)
  const [pendingLive, setPendingLive] = useState<PendingOverride | null>(null)
  const [meetingFor, setMeetingFor] = useState<number | null>(null)
  const [meetingDraft, setMeetingDraft] = useState('')

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

  // Live (published) reassignment: server-first, no optimistic update —
  // students are notified the moment the server accepts.
  const reassign = useMutation({
    mutationFn: (req: EditRequest) => reviewApi.reassign(cycleId, req),
    onError: (err) => {
      toast((err as unknown as ApiError).detail ?? 'reassignment rejected', true)
    },
    onSuccess: (resp) => {
      const prev = queryClient.getQueryData<Board>(['reviewBoard', cycleId])
      if (prev) queryClient.setQueryData(['reviewBoard', cycleId], { ...prev, proposal: resp.proposal })
      queryClient.invalidateQueries({ queryKey: ['reviewBoard', cycleId] })
      toast(`Reassigned — ${resp.notified} students notified`)
    },
  })

  const setMeeting = useMutation({
    mutationFn: ({ groupId, label }: { groupId: number; label: string }) =>
      instructorApi.setGroupMeeting(cycleId, groupId, label),
    onError: (err) => {
      toast((err as unknown as ApiError).detail ?? 'could not set the meeting time', true)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reviewBoard', cycleId] })
      setMeetingFor(null)
      toast('Meeting time saved — the group has been notified')
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
    const warning = check.needsLowOverlap
      ? `Fewer than ${board.config.min_overlap} shared slot(s) — you'll be asked to confirm.`
      : null
    setHoverBlocked({ [gid]: check.ok ? warning : check.reason })
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
    const pending: PendingOverride = {
      req,
      needsOversize: check.needsOversize,
      needsLowOverlap: check.needsLowOverlap,
      overlap: check.overlap,
    }
    if (live) {
      // Published cycle: always confirm before a live change reaches students.
      setPendingLive(pending)
      return
    }
    if (check.needsOversize || check.needsLowOverlap) {
      setPendingOverride(pending)
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
          {editable && !live && (
            <Button variant="secondary" onClick={onApprove}>
              Approve →
            </Button>
          )}
          {live && <Badge>Live — students are notified of changes</Badge>}
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
                onSetMeeting={
                  live
                    ? () => {
                        setMeetingDraft(board.meetings[String(g.group_id)]?.label ?? '')
                        setMeetingFor(g.group_id)
                      }
                    : undefined
                }
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

      <Modal
        open={meetingFor != null}
        title={`Set meeting time — Group ${meetingFor ?? ''}`}
        onClose={() => setMeetingFor(null)}
      >
        <p>
          The group's members will be notified of the new time. This does not change the
          matcher's proposal.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (meetingFor != null && meetingDraft.trim())
              setMeeting.mutate({ groupId: meetingFor, label: meetingDraft.trim() })
          }}
        >
          <div style={{ margin: '12px 0' }}>
            <input
              value={meetingDraft}
              onChange={(e) => setMeetingDraft(e.target.value)}
              maxLength={120}
              placeholder="e.g. Mon 08:30 or Fridays 7pm, library"
              style={{ width: '100%', border: 'var(--border)', padding: 12 }}
            />
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <Button type="submit" disabled={setMeeting.isPending || !meetingDraft.trim()}>
              Save &amp; notify group
            </Button>
            <Button type="button" variant="ghost" onClick={() => setMeetingFor(null)}>
              Cancel
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={pendingLive != null}
        title="Reassign in a published cycle?"
        onClose={() => setPendingLive(null)}
      >
        <p>
          This cycle is <strong>published</strong> — groups are live.{' '}
          <strong>{board.students[pendingLive?.req.student_id ?? '']?.name || pendingLive?.req.student_id}</strong>{' '}
          will be {pendingLive?.req.action === 'assign' ? 'assigned' : 'moved'} to Group{' '}
          {pendingLive?.req.to_group}, and every affected student will be notified.
        </p>
        {pendingLive?.needsOversize && (
          <p>
            ⚠ The target group will exceed the maximum size of {board.config.max_size} (explicit
            oversize override).
          </p>
        )}
        {pendingLive?.needsLowOverlap && (
          <p>
            ⚠ The group would share {pendingLive.overlap} mutually free slot(s) — below the
            minimum of {board.config.min_overlap}. The group may have no shared meeting time
            (explicit low-overlap override).
          </p>
        )}
        <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
          <Button
            onClick={() => {
              if (pendingLive)
                reassign.mutate({
                  ...pendingLive.req,
                  allow_oversize: pendingLive.needsOversize,
                  allow_low_overlap: pendingLive.needsLowOverlap,
                })
              setPendingLive(null)
            }}
            disabled={reassign.isPending}
          >
            Reassign &amp; notify
          </Button>
          <Button variant="ghost" onClick={() => setPendingLive(null)}>
            Cancel
          </Button>
        </div>
      </Modal>

      <Modal open={pendingOverride != null} title="⚠ Override constraint?">
        {pendingOverride?.needsOversize && (
          <p>
            This group will have{' '}
            <strong>
              {(board.proposal.groups.find((g) => g.group_id === pendingOverride.req.to_group)
                ?.members.length ?? 0) + 1}{' '}
              members
            </strong>{' '}
            (Max {board.config.max_size}).
          </p>
        )}
        {pendingOverride?.needsLowOverlap && (
          <p>
            <strong>
              {board.students[pendingOverride.req.student_id]?.name ||
                pendingOverride.req.student_id}
            </strong>
            &rsquo;s schedule shares {pendingOverride.overlap} mutually free slot(s) with this
            group — below the minimum of {board.config.min_overlap}. The group may have no
            shared meeting time.
          </p>
        )}
        <p>Have you confirmed this with the students?</p>
        <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
          <Button
            onClick={() => {
              if (pendingOverride)
                edit.mutate({
                  ...pendingOverride.req,
                  allow_oversize: pendingOverride.needsOversize,
                  allow_low_overlap: pendingOverride.needsLowOverlap,
                })
              setPendingOverride(null)
            }}
          >
            Do it anyway
          </Button>
          <Button variant="ghost" onClick={() => setPendingOverride(null)}>
            Cancel
          </Button>
        </div>
      </Modal>
    </>
  )
}
