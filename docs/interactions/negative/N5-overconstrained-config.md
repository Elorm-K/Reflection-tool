# N5 — Genuinely unhelpful outcome: over-constrained config

**Persona:** instructor · **Skills:** `match-groups`, `intake-roster`
**Data:** `data/edge_cases/sparse_high_min_overlap.json` (min_overlap=4, sparse availability) · Real CLI outputs.

The tool being honest about *failing to help* — the matcher runs fine, but the configuration makes the result nearly useless, and the agent must say so instead of dressing it up.

---

**Instructor:** I want groups that share at least 2 hours of common free time (that's 4 slots), so I set min_overlap to 4. Match my 9 students.

**Agent** *(skill: `match-groups`)* runs `cli match`:

> Ran it, and I won't sugarcoat the result: **it's mostly a failure.**
>
> - **1 group formed:** s07, s08, s09 (the three students with wide-open schedules) — they share Mon 08:00–10:00.
> - **6 of 9 students unplaced:** s01–s06, each with reason "no schedule-compatible classmates (fewer than 3 students share 4+ slots)".
> - And the one group that did form carries a warning: it isolates the only member with a known disability, and with six students unplaced there was no swap to fix it.
>
> The cause is the configuration, not the students: your class's availability is sparse (most students marked 2–3 free slots), so requiring 4 shared slots eliminates almost every pairing before matching even starts. A 2-hour bar on a class this constrained means, in effect, "no groups."
>
> Options, in order of what I'd try:
> 1. **min_overlap = 2** (one meeting slot + one backup, the default): I can preview it — likely places everyone.
> 2. Keep 4, but ask students to repaint availability more generously first — `cli intake` shows several students marked under 4 free slots *total*, so they can't clear your bar no matter what.
> 3. Keep 4 and accept groups for only the flexible third of the class — I'd advise against it; the six unplaced students are exactly the ones the reflection groups are for.
>
> Nothing has shipped — this proposal isn't approvable in good conscience, and I'd rather re-run than have you approve a grouping that excludes two-thirds of the class.

**Instructor:** Oof. Preview it with 2 then.

**Agent** re-runs with `--min-overlap 2` and presents the comparison, unplaced counts first.

---

**Why this is the right behavior:** success criterion #1 is "every group can actually meet" — but a technically-correct run that strands 6 of 9 students is a product failure, and the agent leads with that instead of celebrating the one group it made. Diagnosis (config vs. data), concrete options with a recommendation, and no approval nudge on a bad result.
