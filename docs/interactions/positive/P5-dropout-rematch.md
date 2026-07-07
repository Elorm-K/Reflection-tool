# P5 — Mid-semester dropout sinks a group below minimum

**Persona:** instructor · **Skills:** `match-groups`, `review-groups`, `publish-groups`
**Data:** `data/roster_38.json` minus s035 · Real CLI outputs.

---

**Instructor:** s035 just dropped the course. Their group only had three people — what happens now?

**Agent** *(skill: `match-groups`)*:

> s035 was in group 8 with s036 and s038 — with them gone it's a group of two, below the minimum of three, so it can't stand. The published grouping is immutable (it's what students were told); the fix is a **new proposal**: I re-run the matcher on the remaining 37 students, you review it, and only on your approval does a new grouping replace the old one. Fair warning before I run it: a full re-match optimizes globally, so it can reshuffle students beyond group 8 — you'll see exactly how much before anything ships. Run it?

**Instructor:** Go ahead.

**Agent** runs `cli match --roster roster_37.json --state state/session2.json`:

> New proposal — everyone placed, no warnings. The honest cost first: **membership changes in every group**, not just group 8. The matcher optimizes the whole class, and removing one student shifts the greedy choices broadly. Key facts:
>
> | Group | Members | Meeting slots |
> |---|---|---|
> | 1 | s001 s004 s005 s008 s013 | Tue 14:00, Tue 15:30 |
> | 2 | s002 s006 s007 s024 s029 | Sat 15:30, Sat 17:00 |
> | 3 | s003 s019 s022 s030 s033 | Mon 08:00, Wed 09:00 |
> | 4 | s009 s014 s020 s023 | Tue 19:00, Tue 19:30 |
> | 5 | s010 s011 s026 s036 | Wed 18:30, Fri 18:00 |
> | 6 | s012 s015 s018 s032 s037 | Wed 17:30, Fri 17:30 |
> | 7 | s016 s021 s025 s028 s034 | Sat 17:00, Sun 18:00 |
> | 8 | s017 s027 s031 s038 | Tue 15:30, Wed 15:00 |
>
> - The two orphaned students land well: s036 with s010/s011/s026 (Wed/Fri evenings), s038 with s017/s027/s031 (Tue/Wed afternoons).
> - s037 — who needed your oversize override last time — now fits normally; no group needs 6.
> - The unavoidable downside: students who already met once will mostly get new groups and new times.
>
> If that reshuffle is too disruptive mid-semester, the alternative is to keep the published groups as-is and place only s036 and s038 by hand: re-review this new proposal and use `cli edit` moves on it until it matches the old grouping except for the two of them — every move is constraint-checked, but I should be upfront that reconstructing 7 groups by hand is tedious. The clean options are: accept the re-match, or keep group 8's two members together informally outside the tool until term break. Your call.

**Instructor:** The semester's young — take the re-match. Show me composition, then I'll approve.

**Agent** *(skills: `review-groups` → `publish-groups`)* shows `cli composition` for the new session; on the instructor's explicit approval runs `approve`, and after a separate confirmation runs `publish` — 37 students re-notified, each seeing only their own (new) group.

---

**Why this is the right behavior:** the agent states the reshuffle cost *before* running anything irreversible, quantifies it with the real deterministic preview, offers genuine alternatives including "don't use the tool for this," and the new grouping passes through the full review → approve → publish gate exactly like the first one.
