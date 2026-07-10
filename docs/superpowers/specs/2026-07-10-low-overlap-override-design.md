# Low-overlap override for instructor edits — design

**Date:** 2026-07-10
**Status:** approved (instructor confirmed: explicit override mirroring oversize; instructor warning + safe student note)

## Problem

When the instructor drags a student into a group whose members share fewer than
`min_overlap` free slots with that student, the move is hard-blocked everywhere:

- Frontend `precheckMove` returns `ok: false` ("X's schedule does not overlap…"),
  so the drop is refused outright.
- Backend `_validate_group` raises `InvalidEdit` with no override path.

The size constraint already has an escape hatch: `allow_oversize` lets the
instructor form a 6th-member group after an explicit ⚠ confirm dialog, with an
`[oversize override]` audit annotation. The overlap constraint has no
equivalent, even though the instructor may know an out-of-band time works
(e.g. the group agreed to meet asynchronously or off-grid).

## Decision

Add an `allow_low_overlap` override that mirrors `allow_oversize` end to end:

1. **Rejected by default.** `_validate_group` still raises `InvalidEdit` when
   the resulting group shares fewer than `min_overlap` slots; the message gains
   the same hint style: `(pass allow_low_overlap for an explicit instructor
   override)`.
2. **Explicit instructor confirmation.** The review board shows the same kind
   of ⚠ confirm dialog as the group-of-6 case before sending the flag — for
   both pre-publish edits and live (published) reassignments. Zero overlap is
   overridable too (no "some overlap required" floor).
3. **Audited.** Overridden edits append ` [low-overlap override]` to the audit
   entry (move and assign), parallel to ` [oversize override]`.
4. **No silent failure downstream (invariant 4).** A group with no shared
   slots gets `meeting_slots: []` (existing `_refresh_group` behavior; the
   board already renders "no shared slots"). Live-reassignment notification
   bodies gain a fallback: instead of "New meeting time: ." students see
   "Your group does not yet have a shared meeting time — your instructor will
   help coordinate." Bodies still pass `student_safe()`; no demographics are
   involved anywhere in this feature.

Constitution note: invariant 3 stays true — `cli edit` still re-validates
min_overlap and rejects by default; the override is an explicit, audited
instructor action, exactly like the pre-existing oversize override.

## Changes by layer

### Matcher core — `src/reflectool/review_workflow.py`
- `_validate_group(session, members, allow_oversize, allow_low_overlap)`:
  skip (don't remove) the overlap check when the flag is set; otherwise raise
  with the override hint appended.
- `_apply_edit_inner`: read `allow_low_overlap = bool(edit.get("allow_low_overlap"))`;
  pass it to the **target** validation for both `move` and `assign`. The source
  group stays strict (removing a member can only grow its shared-slot set).
- Audit suffix ` [low-overlap override]` on move/assign entries when the flag
  was set and the resulting target group is below `min_overlap`.

### CLI — `src/reflectool/cli.py`
- `edit` subcommand gains `--allow-low-overlap` (dest `allow_low_overlap`),
  passed through to the edit dict like `--allow-oversize`.

### Web API — `src/reflectool_web/routers/cycles.py`
- `EditBody` and `ReassignmentBody` gain `allow_low_overlap: bool = False`
  (flows through `model_dump()` automatically).
- `_notify_reassignment`: when the target group's `meeting_slots` is empty,
  use the no-shared-time fallback sentence in both the moved-student and
  group-member bodies instead of rendering an empty slot list.

### Frontend — `web/src/features/reviewBoard/`
- Extract `precheckMove` into `precheck.ts` (pure, unit-testable; ReviewBoard
  re-imports it). `Precheck` gains `needsLowOverlap: boolean`; below-min
  overlap no longer returns `ok: false` — it returns
  `ok: true, needsLowOverlap: true` with the shared-slot count available for
  dialog copy. Hard blocks that remain: unknown group, already-in-group,
  source dropping below `min_size`, size beyond `max_size + 1`.
- `EditRequest` (lib/api/review.ts) gains `allow_low_overlap?: boolean`.
- Board state: `pendingOversize: EditRequest | null` generalizes to
  `pendingOverride: { req, needsOversize, needsLowOverlap } | null`. The
  "⚠ Override constraint?" modal renders a paragraph per triggered override;
  the low-overlap one reads: "N's schedule shares fewer than min_overlap
  slot(s) with this group — the group may have no shared meeting time. Have
  you arranged a time with the students?" Confirm sends the matching flags.
- Live modal (`pendingLive`) gains the same low-overlap paragraph and sends
  `allow_low_overlap` alongside `allow_oversize`.
- Drag-over hover: a low-overlap target shows a warning hint rather than the
  blocked state.

## Testing

TDD throughout (project convention):
- `tests/test_review_workflow.py`: low-overlap move rejected without flag
  (message includes the hint); allowed with flag + audit suffix; assign to a
  no-overlap group with flag; zero-overlap group gets `meeting_slots: []`.
- `tests/web/test_edits.py`: 422 without flag, success with flag.
- `tests/web/test_reassignments.py`: live reassignment with
  `allow_low_overlap` + `confirm`; notification bodies use the fallback text
  (and still pass privacy checks) when the group has no shared slots.
- `web/src/features/reviewBoard/precheck.test.ts` (vitest): needsLowOverlap
  set below min (including zero overlap), remaining hard blocks intact,
  oversize+low-overlap combination.

## Out of scope

- ~~Adding the oversize audit suffix to `assign` entries~~ — implemented after
  all: the shared `_override_suffix` helper annotates both overrides on both
  `move` and `assign` (audit completeness, invariant 4).
- Any change to matcher scoring or publish-time notification payloads
  (`notify.py` returns structured slot lists, no prose to fix).
- Persisted `proposal["warnings"]` entries for overridden groups (the board
  and composition views already show the missing shared slots).
