import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { instructorApi } from '../../lib/api/instructor'
import type { ApiError } from '../../lib/api/client'
import { Badge, Button, Card, Field, Modal, useToast } from '../../components/ui'
import styles from './instructor.module.css'

function parseRosterText(text: string): { student_id: string; name: string }[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [id, ...rest] = line.split(/[,\t]/)
      return { student_id: id.trim(), name: rest.join(',').trim() }
    })
}

export function ClassesPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState('')
  const [term, setTerm] = useState('')
  const [rosterText, setRosterText] = useState('')
  const toast = useToast()
  const queryClient = useQueryClient()

  const { data: classes } = useQuery({ queryKey: ['classes'], queryFn: instructorApi.classes })

  const createClass = useMutation({
    mutationFn: async () => {
      const cls = await instructorApi.createClass(name, term)
      const roster = parseRosterText(rosterText)
      if (roster.length > 0) await instructorApi.uploadRoster(cls.id, roster)
      return cls
    },
    onSuccess: (cls) => {
      queryClient.invalidateQueries({ queryKey: ['classes'] })
      setCreateOpen(false)
      setName('')
      setTerm('')
      setRosterText('')
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

      <Modal open={createOpen}>
        <h3 style={{ marginBottom: 16 }}>Create class</h3>
        <Field label="Class name">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="CS50: Intro…" />
        </Field>
        <Field label="Term">
          <input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Fall 2026" />
        </Field>
        <Field label="Roster — one student per line: id, name">
          <textarea
            value={rosterText}
            onChange={(e) => setRosterText(e.target.value)}
            rows={6}
            placeholder={'2024-001, Jane Doe\n2024-002, Mark Smith'}
          />
        </Field>
        <div style={{ display: 'flex', gap: 12 }}>
          <Button onClick={() => createClass.mutate()} disabled={!name || createClass.isPending}>
            Create
          </Button>
          <Button variant="ghost" onClick={() => setCreateOpen(false)}>
            Cancel
          </Button>
        </div>
      </Modal>
    </>
  )
}
