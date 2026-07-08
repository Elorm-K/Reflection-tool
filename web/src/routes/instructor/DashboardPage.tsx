import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { instructorApi } from '../../lib/api/instructor'
import type { ApiError } from '../../lib/api/client'
import { Badge, Button, Card, Field, Modal, Table, useToast } from '../../components/ui'
import { useClassCycle } from './useClassCycle'
import styles from './instructor.module.css'

export function DashboardPage() {
  const { classId, cls, cycles, cycle } = useClassCycle()
  const [cycleOpen, setCycleOpen] = useState(false)
  const [label, setLabel] = useState('')
  const [deadline, setDeadline] = useState('')
  const toast = useToast()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const { data: roster } = useQuery({
    queryKey: ['roster', classId],
    queryFn: () => instructorApi.roster(classId),
    enabled: Number.isFinite(classId),
  })
  const { data: status } = useQuery({
    queryKey: ['rosterStatus', cycle?.id],
    queryFn: () => instructorApi.rosterStatus(cycle!.id),
    enabled: cycle != null,
    refetchInterval: cycle?.status === 'collecting' ? 10000 : false,
  })
  const { data: proposal } = useQuery({
    queryKey: ['proposal', cycle?.id],
    queryFn: () => instructorApi.proposal(cycle!.id),
    enabled: cycle != null && cycle.status !== 'collecting',
    retry: false,
  })

  const createCycle = useMutation({
    mutationFn: () => instructorApi.createCycle(classId, label, {}, deadline || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cycles', classId] })
      setCycleOpen(false)
      toast('Cycle created — students can now submit availability')
    },
    onError: (err) => toast((err as unknown as ApiError).detail ?? 'failed', true),
  })

  const runMatch = useMutation({
    mutationFn: () => instructorApi.match(cycle!.id),
    onSuccess: (p) => {
      queryClient.invalidateQueries()
      toast(
        `Match complete: ${p.groups.length} groups, ${p.unplaced.length} unplaced` +
          (p.warnings.length ? `, ${p.warnings.length} warnings` : ''),
      )
      navigate(`/i/classes/${classId}/review`)
    },
    onError: (err) => toast((err as unknown as ApiError).detail ?? 'match failed', true),
  })

  if (!cls) return <p>Loading…</p>

  if (runMatch.isPending) {
    return (
      <div className={styles.processing}>
        <span className={styles.processingDot}>■</span>
        <h2>Matching in progress</h2>
        <p className={styles.pageIntro}>
          Running the deterministic matcher over {status?.submitted_count ?? '…'} submissions.
        </p>
      </div>
    )
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <div>
          <h2 className={styles.pageTitle}>{cls.name}</h2>
          <p className={styles.pageIntro}>
            Class code <strong>{cls.class_code}</strong>
            {cycle?.deadline ? ` · deadline ${cycle.deadline}` : ''}
          </p>
        </div>
        {cycle && <Badge>{cycle.status}</Badge>}
      </div>

      {!cycle && (
        <Card>
          <p>No matching cycle yet. Start one to begin collecting availability.</p>
          <Button onClick={() => setCycleOpen(true)}>Start a cycle</Button>
        </Card>
      )}

      {cycle && (
        <>
          <div className={styles.statRow}>
            <div className={styles.stat}>
              <div className={styles.statLabel}>Enrolled</div>
              <div className={styles.statValue}>
                {status?.joined_count ?? '–'}/{status?.roster_count ?? roster?.students.length ?? '–'}
              </div>
            </div>
            <div className={styles.stat}>
              <div className={styles.statLabel}>Submitted availability</div>
              <div className={styles.statValue}>{status?.submitted_count ?? '–'}</div>
            </div>
            <div className={styles.stat}>
              <div className={styles.statLabel}>Groups</div>
              <div className={styles.statValue}>{proposal?.groups.length ?? '–'}</div>
            </div>
            <div className={styles.stat}>
              <div className={styles.statLabel}>Unassigned</div>
              <div className={styles.statValue}>{proposal?.unplaced.length ?? '–'}</div>
            </div>
          </div>

          {status != null && status.missing.length > 0 && cycle.status === 'collecting' && (
            <div className={styles.warningCard}>
              <strong>{status.missing.length} students haven't submitted:</strong>{' '}
              {status.missing.join(', ')} — they'll be left out of matching until they do.
            </div>
          )}
          {(proposal?.warnings ?? []).map((w) => (
            <div key={w} className={styles.warningCard}>
              ⚠ {w}
            </div>
          ))}

          {cycle.status === 'collecting' && (
            <div className={styles.actions}>
              <Button
                onClick={() => runMatch.mutate()}
                disabled={(status?.submitted_count ?? 0) === 0}
              >
                ✦ Run match
              </Button>
              <Link to={`/i/classes/${classId}/config`}>
                <Button variant="secondary">Edit settings</Button>
              </Link>
            </div>
          )}

          {proposal && (
            <>
              <h3 style={{ margin: '24px 0 12px' }}>Groups ({proposal.groups.length})</h3>
              <Table>
                <thead>
                  <tr>
                    <th>Group</th>
                    <th>Meeting time</th>
                    <th>Members</th>
                  </tr>
                </thead>
                <tbody>
                  {proposal.groups.map((g) => (
                    <tr key={g.group_id}>
                      <td>Group {g.group_id}</td>
                      <td>{g.meeting_slots.join(', ')}</td>
                      <td>{g.members.length} students</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <div className={styles.actions}>
                <a href={instructorApi.exportCsvUrl(cycle.id)} download>
                  <Button variant="secondary">Export results (CSV) ↓</Button>
                </a>
              </div>
            </>
          )}
        </>
      )}

      {cycles != null && cycles.length > 1 && (
        <>
          <h3 style={{ margin: '32px 0 12px' }}>Historical cycles</h3>
          {cycles
            .filter((c) => c.id !== cycle?.id)
            .map((c) => (
              <Card key={c.id} flat>
                {c.label || `Cycle ${c.id}`} — {c.status} · started {c.created_at}
              </Card>
            ))}
        </>
      )}

      <Modal open={cycleOpen}>
        <h3 style={{ marginBottom: 16 }}>Start a matching cycle</h3>
        <Field label="Label">
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Week 1" />
        </Field>
        <Field label="Deadline (shown to students)">
          <input
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
            placeholder="2026-10-24"
          />
        </Field>
        <div style={{ display: 'flex', gap: 12 }}>
          <Button onClick={() => createCycle.mutate()} disabled={createCycle.isPending}>
            Start cycle
          </Button>
          <Button variant="ghost" onClick={() => setCycleOpen(false)}>
            Cancel
          </Button>
        </div>
      </Modal>
    </>
  )
}
