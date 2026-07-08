# Roster file upload (JSON + CSV) — design

Date: 2026-07-08
Status: approved by instructor (Cyril) in-session

## Problem

The only way to enter students in the web app is pasting `id, name` lines into a
textarea in the Create-class modal (`web/src/routes/instructor/ClassesPage.tsx`).
There is no way to upload a file, and no way to change the roster after class
creation from the UI. Instructors typically have rosters as JSON or CSV exports
and should not have to copy-paste.

## Decisions (confirmed with user)

- Accept **both JSON and CSV** file uploads (plus keep the paste box).
- Available in **the Create-class modal and on the class dashboard** ("Manage
  roster"), so rosters can be added/replaced after creation.
- **Preview + confirm** before anything is saved.

## Scope

Frontend-only. The backend endpoint `PUT /api/classes/{class_id}/roster`
already accepts `{"students": [{"student_id", "name"}]}` and already preserves
students with claimed enrollments when replacing (`repo.replace_roster`).
No Python changes.

## Components

### `web/src/features/roster/parse.ts`

Pure parsing functions, unit-tested with vitest:

- `parseRosterJson(text) -> ParseResult`
  - Accepts a top-level array `[{student_id, name}, …]` or a `{students: […]}`
    wrapper.
  - `id` is accepted as an alias for `student_id`; numeric ids are coerced to
    strings (common in LMS JSON exports).
  - Entries missing/blank `student_id` or `name`, or with other non-string
    values, become per-entry errors (row index + reason); valid entries still
    parse.
  - Non-JSON or wrong top-level shape is a single fatal error.
- `parseRosterCsv(text) -> ParseResult` — extracts today's inline line parser:
  one student per line, `id, name`, comma or tab separated. Skips an optional
  header row (first line whose id column is `student_id` or `id`,
  case-insensitive). Blank lines ignored; lines without a name column are
  per-line errors.
- `parseRosterFile(fileName, text)` — dispatches by extension (`.json` → JSON,
  anything else → CSV).
- Both parsers flag duplicate `student_id`s as errors (client-side, so they
  show in the preview instead of a server 400).

`ParseResult = { students: {student_id, name}[]; errors: string[] }`

### `web/src/features/roster/RosterUpload.tsx`

Controlled component used in both placements:

- File picker (`accept=".json,.csv,.txt"`) **and** the existing paste textarea;
  whichever was touched last wins as the source.
- Renders the preview: "N students parsed", scrollable table of entries, and
  the error list.
- Reports `{ students, errors }` to the parent via a callback; the parent
  decides button enablement (valid = ≥1 student and 0 errors).

## Placements

1. **Create-class modal** (`ClassesPage.tsx`): textarea replaced by
   `RosterUpload`. Create button requires class name; roster optional but if
   provided must be valid. Behavior otherwise unchanged (create class, then
   upload roster if non-empty).
2. **Class dashboard** (`DashboardPage.tsx`): "Manage roster" button opens a
   modal with `RosterUpload` plus the current roster count. Confirm calls
   `instructorApi.uploadRoster`. Modal copy states: *replaces the current
   roster; students who have already joined are kept.* On success, invalidate
   the `roster` and `rosterStatus` queries.

## Error handling

- Parse errors: shown inline in the preview; confirm disabled.
- Server errors (e.g. race on duplicate): surfaced via toast, as elsewhere.
- Empty file / zero valid students: confirm disabled with a hint.

## Privacy

Roster data is `student_id` + `name` only — no demographic fields exist on this
surface, so the demographic-privacy invariant is untouched. Extra keys in
uploaded JSON (whatever they are) are ignored, never stored or echoed.

## Testing

- Vitest unit tests for `parse.ts`: valid JSON array, `students` wrapper, `id`
  alias, malformed JSON, wrong shape, missing fields, CSV with/without header,
  tab-separated, duplicates, blank lines.
- Manual end-to-end verify: create class with JSON file; replace roster from
  dashboard with CSV; confirm claimed students survive replacement.
