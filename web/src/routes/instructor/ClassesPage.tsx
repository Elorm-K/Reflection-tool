import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { instructorApi } from '../../lib/api/instructor'
import type { ApiError } from '../../lib/api/client'
import { Badge, Button, Card, Field, Modal, useToast } from '../../components/ui'
import { RosterUpload } from '../../features/roster/RosterUpload'
import type { ParseResult } from '../../features/roster/parse'
import styles from './instructor.module.css'

export function ClassesPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState('')
  const [term, setTerm] = useState('')
  const [roster, setRoster] = useState<ParseResult>({ students: [], errors: [] })
  const toast = useToast()
  const queryClient = useQueryClient()

  const { data: classes } = useQuery({ queryKey: ['classes'], queryFn: instructorApi.classes })

  const createClass = useMutation({
    mutationFn: async () => {
      const cls = await instructorApi.createClass(name, term)
      if (roster.students.length > 0) await instructorApi.uploadRoster(cls.id, roster.students)
      return cls
    },
    onSuccess: (cls) => {
      queryClient.invalidateQueries({ queryKey: ['classes'] })
      setCreateOpen(false)
      setName('')
      setTerm('')
      setRoster({ students: [], errors: [] })
      toast(`Class created — share code ${cls.class_code} with your students`)
    },
    onError: (err) => toast((err as unknown as ApiError).detail ?? 'could not create class', true),
  })

  return (
    <>
      <h2 className={styles.pageTitle}>Active Classes</h2>
      <p className={styles.pageIntro}>
        Manage your active courses, monitor group formation progress, and review student
        engagement.
      </p>

      <div className={styles.statRow}>
        <div className={styles.stat}>
          <div className={styles.statLabel}>Total classes</div>
          <div className={styles.statValue}>{classes?.length ?? '–'}</div>
        </div>
      </div>

      <div className={styles.classGrid}>
        {(classes ?? []).map((c) => (
          <Card key={c.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <div>
                <div className="mono-label">Class code</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800 }}>{c.class_code}</div>
              </div>
              <Badge variant="outline">{c.term || 'no term'}</Badge>
            </div>
            <h3 style={{ marginBottom: 16 }}>{c.name}</h3>
            <Link to={`/i/classes/${c.id}`}>
              <Button>Manage class</Button>
            </Link>
          </Card>
        ))}
      </div>

      <div className={styles.actions}>
        <Button variant="secondary" onClick={() => setCreateOpen(true)}>
          Create new class
        </Button>
      </div>

      <Modal
        open={createOpen}
        title="Create class"
        onClose={() => {
          setRoster({ students: [], errors: [] })
          setCreateOpen(false)
        }}
      >
        <Field label="Class name">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="CS50: Intro…" />
        </Field>
        <Field label="Term">
          <input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Fall 2026" />
        </Field>
        <RosterUpload onChange={setRoster} />
        <div style={{ display: 'flex', gap: 12 }}>
          <Button
            onClick={() => createClass.mutate()}
            disabled={!name || roster.errors.length > 0 || createClass.isPending}
          >
            Create
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              setRoster({ students: [], errors: [] })
              setCreateOpen(false)
            }}
          >
            Cancel
          </Button>
        </div>
      </Modal>
    </>
  )
}
