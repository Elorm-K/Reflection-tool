import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { studentApi } from '../../lib/api/student'
import type { ApiError } from '../../lib/api/client'
import { AvailabilityGrid } from '../../features/availability/AvailabilityGrid'
import gridStyles from '../../features/availability/availability.module.css'
import { Button, useToast } from '../../components/ui'
import styles from './student.module.css'

export function AvailabilityPage() {
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: studentApi.me })
  const [vector, setVector] = useState<boolean[]>([])
  const [count, setCount] = useState(0)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const navigate = useNavigate()

  if (!me) return <p>Loading…</p>
  if (!me.cycle) return <p>No active matching cycle for your class yet — check back later.</p>

  const grid = me.cycle.grid
  const closed = me.cycle.phase !== 'collecting'

  async function submit() {
    setBusy(true)
    try {
      const resp = await studentApi.submitAvailability(vector)
      toast(`Availability saved — ${resp.slots_selected} slots`)
      navigate('/s/survey')
    } catch (err) {
      toast((err as ApiError).detail ?? 'could not submit', true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <h2 className={styles.pageTitle}>✎ Paint your free times</h2>
      <p className={styles.pageIntro}>
        Tap or drag to select your availability between {me.cycle.grid.start} and{' '}
        {me.cycle.grid.end}.
        {me.availability_submitted && ' You already submitted — painting again replaces it.'}
      </p>
      {closed ? (
        <p>
          Submissions are closed for this cycle
          {me.cycle.phase === 'published' ? ' — see My Group below.' : '.'}
        </p>
      ) : (
        <>
          <AvailabilityGrid
            grid={grid}
            onChange={(v, c) => {
              setVector(v)
              setCount(c)
            }}
          />
          <div className={styles.footerBar}>
            <span className={gridStyles.legend}>
              <span className={gridStyles.swatchOn} /> <strong>{count} slots selected</strong>
            </span>
            <Button onClick={submit} disabled={busy || count === 0}>
              Submit availability ▷
            </Button>
          </div>
        </>
      )}
    </>
  )
}
