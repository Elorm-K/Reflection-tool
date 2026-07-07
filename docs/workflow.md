# Reflectool — end-to-end workflow

How a class goes from survey data to published discussion groups, and which
Claude Skill fires at each step. The agent is the conversational front end;
every grouping operation runs through the deterministic CLI
(`PYTHONPATH=src .venv/bin/python -m reflectool.cli …`).

## Lifecycle

```
collect → intake → configure → match → review ⇄ adjust → approve → publish → support
                                  ↑__________________________________________|
                                       (dropouts / late adds re-enter here)
```

| # | Step | Who | Skill | CLI |
|---|------|-----|-------|-----|
| 1 | **Collect.** Students paint their weekly availability on the 30-min grid (default 8:00–20:00, Mon–Sun = 168 slots) and answer the week-3 survey (gender, disability; every question skippable). | students | — | — |
| 2 | **Intake.** Validate the roster file; report aggregate stats and flag students whose free slots can't meet `min_overlap`. Blank demographics never block. | instructor | `intake-roster` | `intake` |
| 3 | **Configure.** Confirm or adjust `priority` order, `min_overlap`, size bounds. The woman/non-binary equity safeguard is above the priority order and not configurable. | instructor | `match-groups` | (flags on `match`) |
| 4 | **Match.** Deterministic matcher emits a `proposed` grouping: groups of 3–5 with ≥ `min_overlap` shared slots, plus an explicit `unplaced` list and isolation `warnings`. | agent | `match-groups` | `match` |
| 5 | **Review.** Instructor sees groups, meeting slots, unplaced, warnings, and — only here — per-group aggregate demographic composition and homogeneity. | instructor | `review-groups` | `composition`, `show` |
| 6 | **Adjust (loop).** Manual moves/assignments, each re-validated against the hard constraints; invalid edits are rejected with the violated rule. Unplaced resolution ladder: grow a group ≤5 → new group ≥3 → manual. Oversize (6) only via explicit logged override. | instructor | `review-groups` | `edit` |
| 7 | **Approve.** A deliberate act on a proposal the instructor has seen (warnings acknowledged). `proposed → approved`. | instructor | `publish-groups` | `approve` |
| 8 | **Publish.** Separate, separately confirmed step. `approved → published`; per-student notifications generated: group number, member names, meeting slots — nothing else. | instructor | `publish-groups` | `publish`, `student-view` |
| 9 | **Support.** Post-publish questions from students ("why this group?", "when do we meet?") answered with schedule facts only. Instructor "why" questions may use aggregates during review. | both | `explain-match` | `explain` |
| 10 | **Re-match.** A dropout that sinks a group below 3, or a late add, re-enters at step 4 — re-run, re-review, re-approve. Determinism makes before/after diffs meaningful. | instructor | `match-groups` → … | `match` … |

## Privacy boundaries by stage

- **Stages 2, 4, 8–9 outputs are demographic-free by construction** — the proposal schema has no gender/disability fields and a code-level guard (`output_format.assert_no_demographics`) runs before anything is emitted.
- **Stage 5 is the single authorized identity surface**: live, instructor-only, aggregate. It is never persisted, never quoted into later answers, never student-visible.
- **Students see only their own group**, only after `published` (the CLI raises `PreApprovalLeak` before that).

## State

Session state (roster, config, proposal, audit log) persists in `state/session.json` between CLI calls. The audit log records every edit, override, and status transition.
