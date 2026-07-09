import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { instructorApi } from '../../lib/api/instructor'
import type { ApiError } from '../../lib/api/client'
import { BackLink, Badge, Button, Card, LifecycleSteps, Modal, useToast } from '../../components/ui'
import { useClassCycle } from './useClassCycle'
import styles from './instructor.module.css'

const STEPS = ['Proposed', 'Approved', 'Published']

export function PublishPage() {
  const { classId, cycle } = useClassCycle()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const toast = useToast()
  const queryClient = useQueryClient()

  const { data: proposal } = useQuery({
    queryKey: ['proposal', cycle?.id],
    queryFn: () => instructorApi.proposal(cycle!.id),
    enabled: cycle != null && cycle.status !== 'collecting',
    retry: false,
  })

  const publish = useMutation({
    mutationFn: () => instructorApi.publish(cycle!.id),
    onSuccess: (resp) => {
      queryClient.invalidateQueries()
      setConfirmOpen(false)
      toast(`Published — ${resp.notified} students notified`)
    },
    onError: (err) => {
      setConfirmOpen(false)
      toast((err as unknown as ApiError).detail ?? 'could not publish', true)
    },
  })

  if (!cycle) return <p>No active cycle.</p>
  if (cycle.status === 'collecting')
    return <p>Nothing to publish yet — run the match and review it first.</p>

  const stepIndex = { proposed: 0, approved: 1, published: 2, archived: 2, collecting: 0 }[
    cycle.status
  ]
  const placed = proposal?.groups.reduce((n, g) => n + g.members.length, 0) ?? 0

  return (
    <>
      <BackLink to={`/i/classes/${classId}`}>Overview</BackLink>
      <div style={{ height: 8 }} />
      <Badge>Step 4: Final approval</Badge>
      <h2 className={styles.pageTitle} style={{ marginTop: 8 }}>
        Approve &amp; publish groups
      </h2>

      <LifecycleSteps steps={STEPS} activeIndex={stepIndex} />

      <div style={{ height: 24 }} />

      <div className={styles.configGrid}>
        <Card>
          <h3 style={{ marginBottom: 16 }}>Matching summary</h3>
          <div className={styles.statRow}>
            <div>
              <div className={styles.statValue}>{proposal?.groups.length ?? '–'}</div>
              <div className={styles.statLabel}>Groups created</div>
            </div>
            <div>
              <div className={styles.statValue}>{placed}</div>
              <div className={styles.statLabel}>Students placed</div>
            </div>
            <div>
              <div className={styles.statValue}>{proposal?.unplaced.length ?? 0}</div>
              <div className={styles.statLabel}>Unplaced</div>
            </div>
          </div>
          {(proposal?.unplaced.length ?? 0) > 0 && (
            <div className={styles.warningCard}>
              {proposal!.unplaced.length} students are unplaced — resolve them on the{' '}
              <Link to={`/i/classes/${classId}/review`}>review board</Link> or follow up with
              them directly before publishing.
            </div>
          )}
        </Card>

        <Card>
          <h3 style={{ marginBottom: 16 }}>Deployment checklist</h3>
          <p>
            {(proposal?.warnings.length ?? 0) === 0 ? '☑' : '☐'} All groups valid
            {(proposal?.warnings.length ?? 0) > 0 && ` — ${proposal!.warnings.length} warnings open`}
          </p>
          <p>{proposal?.groups.every((g) => g.meeting_slots.length > 0) ? '☑' : '☐'} Meeting times assigned</p>
          <p>{cycle.status !== 'proposed' ? '☑' : '☐'} Proposal approved after review</p>
        </Card>
      </div>

      <div style={{ height: 24 }} />

      <Card flat>
        <p>
          <strong>🛡 Privacy reminder:</strong> students will see only their own group — never
          demographic data.
        </p>
        {cycle.status === 'proposed' && (
          <p className={styles.pageIntro}>
            Approve the proposal from the <Link to={`/i/classes/${classId}/review`}>review board</Link>{' '}
            first — approval requires having seen the current proposal.
          </p>
        )}
        {cycle.status === 'approved' && (
          <>
            <Button onClick={() => setConfirmOpen(true)}>Publish &amp; notify students ▷</Button>
            <p className="mono-label" style={{ marginTop: 8 }}>
              Action cannot be undone once notifications are dispatched.
            </p>
          </>
        )}
        {cycle.status === 'published' && (
          <p>
            <Badge>Published</Badge> Students can now see their groups.
          </p>
        )}
      </Card>

      <Modal open={confirmOpen} title="Publish groups?" onClose={() => setConfirmOpen(false)}>
        <p>
          Every student will immediately see their group and meeting time. This cannot be
          undone.
        </p>
        <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
          <Button onClick={() => publish.mutate()} disabled={publish.isPending}>
            Publish now
          </Button>
          <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
            Cancel
          </Button>
        </div>
      </Modal>
    </>
  )
}
