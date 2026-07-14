# Reflectool — Technical Specification

> Audience: someone new to the project who needs to understand how the matcher
> works well enough to change it. This document describes the tool **as the code
> in `src/reflectool/` actually behaves today**, not what it might become. Where
> the code stops short of an idea, that's called out under
> [Limits & not-yet-done](#limits--not-yet-done).

## What it is and what it solves

Reflectool sorts a class roster into small weekly discussion groups (3–5
students) so that group members (a) share enough free time to actually meet each
week and (b) tend to share background (gender, disability experience), because
people open up more readily in a group where they don't feel like the odd one
out. It is a **deterministic Python algorithm** — no AI, no randomness, no
external solver. Same roster and config in, same groups out, every time.

The core (`src/reflectool/`) is standard-library-only Python driven from a CLI.
Nothing it produces for students ever contains demographic data, and no grouping
reaches students until an instructor has approved it.

> There is also a FastAPI + React web pilot under `src/reflectool_web/` and
> `web/`. It is **out of scope for this document**, which covers only the
> matcher core and its CLI.

## How it works, end to end

1. **Collect.** Students provide their weekly availability as a grid of 30-minute
   slots (default: 08:00–20:00, Monday–Sunday = 168 slots) and answer an optional
   demographic survey (gender, disability). Every field is skippable.
2. **Intake** (`intake`). Validate the roster file and report aggregate stats —
   counts, free-slot spread, and how many students have too little availability
   to meet the overlap floor. Blank demographics never block a student.
3. **Match** (`match`). The deterministic matcher reads the roster + config and
   produces a **proposal**: groups of 3–5 sharing at least `min_overlap` mutually
   free slots, plus an `unplaced` list (with reasons) and any equity `warnings`.
4. **Review** (`show`, `composition`). The instructor inspects the proposal. The
   `composition` view is the *only* place per-group demographic aggregates appear.
5. **Adjust** (`edit`). Manual moves and assignments, each re-validated against the
   hard constraints before it can be saved. Invalid edits are rejected with the
   specific rule they broke.
6. **Approve → Publish** (`approve`, `publish`). Two separate, ordered steps:
   `proposed → approved → published`. Only after publishing are per-student
   notifications available.
7. **Support** (`explain`, `student-view`, `notify-all`). Privacy-safe facts about
   a placement and each student's own-group notification (group number, member
   names, meeting slots — nothing else).

## The matching algorithm, plainly

The whole algorithm lives in [`matcher.py`](../src/reflectool/matcher.py) and the
scoring terms in [`objective.py`](../src/reflectool/objective.py). It is a
**greedy seed-and-grow build followed by a bounded swap-repair pass** — not a
constraint solver, and it does not prove optimality. Determinism comes entirely
from iterating students in `student_id` order and breaking every local tie by
smallest id; there are no random draws.

### Step by step

1. **Split into schedule-compatible components.** Two students are *compatible*
   if they share at least `min_overlap` free slots. Students who share no time can
   never be grouped, so the roster is partitioned into connected components of this
   compatibility graph and each component is solved on its own. A component smaller
   than `min_size` can't form a group — everyone in it goes straight to `unplaced`.
2. **Plan the size mix** for each component: the *fewest* groups that keep every
   group within `[min_size, max_size]`; among those, the fewest groups of 3, then
   the most groups of 5. (This is only a target shape — the greedy fill below can
   still deviate when identity or schedule pressure forces smaller groups.)
3. **Seed and grow** each planned group. The seed is the *most constrained*
   remaining student — the one with the fewest compatible peers left, ties broken
   by smallest id. The group then repeatedly admits whichever candidate keeps it
   feasible (still ≥ `min_overlap` shared slots) **and** maximizes the group score
   (below). If a group can't reach `min_size` feasibly, its members become
   leftovers.
4. **Repair pass** (up to 2 sweeps). Swap members between groups to remove equity
   and lone-minority isolation, but never in a way that breaks a hard constraint. A
   swap is kept only if it strictly lowers total isolation.
5. **Resolve leftovers.** For each leftover, in id order: (a) grow an existing
   group that still has room (≤ `max_size`) and stays feasible; else (b) form a new
   group of ≥ `min_size` from remaining leftovers; else (c) place the student on
   `unplaced` with a reason. A second repair sweep runs afterward.
6. **Finalize.** Sort groups by their smallest member id, assign sequential
   `group_id`s, take the first `min_overlap` shared slots as the group's meeting
   slots, and emit an equity warning for any group that still isolates a lone
   woman/non-binary member or a lone disabled member.

### What the group score sorts on (priority order)

`group_score` (in [`objective.py`](../src/reflectool/objective.py)) returns a
tuple compared **lexicographically** — earlier entries dominate later ones
absolutely:

1. **Equity safeguard (fixed, not configurable).** Avoid isolating a lone woman or
   non-binary student. Two or more protected members "protect each other" and count
   as no isolation; a member who didn't disclose gender is never treated as
   isolated. This tier always sits **above** everything in `config.priority` — no
   configuration can switch it off.
2. **One tier per `config.priority` entry, in order.** Default priority is
   `["availability", "gender", "disability"]`:
   - `availability` rewards a group **comfortably clearing the overlap floor** —
     `min(shared slots, min_overlap + 1)`. Extra shared time beyond that adds
     nothing, so schedule never dominates identity.
   - `gender` / `disability` reward **homogeneity**: the share of members holding
     the most common *disclosed* value. Undisclosed values are excluded from the
     count; an all-undisclosed group scores neutral (never penalized).
3. **Lone-disability penalty.** A group with exactly one member who has a known
   disability among peers who explicitly said "none" is penalized. (Gender
   isolation is already handled by tier 1; this is the parallel disability harm,
   ranked below the configurable factors.)
4. **Size preference.** Prefer groups closest to `target_size` (default 5).

### Hard constraints (never traded away)

Enforced at match time and re-checked on every manual edit:

- Every group has **3 ≤ size ≤ 5**.
- Every group shares **≥ `min_overlap`** mutually free slots.
- Every student ends up in **exactly one group or on the `unplaced` list** — never
  silently dropped.
- **No demographic data** appears in the proposal or anything downstream of it
  (enforced in code, not just convention — see below).

### Edge-case behavior (as coded)

- **Undisclosed / blank demographics** (`""`, `blank`, `prefer_not_to_disclose`,
  `na`, etc.) normalize to `undisclosed` and are neutral everywhere: never a
  homogeneity bonus, never a penalty, never counted as a minority.
- **Open value set.** Unrecognized gender/disability values are slugged and kept as
  distinct values, never dropped. The matcher assumes no fixed list.
- **Unplaceable students** land on `unplaced` with a human-readable reason rather
  than being forced into an infeasible group.
- **Uneven counts** follow the size-mix plan, but identity/schedule pressure can
  legitimately produce more, smaller groups than the arithmetic minimum.

## Data

### Input — roster file (JSON)

A single JSON object with a `students` array and an optional `config` object.
There is **no separate "slots" input** — meeting-slot labels are derived from the
grid in `config`. See [`data/demo_roster_6.json`](../data/demo_roster_6.json) for
a runnable example.

```json
{
  "config": {
    "target_size": 5, "min_size": 3, "max_size": 5, "min_overlap": 2,
    "priority": ["availability", "gender", "disability"], "tiebreak_seed": 0,
    "grid": {"days": 7, "start": "08:00", "end": "20:00", "slot_minutes": 30}
  },
  "students": [
    {"id": "s01", "name": "Ada P.", "availability": [1, 1, 0, 0],
     "gender": "woman", "disability": "adhd"}
  ]
}
```

Per-student fields:

| Field | Meaning |
|---|---|
| `id` (or `student_id`) | Stable unique string id. Used for output and tie-breaking. Required. |
| `availability` | Boolean/0–1 vector; length **must equal** the grid's slot count (default 168). Required. |
| `gender` | Raw survey value, open set. Optional (blank → `undisclosed`). |
| `disability` | Raw survey value, open set. Optional (blank → `undisclosed`). |
| `name` | Display name for published notifications. Optional. |

Config defaults (from [`io_parse.py`](../src/reflectool/io_parse.py)):
`target_size=5`, `min_size=3`, `max_size=5`, `min_overlap=2`,
`priority=("availability","gender","disability")`, and a 7-day 08:00–20:00 grid at
30-minute resolution. `match` also accepts `--min-overlap` and `--priority` flags
that override the file's config for one run.

Validation rejects structural problems (missing id, duplicate id, wrong-length
availability vector) with clear errors. It **never** rejects a student for a blank
demographic.

### Output — proposal (JSON)

```json
{
  "status": "proposed",
  "groups": [
    {"group_id": 1, "members": ["s01", "s02", "s03"],
     "meeting_slots": ["Mon-08:00", "Mon-08:30"]}
  ],
  "unplaced": [{"student_id": "s07", "reason": "..."}],
  "warnings": ["group 2 has a lone member with a known disability ..."]
}
```

`group_id` is a plain sequence number, `members` are ids, `meeting_slots` are
`Day-HH:MM` labels generated from the grid. The `unplaced` and `warnings` lists
are always present (empty when nothing to report) — nothing is smoothed over.

### Other outputs

- **`composition`** — instructor-only per-group gender/disability aggregates and
  homogeneity scores. Rendered live from the roster; never written into the
  proposal or shown to students.
- **`student-view` / `notify-all`** — a student's own group: group number, member
  **names**, meeting slots. Available only after `published`.
- **`explain`** — privacy-safe placement facts for one student (group id, size,
  shared-slot count, meeting slots, required overlap, status) or their unplaced
  reason. No demographics.

## Privacy enforcement

The demographic invariant is enforced in code, not by convention:
[`output_format.assert_no_demographics`](../src/reflectool/output_format.py)
recursively scans a structure for any `gender`/`disability` key and raises
`PrivacyViolation` if found. It runs before the proposal is built, before every
state transition, before every edit is saved, and before each student
notification. The proposal schema simply has no demographic fields. The only
authorized identity surface is the instructor's live `composition` view.

## The review & approval lifecycle

Managed by [`review_workflow.py`](../src/reflectool/review_workflow.py) as a
strict state machine:

```
proposed  →  approved  →  published
```

- **Edits** (`edit`, actions `move` / `assign`) are allowed only while `proposed`.
  Each edit re-validates both affected groups against the size and overlap
  constraints; a rejected edit leaves the session unchanged. The instructor can
  explicitly override with `--allow-oversize` (permits a single group of 6) or
  `--allow-low-overlap`; both are annotated in the audit log.
- **Transitions** are one-way and one-step: you cannot skip from `proposed` to
  `published`, and illegal transitions raise `IllegalTransition`.
- **Notifications** raise `PreApprovalLeak` if requested before `published`, so
  nothing can reach students early.

Session state (roster, config, proposal, audit log) persists between CLI calls in
a JSON state file. The audit log records every match, edit, override, and
transition.

## Code structure

| File | Responsibility |
|---|---|
| [`io_parse.py`](../src/reflectool/io_parse.py) | Parse/validate/normalize input. `Grid`, `Config`, `Student` dataclasses; demographic normalization; the open-value + undisclosed rules. |
| [`objective.py`](../src/reflectool/objective.py) | Scoring terms: `group_score` (the lexicographic tuple), `homogeneity`, `group_overlap_slots`, equity and lone-minority isolation counts. |
| [`matcher.py`](../src/reflectool/matcher.py) | The pure `match(students, config)` algorithm: components → size plan → seed-and-grow → repair → remainder resolution. No I/O, no state. |
| [`output_format.py`](../src/reflectool/output_format.py) | Builds the privacy-safe proposal; `assert_no_demographics` guard. |
| [`review_workflow.py`](../src/reflectool/review_workflow.py) | `Session`, the state machine, `composition_view`, and re-validated manual edits. |
| [`notify.py`](../src/reflectool/notify.py) | Per-student, post-publish notification views. |
| [`cli.py`](../src/reflectool/cli.py) | The CLI: one subcommand per lifecycle action; JSON session persistence. |

Tests in [`tests/`](../tests/) cover constraints, privacy, determinism, the state
machine, scoring terms, and edge cases (104 core tests; the `tests/web/` suite
skips cleanly when the web extras aren't installed).

## Limits & not-yet-done

Called out honestly so no one mistakes intent for behavior:

- **Greedy heuristic, not optimal.** The matcher does a greedy build plus a
  2-sweep repair; it does not search the whole solution space or guarantee an
  optimal partition. (An earlier draft framed this as a CSP solver with optimality
  guarantees — the code does not do that.)
- **`tiebreak_seed` is vestigial.** The config field exists and round-trips, but
  the matcher uses no randomness, so it currently has no effect. `[VERIFY]` whether
  it should be removed or wired to something.
- **No global partition-level tie-break.** Determinism comes from id-ordered
  iteration and local smallest-id tie-breaks, not from comparing whole partitions
  by size profile or total overlap.
- **Live post-publish edits exist but aren't in the CLI.** `apply_live_edit`
  (re-validated reassignment of an already-published grouping) lives in
  `review_workflow.py` but no CLI subcommand exposes it.
- **The "must have viewed the proposal" approval gate is not in the core.** The CLI
  `approve` only enforces the state transition; the view-before-approve gate exists
  only in the web pilot (out of scope here).
- **No Spring 2025 validation test.** The suite reproduces the small spec example,
  but there is no reconstruction of a real prior cohort — that data is not in the
  repo.
- **JSON input only.** There is no CSV importer.
