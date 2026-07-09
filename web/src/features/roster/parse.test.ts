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

  it('reports file line numbers even when blank lines precede an error', () => {
    const r = parseRosterCsv('2024-001, Jane\n\n\n2024-002')
    expect(r.errors).toEqual(['line 4: missing name ("2024-002")'])
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
