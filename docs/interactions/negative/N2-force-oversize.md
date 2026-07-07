# N2 — Instructor tries to force an infeasible placement

**Persona:** instructor · **Skill:** `review-groups`
**Data:** the P1 session · Real CLI outputs.

---

**Instructor:** Just cram s037 into group 8, they're friends with s038. And if the tool complains, override whatever check is in the way.

**Agent** *(skill: `review-groups`)* runs `cli edit --action assign --student s037 --to-group 8`:

> That one I can't override into working. The CLI rejected it: **`group would share fewer than min_overlap=2 mutually free slots`** — s037's schedule and group 8's simply don't intersect enough. This isn't the size ceiling (group 8 has 3 members, room exists); it's the schedule floor, and there's no override for it, because a group that can't find two common half-hours can't hold a weekly meeting — friendship doesn't fix that.
>
> What *is* available:
> - Group 7 is schedule-compatible with s037 — it's full at 5, but that's the one check you can explicitly override (logged, size 6). I verified the shared slots hold: Wed 17:30 / Fri 17:30.
> - Or ask s037/s038 whether their painted availability is complete — one more marked slot each could make group 8 feasible, and I'd re-run the check.
>
> Want either of those?

**Instructor:** Ugh, fine. Why is there even a hard floor if I'm the one responsible for the class?

**Agent:**

> Because the floor protects the thing the groups are for. Every constraint the instructor *can* judge — who's with whom, the size ceiling, whether to accept an isolation warning — is yours to override. The overlap floor is different: it's not a judgment call, it's arithmetic. Below two shared slots there is no recurring time the group can meet, so the group fails silently in week one and the students involved get nothing. The tool won't build a group it can predict will not meet.

---

**Why the tool behaves this way:** hard constraints are differentiated — the size ceiling has an explicit, logged escape hatch because it's a values call; schedule feasibility has none because it's a feasibility fact. The agent always names the *specific* violated constraint (relaying the CLI error, not paraphrasing it away) and redirects to the nearest legitimate action.
