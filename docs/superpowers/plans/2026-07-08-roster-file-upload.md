# Roster File Upload (JSON + CSV) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let instructors upload a JSON or CSV roster file (with preview + confirm) in the Create-class modal and from a new "Manage roster" modal on the class dashboard, instead of only copy-pasting lines.

**Architecture:** Frontend-only. Pure parsing functions in `web/src/features/roster/parse.ts` (unit-tested), a `RosterUpload` component that combines file picker + paste box + preview, wired into `ClassesPage` (create modal) and `DashboardPage` (new manage-roster modal). Backend `PUT /api/classes/{id}/roster` already accepts the payload and preserves claimed enrollments on replace — no Python changes.

**Tech Stack:** React 19 + TypeScript, vitest (colocated `.test.ts` files, no config file — defaults), existing shared UI components (`Button`, `Field`, `Modal`, `Table`, `useToast` from `web/src/components/ui`), `@tanstack/react-query`.

**Spec:** `docs/superpowers/specs/2026-07-08-roster-file-upload-design.md`

**Working directory for all npm commands:** `web/` (e.g. `cd /Users/cyril/Documents/Reflectool/web`).

---

### Task 1: Roster parsing functions (`parse.ts`)

**Files:**
- Create: `web/src/features/roster/parse.ts`
- Test: `web/src/features/roster/parse.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `web/src/features/roster/parse.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { parseRosterCsv, parseRosterFile, parseRosterJson } from './parse'

describe('parseRosterCsv', () => {
  it('parses comma-separated id, name lines', () => {
    const r = parseRosterCsv('2024-001, Jane Doe\n2024-002, Mark Smith\n')
    expect(r.errors).toEqual([])
    expect(r.students).toEqual([
      { student_id: '2024-001', name: 'Jane Doe' },
      { student_id: '2024-002', name: 'Mark Smith' },
    ])
  })

  it('parses tab-separated lines and skips blank lines', () => {
    const r = parseRosterCsv('2024-001\tJane Doe\n\n2024-002\tMark Smith')
    expect(r.errors).toEqual([])
    expect(r.students).toHaveLength(2)
  })

  it('keeps commas inside the name column', () => {
    const r = parseRosterCsv('2024-001, Doe, Jane Marie')
    expect(r.students).toEqual([{ student_id: '2024-001', name: 'Doe, Jane Marie' }])
  })

  it('skips a header row (student_id or id, case-insensitive)', () => {
    expect(parseRosterCsv('student_id,name\n2024-001,Jane').students).toHaveLength(1)
    expect(parseRosterCsv('ID,Name\n2024-001,Jane').students).toHaveLength(1)
  })

  it('does not skip a first row that is real data', () => {
    const r = parseRosterCsv('2024-001, Jane Doe\n2024-002, Mark Smith')
    expect(r.students).toHaveLength(2)
  })

  it('reports lines with a missing name', () => {
    const r = parseRosterCsv('2024-001, Jane\n2024-002')
    expect(r.students).toHaveLength(1)
    expect(r.errors).toEqual(['line 2: missing name ("2024-002")'])
  })

  it('reports lines with a missing id', () => {
    const r = parseRosterCsv(', Jane Doe')
    expect(r.students).toHaveLength(0)
    expect(r.errors).toEqual(['line 1: missing student id (", Jane Doe")'])
  })

  it('reports duplicate student ids', () => {
    const r = parseRosterCsv('2024-001, Jane\n2024-001, Mark')
    expect(r.students).toHaveLength(2)
    expect(r.errors).toEqual(['duplicate student id: 2024-001'])
  })

  it('returns empty result for empty text', () => {
    expect(parseRosterCsv('')).toEqual({ students: [], errors: [] })
  })
})

describe('parseRosterJson', () => {
  it('parses a top-level array of {student_id, name}', () => {
    const r = parseRosterJson('[{"student_id": "2024-001", "name": "Jane Doe"}]')
    expect(r.errors).toEqual([])
    expect(r.students).toEqual([{ student_id: '2024-001', name: 'Jane Doe' }])
  })

  it('parses a {"students": [...]} wrapper', () => {
    const r = parseRosterJson('{"students": [{"student_id": "1", "name": "Jane"}]}')
    expect(r.students).toEqual([{ student_id: '1', name: 'Jane' }])
  })

  it('accepts "id" as an alias for student_id', () => {
    const r = parseRosterJson('[{"id": "2024-001", "name": "Jane"}]')
    expect(r.students).toEqual([{ student_id: '2024-001', name: 'Jane' }])
  })

  it('coerces numeric ids to strings', () => {
    const r = parseRosterJson('[{"student_id": 42, "name": "Jane"}]')
    expect(r.students).toEqual([{ student_id: '42', name: 'Jane' }])
  })

  it('ignores extra keys', () => {
    const r = parseRosterJson('[{"student_id": "1", "name": "Jane", "email": "j@x.com"}]')
    expect(r.errors).toEqual([])
    expect(r.students).toEqual([{ student_id: '1', name: 'Jane' }])
  })

  it('reports entries missing name or id but keeps valid ones', () => {
    const r = parseRosterJson(
      '[{"student_id": "1", "name": "Jane"}, {"student_id": "2"}, {"name": "Mark"}]',
    )
    expect(r.students).toHaveLength(1)
    expect(r.errors).toEqual(['entry 2: missing name', 'entry 3: missing student_id'])
  })

  it('reports non-object entries', () => {
    const r = parseRosterJson('["nope"]')
    expect(r.students).toHaveLength(0)
    expect(r.errors).toEqual(['entry 1: not an object'])
  })

  it('reports invalid JSON as a single fatal error', () => {
    const r = parseRosterJson('not json {')
    expect(r.students).toEqual([])
    expect(r.errors).toEqual(['not valid JSON'])
  })

  it('reports a wrong top-level shape', () => {
    const r = parseRosterJson('{"foo": 1}')
    expect(r.students).toEqual([])
    expect(r.errors).toEqual(['expected a JSON array of students, or {"students": [...]}'])
  })

  it('reports duplicate student ids', () => {
    const r = parseRosterJson(
      '[{"student_id": "1", "name": "Jane"}, {"student_id": "1", "name": "Mark"}]',
    )
    expect(r.errors).toEqual(['duplicate student id: 1'])
  })
})

describe('parseRosterFile', () => {
  it('dispatches .json (any case) to the JSON parser', () => {
    const r = parseRosterFile('roster.JSON', '[{"student_id": "1", "name": "Jane"}]')
    expect(r.students).toEqual([{ student_id: '1', name: 'Jane' }])
  })

  it('dispatches anything else to the CSV parser', () => {
    expect(parseRosterFile('roster.csv', '1, Jane').students).toHaveLength(1)
    expect(parseRosterFile('roster.txt', '1\tJane').students).toHaveLength(1)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/cyril/Documents/Reflectool/web && npx vitest run src/features/roster/parse.test.ts`
Expected: FAIL — cannot resolve `./parse` (module does not exist).

- [ ] **Step 3: Write the implementation**

Create `web/src/features/roster/parse.ts`:

```ts
export type RosterEntry = { student_id: string; name: string }
export type ParseResult = { students: RosterEntry[]; errors: string[] }

function withDuplicateCheck(students: RosterEntry[], errors: string[]): ParseResult {
  const seen = new Set<string>()
  for (const s of students) {
    if (seen.has(s.student_id)) errors.push(`duplicate student id: ${s.student_id}`)
    seen.add(s.student_id)
  }
  return { students, errors }
}

export function parseRosterCsv(text: string): ParseResult {
  const students: RosterEntry[] = []
  const errors: string[] = []
  const lines = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  lines.forEach((line, i) => {
    const [id, ...rest] = line.split(/[,\t]/)
    const student_id = id.trim()
    const name = rest.join(',').trim()
    if (i === 0 && ['student_id', 'id'].includes(student_id.toLowerCase())) return
    if (!student_id) {
      errors.push(`line ${i + 1}: missing student id ("${line}")`)
      return
    }
    if (!name) {
      errors.push(`line ${i + 1}: missing name ("${line}")`)
      return
    }
    students.push({ student_id, name })
  })
  return withDuplicateCheck(students, errors)
}

export function parseRosterJson(text: string): ParseResult {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    return { students: [], errors: ['not valid JSON'] }
  }
  if (data !== null && typeof data === 'object' && !Array.isArray(data)) {
    const wrapped = (data as { students?: unknown }).students
    if (Array.isArray(wrapped)) data = wrapped
  }
  if (!Array.isArray(data)) {
    return { students: [], errors: ['expected a JSON array of students, or {"students": [...]}'] }
  }
  const students: RosterEntry[] = []
  const errors: string[] = []
  data.forEach((item, i) => {
    if (item === null || typeof item !== 'object' || Array.isArray(item)) {
      errors.push(`entry ${i + 1}: not an object`)
      return
    }
    const obj = item as Record<string, unknown>
    const rawId = obj.student_id ?? obj.id
    const student_id =
      typeof rawId === 'string' ? rawId.trim() : typeof rawId === 'number' ? String(rawId) : ''
    const name = typeof obj.name === 'string' ? obj.name.trim() : ''
    if (!student_id) {
      errors.push(`entry ${i + 1}: missing student_id`)
      return
    }
    if (!name) {
      errors.push(`entry ${i + 1}: missing name`)
      return
    }
    students.push({ student_id, name })
  })
  return withDuplicateCheck(students, errors)
}

export function parseRosterFile(fileName: string, text: string): ParseResult {
  return fileName.toLowerCase().endsWith('.json') ? parseRosterJson(text) : parseRosterCsv(text)
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/cyril/Documents/Reflectool/web && npx vitest run src/features/roster/parse.test.ts`
Expected: PASS (all tests green).

- [ ] **Step 5: Commit**

```bash
cd /Users/cyril/Documents/Reflectool
git add web/src/features/roster/parse.ts web/src/features/roster/parse.test.ts
git commit -m "Roster parsers: JSON (array/wrapper/id-alias/numeric ids) and CSV (header skip), per-entry errors, duplicate detection (TDD)"
```

---

### Task 2: `RosterUpload` component

**Files:**
- Create: `web/src/features/roster/RosterUpload.tsx`

No unit test for this task — the project has no React testing-library setup and adding one is out of scope (YAGNI). All parsing logic it uses is covered by Task 1; the component is verified by `tsc`/lint here and end-to-end in Task 5.

- [ ] **Step 1: Write the component**

Create `web/src/features/roster/RosterUpload.tsx`:

```tsx
import { useRef, useState } from 'react'
import { Field, Table } from '../../components/ui'
import { parseRosterCsv, parseRosterFile } from './parse'
import type { ParseResult } from './parse'

const EMPTY: ParseResult = { students: [], errors: [] }

export function RosterUpload({ onChange }: { onChange: (result: ParseResult) => void }) {
  const [result, setResult] = useState<ParseResult>(EMPTY)
  const [fileName, setFileName] = useState<string | null>(null)
  const [pasted, setPasted] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  const update = (r: ParseResult) => {
    setResult(r)
    onChange(r)
  }

  const onFile = async (file: File | undefined) => {
    if (!file) return
    const text = await file.text()
    setFileName(file.name)
    setPasted('')
    update(parseRosterFile(file.name, text))
  }

  const onPaste = (text: string) => {
    setPasted(text)
    setFileName(null)
    if (fileInput.current) fileInput.current.value = ''
    update(text.trim() ? parseRosterCsv(text) : EMPTY)
  }

  const hasInput = fileName != null || pasted.trim() !== ''

  return (
    <>
      <Field label="Roster file — .json ([{student_id, name}]) or .csv (id, name per line)">
        <input
          ref={fileInput}
          type="file"
          accept=".json,.csv,.txt"
          onChange={(e) => void onFile(e.target.files?.[0])}
        />
      </Field>
      <Field label="…or paste — one student per line: id, name">
        <textarea
          value={pasted}
          onChange={(e) => onPaste(e.target.value)}
          rows={4}
          placeholder={'2024-001, Jane Doe\n2024-002, Mark Smith'}
        />
      </Field>

      {hasInput && (
        <div style={{ marginBottom: 16 }}>
          <p style={{ marginBottom: 8 }}>
            <strong>{result.students.length}</strong> student
            {result.students.length === 1 ? '' : 's'} parsed
            {fileName ? ` from ${fileName}` : ''}
            {result.students.length === 0 && result.errors.length === 0 ? ' — nothing to save' : ''}
          </p>
          {result.errors.length > 0 && (
            <ul style={{ color: 'var(--danger, #b00020)', paddingLeft: 20, marginBottom: 8 }}>
              {result.errors.map((err) => (
                <li key={err}>{err}</li>
              ))}
            </ul>
          )}
          {result.students.length > 0 && (
            <div style={{ maxHeight: 200, overflowY: 'auto' }}>
              <Table>
                <thead>
                  <tr>
                    <th>Student ID</th>
                    <th>Name</th>
                  </tr>
                </thead>
                <tbody>
                  {result.students.map((s) => (
                    <tr key={s.student_id}>
                      <td>{s.student_id}</td>
                      <td>{s.name}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          )}
        </div>
      )}
    </>
  )
}
```

Note: duplicate `student_id`s render duplicate React keys in the preview table for the moment the error is shown — acceptable, since confirm is disabled while duplicates exist and the error list names them.

- [ ] **Step 2: Verify it typechecks and lints**

Run: `cd /Users/cyril/Documents/Reflectool/web && npx tsc -b && npm run lint`
Expected: no errors (warnings about unrelated files are out of scope).

- [ ] **Step 3: Commit**

```bash
cd /Users/cyril/Documents/Reflectool
git add web/src/features/roster/RosterUpload.tsx
git commit -m "RosterUpload component: file picker + paste box with parsed preview and error list"
```

---

### Task 3: Wire `RosterUpload` into the Create-class modal

**Files:**
- Modify: `web/src/routes/instructor/ClassesPage.tsx`

- [ ] **Step 1: Replace the textarea with `RosterUpload`**

In `web/src/routes/instructor/ClassesPage.tsx`:

1. Delete the local `parseRosterText` function (lines 9–18) and the `rosterText` state.
2. Replace imports and state — the top of the file becomes:

```tsx
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
```

3. Update the mutation to use the parsed roster and reset it:

```tsx
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
```

4. In the modal, replace the roster `<Field>` (the textarea block) with:

```tsx
        <RosterUpload onChange={setRoster} />
```

5. Disable Create while the roster has errors:

```tsx
          <Button
            onClick={() => createClass.mutate()}
            disabled={!name || roster.errors.length > 0 || createClass.isPending}
          >
            Create
          </Button>
```

(`Modal`, `Field`, and the rest of the JSX stay as they are. `Field` remains imported because the name/term fields use it.)

- [ ] **Step 2: Verify typecheck, lint, and existing tests**

Run: `cd /Users/cyril/Documents/Reflectool/web && npx tsc -b && npm run lint && npm test`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
cd /Users/cyril/Documents/Reflectool
git add web/src/routes/instructor/ClassesPage.tsx
git commit -m "Create-class modal: file upload + preview via RosterUpload, replaces bare paste textarea"
```

---

### Task 4: "Manage roster" modal on the class dashboard

**Files:**
- Modify: `web/src/routes/instructor/DashboardPage.tsx`

- [ ] **Step 1: Add state, mutation, button, and modal**

In `web/src/routes/instructor/DashboardPage.tsx`:

1. Add imports (top of file — `Field` is not currently used by this page; add `RosterUpload`/`ParseResult` and keep existing imports as they are):

```tsx
import { RosterUpload } from '../../features/roster/RosterUpload'
import type { ParseResult } from '../../features/roster/parse'
```

2. Add state next to the existing `useState` calls:

```tsx
  const [rosterOpen, setRosterOpen] = useState(false)
  const [rosterDraft, setRosterDraft] = useState<ParseResult>({ students: [], errors: [] })
```

3. Add a mutation after `createCycle`:

```tsx
  const saveRoster = useMutation({
    mutationFn: () => instructorApi.uploadRoster(classId, rosterDraft.students),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ['roster', classId] })
      queryClient.invalidateQueries({ queryKey: ['rosterStatus'] })
      setRosterOpen(false)
      setRosterDraft({ students: [], errors: [] })
      toast(`Roster saved — ${r.count} students`)
    },
    onError: (err) => toast((err as unknown as ApiError).detail ?? 'could not save roster', true),
  })
```

4. Add a "Manage roster" button in the header block, next to the cycle badge (replace the existing header `<div>`'s right side):

```tsx
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <div>
          <h2 className={styles.pageTitle}>{cls.name}</h2>
          <p className={styles.pageIntro}>
            Class code <strong>{cls.class_code}</strong>
            {cycle?.deadline ? ` · deadline ${cycle.deadline}` : ''}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Button variant="secondary" onClick={() => setRosterOpen(true)}>
            Manage roster
          </Button>
          {cycle && <Badge>{cycle.status}</Badge>}
        </div>
      </div>
```

5. Add the modal just before the existing cycle `<Modal>` at the bottom:

```tsx
      <Modal open={rosterOpen}>
        <h3 style={{ marginBottom: 8 }}>Manage roster</h3>
        <p className={styles.pageIntro} style={{ marginBottom: 16 }}>
          Current roster: {roster?.students.length ?? 0} students. Uploading{' '}
          <strong>replaces</strong> the roster; students who have already joined are kept.
        </p>
        <RosterUpload onChange={setRosterDraft} />
        <div style={{ display: 'flex', gap: 12 }}>
          <Button
            onClick={() => saveRoster.mutate()}
            disabled={
              rosterDraft.students.length === 0 ||
              rosterDraft.errors.length > 0 ||
              saveRoster.isPending
            }
          >
            Save roster
          </Button>
          <Button variant="ghost" onClick={() => setRosterOpen(false)}>
            Cancel
          </Button>
        </div>
      </Modal>
```

- [ ] **Step 2: Verify typecheck, lint, and tests**

Run: `cd /Users/cyril/Documents/Reflectool/web && npx tsc -b && npm run lint && npm test`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
cd /Users/cyril/Documents/Reflectool
git add web/src/routes/instructor/DashboardPage.tsx
git commit -m "Dashboard: Manage-roster modal — upload/replace roster after class creation, claimed students preserved"
```

---

### Task 5: End-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Full frontend check**

Run: `cd /Users/cyril/Documents/Reflectool/web && npm test && npm run lint && npm run build`
Expected: tests pass, lint clean, build succeeds.

- [ ] **Step 2: Backend tests still green**

Run: `cd /Users/cyril/Documents/Reflectool && .venv/bin/python -m pytest tests/ -q`
Expected: all pass (nothing backend changed; this is a regression guard).

- [ ] **Step 3: Manual end-to-end verify against the running app**

1. Create a JSON fixture in the scratchpad, e.g. `roster.json`:
   `[{"student_id": "2026-001", "name": "Ama Mensah"}, {"student_id": "2026-002", "name": "Kofi Boateng"}]`
   and a `roster.csv`: `student_id,name` header + two rows.
2. Start the backend with a scratch DB (`REFLECTOOL_DB=<scratchpad>/e2e.db PYTHONPATH=src .venv/bin/python -m reflectool_web`) and drive the API/UI:
   - Register/login an instructor, create a class **with** the JSON file via the create modal (or exercise the same path via the API if driving the browser is unavailable), confirm the preview shows 2 students and the roster lands (`GET /api/classes/{id}/roster`).
   - From the dashboard, open Manage roster, upload the CSV, confirm the replace works and previously-claimed students survive (claim one enrollment first, then re-upload).
   - Upload a malformed JSON file and confirm errors render and the save button stays disabled.
3. Report what was observed, including anything that didn't work.

- [ ] **Step 4: Final commit if anything changed during verification**

```bash
cd /Users/cyril/Documents/Reflectool && git status
```

If clean, done. If verification required fixes, commit them with a message describing the fix.
