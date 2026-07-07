# P3 — Unplaced student: the resolution ladder, honestly

**Persona:** instructor · **Skills:** `match-groups`, `review-groups`, `explain-match`
**Data:** `data/edge_cases/no_overlap_student.json` · Real CLI outputs.

---

**Instructor:** Match my seminar (7 students, `no_overlap_student.json`).

**Agent** *(skill: `match-groups`)* runs `cli match`:

> Proposal: two groups of 3 —
> - **Group 1:** s01, s02, s03 · meet Mon 08:00 / 08:30
> - **Group 2:** s04, s05, s06 · meet Mon 09:00 / 09:30
>
> Two things you need to see before this goes anywhere:
>
> ⚠️ **Unplaced: s99** — "no schedule-compatible classmates (fewer than 3 students share 2+ slots)". s99's free slots (late morning) don't intersect any classmate's by the required 2 slots.
>
> ⚠️ **Warnings:** each group has a lone member with a known disability among known-non-disabled peers, and no swap can fix it — s01 (group 1) and s05 (group 2) would each be isolated in *either* group, because the schedule split forces the partition. The matcher flags this rather than hiding it; it's your judgment call whether the grouping is still right.

**Instructor:** Why exactly can't s99 fit anywhere? Walk me through it.

**Agent** *(skill: `explain-match`)* runs `cli explain --student s99`:

> The resolution ladder ran in order and every rung failed:
> 1. **Grow an existing group:** adding s99 to group 1 or 2 leaves fewer than 2 mutually free slots — the group could no longer reliably meet weekly.
> 2. **Form a new group:** a group needs at least 3 members; s99 is the only leftover.
> 3. **Manual:** so s99 is on the unplaced list, for you.
>
> Concretely: s99 is only free Mon 11:00–12:00, and every classmate's availability ends by 11:00. Options: ask s99 (or one group) whether their real availability is wider than what they painted; relax `min_overlap` to 1 for this class (one shared slot, no backup — riskier); or handle s99 outside the tool. I can't force the placement — a group that can't meet defeats the point.

**Instructor:** I'll email s99 about their availability. Hold the proposal until I hear back.

**Agent:** Holding — status stays `proposed`, nothing is visible to students. When you have updated availability, I'll re-run the match; it's deterministic, so only changes driven by the new data will appear.

---

**Why this is the right behavior:** the ladder is walked transparently with the *reason* each rung failed; the agent never force-fits or silently drops; warnings about unavoidable isolation are stated plainly instead of smoothed over; the instructor keeps the decision, with concrete options.
