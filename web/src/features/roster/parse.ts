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
