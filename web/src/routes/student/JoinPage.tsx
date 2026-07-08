import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { setAuth } from '../../lib/api/client'
import type { ApiError } from '../../lib/api/client'
import { studentApi } from '../../lib/api/student'
import { Button, Card, Field, useToast } from '../../components/ui'
import styles from './student.module.css'

export function JoinPage() {
  const [classCode, setClassCode] = useState('')
  const [studentId, setStudentId] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const toast = useToast()

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      const resp = await studentApi.join(classCode.trim(), studentId.trim())
      setAuth(resp.token, 'student')
      toast(`Welcome, ${resp.name || resp.student_id} — joined ${resp.class_name}`)
      navigate('/s/availability')
    } catch (err) {
      toast((err as ApiError).detail ?? 'could not join', true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={styles.shell}>
      <header className={styles.topBar}>
        <h1>GroupMatcher</h1>
      </header>
      <main className={styles.main}>
        <h2 className={styles.pageTitle}>Join your class</h2>
        <p className={styles.pageIntro}>
          Enter the class code your instructor shared and your student ID.
        </p>
        <Card>
          <form onSubmit={submit}>
            <Field label="Class code">
              <input
                value={classCode}
                onChange={(e) => setClassCode(e.target.value.toUpperCase())}
                placeholder="e.g. 7KQ2FD"
                autoComplete="off"
                required
              />
            </Field>
            <Field label="Student ID">
              <input
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                placeholder="e.g. 2024-118"
                autoComplete="off"
                required
              />
            </Field>
            <Button type="submit" disabled={busy}>
              Join class ▷
            </Button>
          </form>
        </Card>
      </main>
    </div>
  )
}
