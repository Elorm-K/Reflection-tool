import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { instructorApi } from '../../lib/api/instructor'
import type { ApiError } from '../../lib/api/client'
import { BackLink, Button, useToast } from '../../components/ui'
import { ReviewBoard } from '../../features/reviewBoard/ReviewBoard'
import { useClassCycle } from './useClassCycle'
import styles from './instructor.module.css'

export function ReviewPage() {
  const { classId, cycle } = useClassCycle()
  const toast = useToast()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const approve = useMutation({
    mutationFn: () => instructorApi.approve(cycle!.id),
    onSuccess: () => {
      queryClient.invalidateQueries()
      toast('Proposal approved — publish when ready')
      navigate(`/i/classes/${classId}/publish`)
    },
    onError: (err) => toast((err as unknown as ApiError).detail ?? 'could not approve', true),
  })

  const rematch = useMutation({
    mutationFn: () => instructorApi.match(cycle!.id),
    onSuccess: () => {
      queryClient.invalidateQueries()
      toast('Proposal reset to a fresh deterministic match')
    },
    onError: (err) => toast((err as unknown as ApiError).detail ?? 'could not reset', true),
  })

  if (!cycle) return <p>No active cycle — start one from the Overview page.</p>
  if (cycle.status === 'collecting')
    return (
      <p>
        No proposal yet — run the match from the Overview page once students have submitted
        availability.
      </p>
    )

  const editable = cycle.status === 'proposed'

  return (
    <>
      <BackLink to={`/i/classes/${classId}`}>Overview</BackLink>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <div>
          <h2 className={styles.pageTitle}>Review proposal</h2>
          <p className={styles.pageIntro}>
            {editable
              ? 'Drag students between groups; every move is re-validated instantly. Demographic labels are visible only to you, only here.'
              : `This proposal is ${cycle.status} — the board is read-only.`}
          </p>
        </div>
        {editable && (
          <Button
            variant="ghost"
            onClick={() => {
              if (window.confirm('Reset all manual edits and re-run the matcher?'))
                rematch.mutate()
            }}
          >
            Reset
          </Button>
        )}
      </div>
      <ReviewBoard cycleId={cycle.id} editable={editable} onApprove={() => approve.mutate()} />
    </>
  )
}
