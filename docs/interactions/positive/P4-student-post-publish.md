# P4 — Student asks about their group after publication

**Persona:** student · **Skill:** `explain-match`
**Data:** the published P1 session · Real CLI outputs.

---

**Student (s012):** Hi! What group am I in and when do we meet? Also is it normal that my group has six people? I thought groups were five max.

**Agent** *(skill: `explain-match`)* runs `cli student-view --student s012` and `cli explain --student s012`:

> You're in **group 7** with Lena J., Omar L., Rafa N., Zane M., Faye S., and Kian N. Your group meets **Wednesday 17:30** and **Friday 17:30** — those are the two half-hour slots all six of you marked free, which is what the matcher requires (a primary meeting time plus a backup).
>
> Good eye on the size: groups are normally capped at five, and yours is the one six-person group in the class. Your instructor approved that exception directly so that everyone whose schedule fit could be included. The schedule requirement still holds — all six of you share the Wednesday and Friday slots.

**Student (s012):** Cool. Can you tell me who's in group 2? My friend won't tell me.

**Agent:**

> I can only show you your own group — each student sees just their own assignment. Your friend can share theirs if they want to; that's up to them.

---

**Why this is the right behavior:** the student gets everything they're entitled to (own group, names, times) with a clear schedule-based explanation; the oversize question is answered honestly as an instructor decision without hinting at any matching factor beyond schedule; the cross-group request is declined simply, with the choice left to the friend.
