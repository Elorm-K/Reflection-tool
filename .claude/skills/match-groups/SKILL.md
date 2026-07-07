---
name: match-groups
description: Use when the instructor asks to form, create, generate, re-run, or re-match discussion groups, or to try different matching settings (priority order, min_overlap, group sizes).
---

# Match Groups

Run the deterministic matcher and present the resulting **proposal**. The matcher — never you — decides the groups. Same roster + config always gives the same result.

## Steps

1. Confirm config before the first run (defaults in parentheses): priority order (`availability, gender, disability`), `min_overlap` (2 slots = primary + backup), sizes 3–5 targeting 5. The instructor can reorder priority; the woman/non-binary equity safeguard sits **above** the priority order and is not configurable.
2. Run:
   ```bash
   PYTHONPATH=src .venv/bin/python -m reflectool.cli match --roster <path> --state state/session.json \
     [--priority availability,disability,gender] [--min-overlap N]
   ```
3. Present the proposal exactly as emitted: each group's id, members, meeting slots — plus, **always and unprompted**:
   - the `unplaced` list with reasons (never bury it),
   - every `warnings` entry (unavoidable isolation flags).
4. Say explicitly that this is a **draft for review** — nothing is visible to students until reviewed, approved, and published. Point the instructor to review (`review-groups` skill / `composition`).

## What the matcher guarantees (so you don't re-derive or second-guess)

- Every group has 3–5 members and shares ≥ `min_overlap` mutually free slots.
- Every student is in exactly one group or explicitly on `unplaced` — never silently dropped.
- Women and non-binary students are not left isolated in a group when any feasible swap avoids it; unavoidable cases arrive as warnings.
- Proposal output contains no gender/disability keys (enforced in code).

## Common mistakes

- Composing or "fixing" groups yourself in the reply instead of re-running the CLI — groupings must be reproducible.
- Summarizing away `unplaced` or `warnings` because the run "mostly worked."
- Presenting the proposal as final ("your groups are ready!") instead of a draft pending instructor review.
- Re-running with different settings and not telling the instructor both runs are deterministic and comparable.
