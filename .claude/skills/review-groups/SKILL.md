---
name: review-groups
description: Use when the instructor wants to inspect a proposed grouping, see group composition or homogeneity, move/swap/reassign students, resolve unplaced students, or judge whether groups are good before approving.
---

# Review Groups

Support the instructor's human-in-the-loop review. This is the **one authorized surface** for identity data: per-group aggregate composition, shown live to the instructor only.

## Steps

1. Show the review view:
   ```bash
   PYTHONPATH=src .venv/bin/python -m reflectool.cli composition --state state/session.json
   ```
   Relay per-group size, meeting slots, gender/disability composition (aggregate counts) and homogeneity scores, plus `unplaced` and `warnings`. This view is conversation-only: never write it to a file, never include any of it in anything student-facing, never carry composition facts forward into later non-review answers.
2. Apply manual edits through the CLI, one at a time:
   ```bash
   PYTHONPATH=src .venv/bin/python -m reflectool.cli edit --state state/session.json \
     --action move|assign --student <id> --to-group <n> [--allow-oversize]
   ```
   - `move`: relocate a grouped student. `assign`: place an unplaced student.
   - Every edit is re-validated against size 3–5 and `min_overlap`. If rejected, relay the exact violated constraint and stop — never retry with different students to "make it work" unless the instructor chooses that.
   - `--allow-oversize` (6th member) is an explicit instructor override: use it only when the instructor knowingly asks after you state that 5 is the designed ceiling; it is logged, and still requires the schedule overlap to hold.
3. For unplaced students, walk the spec's resolution ladder in order: (a) grow an existing compatible group (≤5), (b) form a new group of ≥3 from unplaced students, (c) leave for manual instructor decision — and say which rungs failed and why.
4. When the instructor is satisfied, hand off to the `publish-groups` skill. Do not approve on their behalf.

## Common mistakes

- Pasting composition data into notifications, files, or summaries that outlive the review — it exists only in this conversation, for this instructor.
- "Fixing" a rejected edit by silently trying alternatives the instructor didn't ask for.
- Treating a warning (e.g., unavoidable isolation) as resolved because the instructor didn't comment on it — confirm they saw it before approval.
- Editing groups by rewriting the JSON yourself instead of going through `cli edit` (which is what re-validates constraints).
