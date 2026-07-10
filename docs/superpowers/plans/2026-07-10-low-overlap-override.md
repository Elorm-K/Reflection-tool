# Low-Overlap Override Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the instructor explicitly override the `min_overlap` constraint when moving/assigning a student (mirroring the existing `allow_oversize` override), with a ⚠ confirm dialog, an audit annotation, and a safe student-notification fallback when the group has no shared meeting time.

**Architecture:** One new boolean flag `allow_low_overlap` threaded through the same four layers `allow_oversize` already crosses: `review_workflow._validate_group` (skip check when flagged, hint in the error otherwise) → CLI `edit --allow-low-overlap` → web `EditBody`/`ReassignmentBody` → review-board precheck + confirm modals. Notification bodies gain a fallback sentence when `meeting_slots` is empty.

**Tech Stack:** Python 3.11 stdlib core + pytest; FastAPI web layer; React/TypeScript frontend with vitest.

**Spec:** `docs/superpowers/specs/2026-07-10-low-overlap-override-design.md`

Commands used throughout (run from repo root `/Users/cyril/Documents/Reflectool`):
- Backend tests: `.venv/bin/python -m pytest tests/ -q` (single test: `.venv/bin/python -m pytest tests/test_review_workflow.py::TestApplyEdit::test_name -v`)
- Frontend tests: `cd web && npm test`
- Frontend typecheck/build: `cd web && npm run build`

---

### Task 1: Core workflow — `allow_low_overlap` in `_validate_group` / `_apply_edit_inner`

**Files:**
- Modify: `src/reflectool/review_workflow.py:100-200`
- Test: `tests/test_review_workflow.py` (class `TestApplyEdit`)

- [ ] **Step 1: Write the failing tests**

Add to `TestApplyEdit` in `tests/test_review_workflow.py` (fixtures `make_session`/`make_student` already exist at the top of the file; `SMALL_CONFIG.min_overlap` is 2):

```python
    def test_low_overlap_rejection_mentions_override_hint(self):
        # Same setup as test_move_breaking_min_overlap_rejected: s01 shares no
        # slots with the other group, s07 keeps the source at min_size.
        session = make_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        other = next(g for g in session.proposal["groups"] if "s01" not in g["members"])
        with pytest.raises(InvalidEdit, match="allow_low_overlap"):
            apply_edit(session, {"action": "move", "student_id": "s01", "to_group": other["group_id"]})

    def test_low_overlap_allowed_with_explicit_override_and_logged(self):
        session = make_session(extra=[make_student("s07", [1, 1, 1, 1], "man", "none")])
        other = next(g for g in session.proposal["groups"] if "s01" not in g["members"])
        apply_edit(
            session,
            {"action": "move", "student_id": "s01", "to_group": other["group_id"],
             "allow_low_overlap": True},
        )
        target = next(g for g in session.proposal["groups"] if g["group_id"] == other["group_id"])
        assert "s01" in target["members"]
        # no mutually-free slot -> surfaced as an empty slot list, never invented
        assert target["meeting_slots"] == []
        assert any("low-overlap override" in entry for entry in session.audit_log)

    def test_low_overlap_override_does_not_bypass_size_bounds(self):
        session = make_session()
        # any move out of a size-3 group still violates min_size, flag or not
        with pytest.raises(InvalidEdit, match="size"):
            apply_edit(session, {"action": "move", "student_id": "s06", "to_group": 1,
                                 "allow_low_overlap": True})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_review_workflow.py -q -k low_overlap`
Expected: first two FAIL (`InvalidEdit` message has no `allow_low_overlap`; move raises instead of applying); the third may already pass (size check fires first) — that's fine, it pins the boundary.

- [ ] **Step 3: Implement**

In `src/reflectool/review_workflow.py`, replace `_validate_group` (lines 100–112) with:

```python
def _validate_group(
    session: Session,
    members: list[Student],
    allow_oversize: bool,
    allow_low_overlap: bool = False,
) -> None:
    config = session.config
    max_size = config.max_size + 1 if allow_oversize else config.max_size
    if not (config.min_size <= len(members) <= max_size):
        raise InvalidEdit(
            f"group size {len(members)} violates size bounds "
            f"[{config.min_size}, {config.max_size}]"
            + ("" if allow_oversize else " (pass allow_oversize for an explicit instructor override)")
        )
    if len(group_overlap_slots(members)) < config.min_overlap and not allow_low_overlap:
        raise InvalidEdit(
            f"group would share fewer than min_overlap={config.min_overlap} mutually free slots"
            " (pass allow_low_overlap for an explicit instructor override)"
        )
```

Add a suffix helper right after `_validate_group`:

```python
def _override_suffix(session: Session, members: list[Student],
                     allow_oversize: bool, allow_low_overlap: bool) -> str:
    """Audit-trail annotation for constraints the instructor explicitly overrode."""
    suffix = ""
    if allow_oversize and len(members) > session.config.max_size:
        suffix += " [oversize override]"
    if allow_low_overlap and len(group_overlap_slots(members)) < session.config.min_overlap:
        suffix += " [low-overlap override]"
    return suffix
```

In `_apply_edit_inner`, after `allow_oversize = bool(edit.get("allow_oversize"))` add:

```python
    allow_low_overlap = bool(edit.get("allow_low_overlap"))
```

In the `move` branch, pass the flag to the target validation and use the helper in the audit line (the source check stays strict — removing a member can only grow the shared-slot set):

```python
        _validate_group(session, new_source, allow_oversize=False)
        _validate_group(session, new_target, allow_oversize, allow_low_overlap)
        source["members"] = [sid for sid in source["members"] if sid != student_id]
        target["members"] = sorted(target["members"] + [student_id])
        _refresh_group(session, source)
        _refresh_group(session, target)
        session.audit_log.append(
            f"{prefix}move {student_id}: group {source['group_id']} -> {to_group}"
            + _override_suffix(session, new_target, allow_oversize, allow_low_overlap)
        )
```

In the `assign` branch likewise:

```python
        _validate_group(session, new_target, allow_oversize, allow_low_overlap)
        target["members"] = sorted(target["members"] + [student_id])
        session.proposal["unplaced"] = [
            u for u in session.proposal["unplaced"] if u["student_id"] != student_id
        ]
        _refresh_group(session, target)
        session.audit_log.append(
            f"{prefix}assign unplaced {student_id} -> group {to_group}"
            + _override_suffix(session, new_target, allow_oversize, allow_low_overlap)
        )
```

(Note: `assign` previously logged no oversize suffix; the shared helper now annotates both overrides on both actions — deliberate audit-completeness improvement, invariant 4.)

- [ ] **Step 4: Run the module's tests**

Run: `.venv/bin/python -m pytest tests/test_review_workflow.py -q`
Expected: all PASS (existing `match="min_overlap"` assertions still match the extended message).

- [ ] **Step 5: Commit**

```bash
git add src/reflectool/review_workflow.py tests/test_review_workflow.py
git commit -m "Workflow core: allow_low_overlap instructor override (TDD)"
```

---

### Task 2: CLI — `edit --allow-low-overlap`

**Files:**
- Modify: `src/reflectool/cli.py:129-143` (cmd_edit) and `:225-231` (parser)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli.py` inside `class TestCli` (module fixtures `paths`/`run` exist; `ROSTER` uses `min_overlap: 2`). A move that violates *only* overlap needs a 4-member source, so the test writes its own roster:

```python
    def test_edit_low_overlap_override_flag(self, tmp_path, capsys):
        # Two availability blocks: group 1 = s01..s04 (early), group 2 = s05..s07 (late).
        # Moving s01 -> group 2 keeps the source at min_size but shares 0 slots.
        roster = {
            "config": ROSTER["config"],
            "students": [
                {"id": f"s{i:02d}", "name": f"P{i}",
                 "availability": [1, 1, 0, 0] if i <= 4 else [0, 0, 1, 1],
                 "gender": "man", "disability": "none"}
                for i in range(1, 8)
            ],
        }
        roster_path = tmp_path / "roster.json"
        roster_path.write_text(json.dumps(roster))
        state = tmp_path / "session.json"
        run(capsys, "match", "--roster", roster_path, "--state", state)

        code, out = run(capsys, "edit", "--state", state, "--action", "move",
                        "--student", "s01", "--to-group", "2")
        assert code == 1
        assert "allow_low_overlap" in out  # rejection names the override

        code, out = run(capsys, "edit", "--state", state, "--action", "move",
                        "--student", "s01", "--to-group", "2", "--allow-low-overlap")
        assert code == 0
        proposal = json.loads(out)
        target = next(g for g in proposal["groups"] if g["group_id"] == 2)
        assert "s01" in target["members"]
        assert target["meeting_slots"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli.py::TestCli::test_edit_low_overlap_override_flag -v`
Expected: FAIL — argparse errors on the unknown `--allow-low-overlap` flag (exit code 2 / SystemExit).

- [ ] **Step 3: Implement**

In `src/reflectool/cli.py`, `cmd_edit` — add the key to the edit dict:

```python
        {
            "action": args.action,
            "student_id": args.student,
            "to_group": args.to_group,
            "allow_oversize": args.allow_oversize,
            "allow_low_overlap": args.allow_low_overlap,
        },
```

In the `edit` subparser block, after the `--allow-oversize` line:

```python
    p.add_argument("--allow-low-overlap", action="store_true", dest="allow_low_overlap")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/reflectool/cli.py tests/test_cli.py
git commit -m "CLI: edit --allow-low-overlap flag"
```

---

### Task 3: Web API — flag on `/edits`

**Files:**
- Modify: `src/reflectool_web/routers/cycles.py:51-56` (EditBody)
- Test: `tests/web/test_edits.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/web/test_edits.py` a fixture with two disjoint availability blocks and two tests (module already imports `make_class`, `register_and_login`, `join`, `make_cycle`, and defines `SMALL_GRID`):

```python
@pytest.fixture()
def split(client):
    """Eight students in two disjoint availability blocks -> two groups of four
    with no cross overlap; any cross move violates min_overlap only."""
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": f"s{i:02d}", "name": f"S{i}"} for i in range(1, 9)],
    )
    cycle = make_cycle(client, headers, cls["id"],
                       config={"grid": SMALL_GRID, "min_overlap": 1})
    for i in range(1, 9):
        s = join(client, cls, f"s{i:02d}")
        slots = [1, 1, 0, 0] if i <= 4 else [0, 0, 1, 1]
        client.put("/api/me/availability", json={"slots": slots}, headers=s)
    proposal = client.post(f"/api/cycles/{cycle['id']}/match", headers=headers).json()
    assert sorted(len(g["members"]) for g in proposal["groups"]) == [4, 4]
    return {"headers": headers, "cls": cls, "cycle": cycle, "proposal": proposal}


def cross_move(split):
    """s from group A -> group B: source stays at min_size, zero shared slots."""
    groups = split["proposal"]["groups"]
    return {"action": "move", "student_id": groups[0]["members"][0],
            "to_group": groups[1]["group_id"]}


def test_low_overlap_edit_rejected_without_flag(client, split):
    resp = client.post(f"/api/cycles/{split['cycle']['id']}/edits",
                       json=cross_move(split), headers=split["headers"])
    assert resp.status_code == 422
    assert "min_overlap" in resp.json()["detail"]
    assert "allow_low_overlap" in resp.json()["detail"]


def test_low_overlap_edit_applies_with_flag(client, split):
    move = cross_move(split)
    resp = client.post(f"/api/cycles/{split['cycle']['id']}/edits",
                       json={**move, "allow_low_overlap": True},
                       headers=split["headers"])
    assert resp.status_code == 200, resp.text
    target = next(g for g in resp.json()["groups"] if g["group_id"] == move["to_group"])
    assert move["student_id"] in target["members"]
    assert target["meeting_slots"] == []  # surfaced, never invented
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/web/test_edits.py -q -k low_overlap`
Expected: first test FAILS on the `allow_low_overlap` hint only if Task 1 isn't merged (it is — so it may pass); second FAILS: Pydantic drops the unknown `allow_low_overlap` field, server returns 422.

- [ ] **Step 3: Implement**

In `src/reflectool_web/routers/cycles.py`, add the field to `EditBody`:

```python
class EditBody(BaseModel):
    action: Literal["move", "assign"]
    student_id: str
    to_group: int
    allow_oversize: bool = False
    allow_low_overlap: bool = False
```

(`apply_edit(session, body.model_dump())` already forwards it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/web/test_edits.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/reflectool_web/routers/cycles.py tests/web/test_edits.py
git commit -m "Web edits: allow_low_overlap flag on EditBody (TDD)"
```

---

### Task 4: Web API — flag on `/reassignments` + no-shared-time notification fallback

**Files:**
- Modify: `src/reflectool_web/routers/cycles.py:58-65` (ReassignmentBody) and `:271-311` (`_notify_reassignment`)
- Test: `tests/web/test_reassignments.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/web/test_reassignments.py` (module already imports `make_class`, `register_and_login`, `SMALL_GRID`, `join`, `make_cycle`):

```python
@pytest.fixture()
def published_split(client):
    """Like `published`, but two disjoint availability blocks (4 early, 4 late):
    any cross move violates min_overlap only. Published, student tokens kept."""
    headers = register_and_login(client)
    cls = make_class(
        client, headers,
        roster=[{"student_id": f"s{i:02d}", "name": f"Student {i}"} for i in range(1, 9)],
    )
    cycle = make_cycle(client, headers, cls["id"],
                       config={"grid": SMALL_GRID, "min_overlap": 1})
    students = {}
    for i in range(1, 9):
        sid = f"s{i:02d}"
        students[sid] = join(client, cls, sid)
        slots = [1, 1, 0, 0] if i <= 4 else [0, 0, 1, 1]
        client.put("/api/me/availability", json={"slots": slots},
                   headers=students[sid])
    client.post(f"/api/cycles/{cycle['id']}/match", headers=headers)
    assert client.get(f"/api/cycles/{cycle['id']}/review-board",
                      headers=headers).status_code == 200
    assert client.post(f"/api/cycles/{cycle['id']}/approve",
                       headers=headers).status_code == 200
    assert client.post(f"/api/cycles/{cycle['id']}/publish",
                       headers=headers).status_code == 200
    proposal = client.get(f"/api/cycles/{cycle['id']}/proposal", headers=headers).json()
    return {"headers": headers, "cls": cls, "cycle": cycle,
            "proposal": proposal, "students": students}


def test_live_low_overlap_rejected_without_flag(client, published_split):
    move = first_move(published_split)
    resp = reassign(client, published_split, {**move, "confirm": True})
    assert resp.status_code == 422
    assert "min_overlap" in resp.json()["detail"]


def test_live_low_overlap_applies_with_flag_and_safe_notification(client, published_split):
    move = first_move(published_split)
    resp = reassign(client, published_split,
                    {**move, "confirm": True, "allow_low_overlap": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    target = next(g for g in body["proposal"]["groups"]
                  if g["group_id"] == move["to_group"])
    assert move["student_id"] in target["members"]
    assert target["meeting_slots"] == []
    assert body["notified"] >= 1

    # the moved student's notification says there's no shared time yet —
    # never an empty "New meeting time: ." and never demographics
    notes = client.get("/api/me/notifications",
                       headers=published_split["students"][move["student_id"]]).json()
    note = notes["notifications"][0]
    assert note["kind"] == "group-changed"
    assert "does not yet have a shared meeting time" in note["body"]
    assert "New meeting time: ." not in note["body"]
    assert "gender" not in note["body"].lower()
    assert "disability" not in note["body"].lower()
```

`first_move` already exists in this module and picks group A's first member into group B — with `published_split` that's exactly the zero-overlap cross move (source drops 4→3, target 4→5, both within size bounds).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/web/test_reassignments.py -q -k low_overlap`
Expected: first PASSES already (rejection comes from Task 1's core); second FAILS — `allow_low_overlap` isn't a `ReassignmentBody` field yet, so the server still 422s.

- [ ] **Step 3: Implement**

In `src/reflectool_web/routers/cycles.py`, add the field to `ReassignmentBody`:

```python
class ReassignmentBody(BaseModel):
    action: Literal["move", "assign"]
    student_id: str
    to_group: int
    allow_oversize: bool = False
    allow_low_overlap: bool = False
    # Server-enforced: groups are live, so the instructor must confirm
    # explicitly — a UI dialog alone would be bypassable by any API client.
    confirm: bool = False
```

In `_notify_reassignment`, replace the body-building block (the `slots = ...` line through `member_body = ...`) with:

```python
    slots = ", ".join(target["meeting_slots"])
    no_time = (" Your group does not yet have a shared meeting time —"
               " your instructor will help coordinate.")
    if summary["action"] == "move":
        moved_body = (f"Your instructor moved you to Group {target['group_id']}."
                      + (f" New meeting time: {slots}." if slots else no_time))
    else:
        moved_body = (f"You have been assigned to Group {target['group_id']}."
                      + (f" Meeting time: {slots}." if slots else no_time))
    member_body = ("Your group's membership was updated by your instructor."
                   " Check My Group for the current members and meeting time.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/web/ -q`
Expected: all PASS (including `test_notifications.py`, which imports `published`/`first_move` from this module — unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/reflectool_web/routers/cycles.py tests/web/test_reassignments.py
git commit -m "Live reassignments: allow_low_overlap + no-shared-time notification fallback (TDD)"
```

---

### Task 5: Frontend — extract `precheck.ts` with `needsLowOverlap` (+ vitest)

**Files:**
- Create: `web/src/features/reviewBoard/precheck.ts`
- Create: `web/src/features/reviewBoard/precheck.test.ts`
- Modify: `web/src/features/reviewBoard/ReviewBoard.tsx:22-62` (delete inline `Precheck`/`precheckMove`, import instead)
- Modify: `web/src/lib/api/review.ts:8-13` (EditRequest)

- [ ] **Step 1: Create `precheck.ts`**

```ts
/* Advisory drag prechecks for the review board; the server verdict is
 * authoritative. Below-min overlap is overridable (like oversize), so it
 * surfaces as needsLowOverlap rather than a hard block. */

import type { ReviewBoard as Board } from '../../lib/api/types/review'
import { mutualOverlap } from '../../lib/grid'

export interface Precheck {
  ok: boolean
  needsOversize: boolean
  needsLowOverlap: boolean
  /** Mutually free slots the group would share after the move. */
  overlap: number
  reason: string | null
}

const blocked = (reason: string): Precheck => ({
  ok: false,
  needsOversize: false,
  needsLowOverlap: false,
  overlap: 0,
  reason,
})

export function precheckMove(board: Board, studentId: string, toGroup: number): Precheck {
  const { config, students } = board
  const target = board.proposal.groups.find((g) => g.group_id === toGroup)
  if (!target) return blocked('no such group')
  if (target.members.includes(studentId)) return blocked('already in this group')

  const source = board.proposal.groups.find((g) => g.members.includes(studentId))
  if (source && source.members.length - 1 < config.min_size)
    return blocked(`Group ${source.group_id} would drop below ${config.min_size} members.`)

  const newMembers = [...target.members, studentId]
  if (newMembers.length > config.max_size + 1)
    return blocked(`Max is ${config.max_size} (+1 with override).`)

  const overlap = mutualOverlap(newMembers.map((sid) => students[sid].availability))
  return {
    ok: true,
    needsOversize: newMembers.length > config.max_size,
    needsLowOverlap: overlap < config.min_overlap,
    overlap,
    reason: null,
  }
}
```

- [ ] **Step 2: Write `precheck.test.ts`**

```ts
import { describe, expect, it } from 'vitest'
import { precheckMove } from './precheck'
import type { ReviewBoard as Board } from '../../lib/api/types/review'

/* Minimal board: two groups on disjoint availability blocks. */
function makeBoard(overrides: { members1?: string[]; members2?: string[] } = {}): Board {
  const students: Record<string, unknown> = {}
  const early = [true, true, false, false]
  const late = [false, false, true, true]
  const members1 = overrides.members1 ?? ['a1', 'a2', 'a3', 'a4']
  const members2 = overrides.members2 ?? ['b1', 'b2', 'b3', 'b4']
  for (const sid of members1)
    students[sid] = { name: sid, availability: early, free_slot_count: 2, gender: 'undisclosed', disability: 'undisclosed' }
  for (const sid of members2)
    students[sid] = { name: sid, availability: late, free_slot_count: 2, gender: 'undisclosed', disability: 'undisclosed' }
  return {
    config: { min_size: 3, max_size: 5, min_overlap: 1, grid: { days: 1, start: '08:00', end: '10:00', slot_minutes: 30 } },
    students,
    proposal: {
      status: 'proposed',
      groups: [
        { group_id: 1, members: members1, meeting_slots: [] },
        { group_id: 2, members: members2, meeting_slots: [] },
      ],
      unplaced: [],
      warnings: [],
    },
  } as unknown as Board
}

describe('precheckMove', () => {
  it('flags a zero-overlap move as needsLowOverlap instead of blocking', () => {
    const check = precheckMove(makeBoard(), 'a1', 2)
    expect(check.ok).toBe(true)
    expect(check.needsLowOverlap).toBe(true)
    expect(check.overlap).toBe(0)
    expect(check.needsOversize).toBe(false)
  })

  it('does not flag a move that keeps min_overlap', () => {
    // b9 is a late-block unplaced student joining the late-block group:
    // full overlap, no flags.
    const board = makeBoard({ members2: ['b1', 'b2', 'b3'] })
    board.students['b9'] = {
      name: 'b9', availability: [false, false, true, true], free_slot_count: 2,
      gender: 'undisclosed', disability: 'undisclosed',
    } as Board['students'][string]
    board.proposal.unplaced.push({ student_id: 'b9', reason: 'test' })
    const check = precheckMove(board, 'b9', 2)
    expect(check.ok).toBe(true)
    expect(check.needsLowOverlap).toBe(false)
    expect(check.overlap).toBe(2)
  })

  it('still blocks a drop onto the student\'s own group', () => {
    const check = precheckMove(makeBoard(), 'a1', 1)
    expect(check.ok).toBe(false)
    expect(check.reason).toBe('already in this group')
  })

  it('keeps hard blocks: source below min_size', () => {
    const check = precheckMove(makeBoard({ members1: ['a1', 'a2', 'a3'] }), 'a1', 2)
    expect(check.ok).toBe(false)
    expect(check.reason).toContain('below 3')
  })

  it('keeps hard blocks: beyond max_size + 1', () => {
    const check = precheckMove(
      makeBoard({ members2: ['b1', 'b2', 'b3', 'b4', 'b5', 'b6'] }),
      'a1',
      2,
    )
    expect(check.ok).toBe(false)
    expect(check.reason).toContain('Max is 5')
  })

  it('flags oversize and low overlap together', () => {
    const check = precheckMove(
      makeBoard({ members2: ['b1', 'b2', 'b3', 'b4', 'b5'] }),
      'a1',
      2,
    )
    expect(check.ok).toBe(true)
    expect(check.needsOversize).toBe(true)
    expect(check.needsLowOverlap).toBe(true)
  })
})
```

If the `board.students['b9'] = ... as Board['students'][string]` cast fights the actual `ReviewStudent` type, use `as unknown as Board['students'][string]` — the test only needs `availability`.

- [ ] **Step 3: Run the new tests (fail-first isn't meaningful here — the module is new — but they must pass)**

Run: `cd web && npx vitest run src/features/reviewBoard/precheck.test.ts`
Expected: all PASS.

- [ ] **Step 4: Point ReviewBoard at the module and extend EditRequest**

In `web/src/lib/api/review.ts`:

```ts
export interface EditRequest {
  action: 'move' | 'assign'
  student_id: string
  to_group: number
  allow_oversize?: boolean
  allow_low_overlap?: boolean
}
```

In `ReviewBoard.tsx`: delete the inline `Precheck` interface and `precheckMove` function (lines 22–62) and the now-unused `mutualOverlap` import (`perDayDensity` stays), and add:

```ts
import { precheckMove } from './precheck'
```

- [ ] **Step 5: Typecheck + full frontend tests, then commit**

Run: `cd web && npm run build && npm test`
Expected: build clean, all vitest suites PASS.

```bash
git add web/src/features/reviewBoard/precheck.ts web/src/features/reviewBoard/precheck.test.ts \
        web/src/features/reviewBoard/ReviewBoard.tsx web/src/lib/api/review.ts
git commit -m "Review board: extract precheck module, low overlap is overridable (vitest)"
```

---

### Task 6: Frontend — confirm dialogs send the override flags

**Files:**
- Modify: `web/src/features/reviewBoard/ReviewBoard.tsx` (state, onDragOver, onDragEnd, both modals)

- [ ] **Step 1: Generalize the pending-override state**

Replace

```ts
const [pendingOversize, setPendingOversize] = useState<EditRequest | null>(null)
const [pendingLive, setPendingLive] = useState<{
  req: EditRequest
  needsOversize: boolean
} | null>(null)
```

with

```ts
interface PendingOverride {
  req: EditRequest
  needsOversize: boolean
  needsLowOverlap: boolean
  overlap: number
}
const [pendingOverride, setPendingOverride] = useState<PendingOverride | null>(null)
const [pendingLive, setPendingLive] = useState<PendingOverride | null>(null)
```

(Declare `PendingOverride` at module level, next to the other top-level declarations.)

- [ ] **Step 2: Route drops through the overrides**

In `onDragOver`, warn (but don't block) on low overlap:

```ts
function onDragOver(e: DragOverEvent) {
  if (!e.over || !board) return
  const gid = Number(String(e.over.id).replace('group-', ''))
  const check = precheckMove(board, String(e.active.id), gid)
  const warning = check.needsLowOverlap
    ? `Fewer than ${board.config.min_overlap} shared slot(s) — you'll be asked to confirm.`
    : null
  setHoverBlocked({ [gid]: check.ok ? warning : check.reason })
}
```

In `onDragEnd`, replace the tail (from `if (live) {`) with:

```ts
    if (live) {
      // Published cycle: always confirm before a live change reaches students.
      setPendingLive({ req, ...check })
      return
    }
    if (check.needsOversize || check.needsLowOverlap) {
      setPendingOverride({ req, ...check })
      return
    }
    edit.mutate(req)
```

(`{ req, ...check }` carries `needsOversize`, `needsLowOverlap`, `overlap`; the extra `ok`/`reason` fields are harmless but if TypeScript complains about excess properties, spell the object out: `{ req, needsOversize: check.needsOversize, needsLowOverlap: check.needsLowOverlap, overlap: check.overlap }`.)

- [ ] **Step 3: Update the live modal**

After the existing `pendingLive?.needsOversize` paragraph, add:

```tsx
{pendingLive?.needsLowOverlap && (
  <p>
    ⚠ The group would share {pendingLive.overlap} mutually free slot(s) — below the
    minimum of {board.config.min_overlap}. The group may have no shared meeting time
    (explicit low-overlap override).
  </p>
)}
```

and send both flags on confirm:

```tsx
onClick={() => {
  if (pendingLive)
    reassign.mutate({
      ...pendingLive.req,
      allow_oversize: pendingLive.needsOversize,
      allow_low_overlap: pendingLive.needsLowOverlap,
    })
  setPendingLive(null)
}}
```

- [ ] **Step 4: Update the pre-publish override modal**

Replace the `pendingOversize` modal with:

```tsx
<Modal open={pendingOverride != null} title="⚠ Override constraint?">
  {pendingOverride?.needsOversize && (
    <p>
      This group will have{' '}
      <strong>
        {(board.proposal.groups.find((g) => g.group_id === pendingOverride.req.to_group)
          ?.members.length ?? 0) + 1}{' '}
        members
      </strong>{' '}
      (Max {board.config.max_size}).
    </p>
  )}
  {pendingOverride?.needsLowOverlap && (
    <p>
      <strong>
        {board.students[pendingOverride.req.student_id]?.name ||
          pendingOverride.req.student_id}
      </strong>
      's schedule shares {pendingOverride.overlap} mutually free slot(s) with this group —
      below the minimum of {board.config.min_overlap}. The group may have no shared
      meeting time.
    </p>
  )}
  <p>Have you confirmed this with the students?</p>
  <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
    <Button
      onClick={() => {
        if (pendingOverride)
          edit.mutate({
            ...pendingOverride.req,
            allow_oversize: pendingOverride.needsOversize,
            allow_low_overlap: pendingOverride.needsLowOverlap,
          })
        setPendingOverride(null)
      }}
    >
      Do it anyway
    </Button>
    <Button variant="ghost" onClick={() => setPendingOverride(null)}>
      Cancel
    </Button>
  </div>
</Modal>
```

(JSX apostrophe: write `'s schedule shares` as `&rsquo;s schedule shares` or wrap the sentence in a template string if the linter objects to the raw `'`.)

- [ ] **Step 5: Typecheck, test, commit**

Run: `cd web && npm run build && npm test`
Expected: build clean, tests PASS.

```bash
git add web/src/features/reviewBoard/ReviewBoard.tsx
git commit -m "Review board: low-overlap confirm dialogs send allow_low_overlap"
```

---

### Task 7: Full verification

- [ ] **Step 1: Full backend suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all PASS, no skips beyond the usual `importorskip` guards.

- [ ] **Step 2: Full frontend build + suite**

Run: `cd web && npm run build && npm test`
Expected: clean build, all PASS.

- [ ] **Step 3: End-to-end sanity (CLI lifecycle with the override)**

```bash
cd /Users/cyril/Documents/Reflectool && PYTHONPATH=src .venv/bin/python - <<'EOF'
import json, tempfile, pathlib
from reflectool.cli import main
d = pathlib.Path(tempfile.mkdtemp())
roster = {"config": {"grid": {"days": 1, "start": "08:00", "end": "10:00", "slot_minutes": 30}, "min_overlap": 2},
          "students": [{"id": f"s{i:02d}", "name": f"P{i}",
                        "availability": [1,1,0,0] if i <= 4 else [0,0,1,1],
                        "gender": "man", "disability": "none"} for i in range(1, 8)]}
(d / "roster.json").write_text(json.dumps(roster))
assert main(["match", "--roster", str(d/"roster.json"), "--state", str(d/"s.json")]) == 0
assert main(["edit", "--state", str(d/"s.json"), "--action", "move", "--student", "s01", "--to-group", "2"]) == 1
assert main(["edit", "--state", str(d/"s.json"), "--action", "move", "--student", "s01", "--to-group", "2", "--allow-low-overlap"]) == 0
print("override lifecycle OK")
EOF
```

Expected: prints the rejection JSON, then the edited proposal, then `override lifecycle OK`.

- [ ] **Step 4: Update the spec's out-of-scope note** (the shared `_override_suffix` helper now annotates `assign` too) and commit any doc delta.
