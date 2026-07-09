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
    setFileName(file.name)
    setPasted('')
    try {
      const text = await file.text()
      update(parseRosterFile(file.name, text))
    } catch {
      update({ students: [], errors: ['could not read file'] })
    }
    if (fileInput.current) fileInput.current.value = ''
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
            <ul style={{ color: 'var(--alert)', paddingLeft: 20, marginBottom: 8 }}>
              {result.errors.map((err, i) => (
                <li key={`${i}-${err}`}>{err}</li>
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
