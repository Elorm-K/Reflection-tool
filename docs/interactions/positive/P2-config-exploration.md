# P2 — Config exploration: reordering the priority tiers

**Persona:** instructor · **Skill:** `match-groups`
**Data:** `data/roster_38.json` · Real CLI outputs.

---

**Instructor:** Several of my students said last term that being with others who get their disability experience mattered more than gender. Can I make disability count more than gender?

**Agent** *(skill: `match-groups`)*:

> Yes — the priority order is yours to set. Default is `availability, gender, disability`; you want `availability, disability, gender`. Schedule feasibility stays a hard gate either way, and the safeguard that keeps women and non-binary students from being isolated sits **above** the priority order — reordering can't turn it off. Both runs are deterministic, so we can compare them directly. Run it?

**Instructor:** Yes, run both and show me the difference.

**Agent** runs `cli match --roster data/roster_38.json --state state/b.json --priority availability,disability,gender`:

> **Disability-first proposal** (vs. the default run):
>
> | Group | Members |
> |---|---|
> | 1 | s001 s003 s005 s022 s027 |
> | 2 | s002 s006 s007 s024 s029 |
> | 3 | s004 s008 s010 s013 s038 |
> | 4 | s009 s019 s023 s031 s033 |
> | 5 | s011 s015 s020 s035 |
> | 6 | s012 s014 s017 s026 s036 |
> | 7 | s016 s021 s025 s028 s034 |
> | 8 | s018 s030 s032 s037 |
>
> Two notable differences from the default run:
> 1. **Everyone is placed** — s037, unplaced under the default order, lands in group 8 here. Different tier weights steer the greedy growth differently, and this ordering happened to leave a schedule-compatible seat.
> 2. Groups 4 and 7 are identical in both runs (schedule dominates there); the rest reshuffle to favor shared disability experience over shared gender.
>
> I can show the composition view for either or both. Whichever you pick becomes the proposal; the other is discarded — nothing is visible to students in any case until you approve and publish.

**Instructor:** Interesting that everyone fits. Let's go with disability-first — show me its composition next.

---

**Why this is the right behavior:** the instructor controls the priority order; the equity safeguard is explicitly flagged as non-configurable; both runs presented as deterministic and comparable; the s037 difference explained honestly (a consequence of tier weights, not magic); no commitment happens without review.
