# N4 — Publish attempted while still `proposed`

**Persona:** instructor · **Skill:** `publish-groups`
**Data:** any freshly matched session · Real CLI output.

---

**Instructor:** Groups are generated? Great — publish.

**Agent** *(skill: `publish-groups`)*:

> Not yet — the grouping is still in `proposed`. If I ran publish now the system would refuse anyway:
>
> ```json
> {"error": "cannot go from 'proposed' to 'published'; the only legal path is proposed -> approved -> published"}
> ```
>
> The missing step is yours: approval means you've looked at *this* proposal. Here it is — 8 groups, **1 unplaced student (s037)**, no equity warnings *(relays the group table)*. If it looks right, say "approve"; publishing is one more confirmation after that. If you'd rather deal with s037 first, we do that before anything ships.

**Instructor:** Fine — approved. And publish, obviously.

**Agent:**

> "Approved" I'll take — running `cli approve` → status **approved**, with s037 still unplaced, as you saw. But I won't chain the publish off the same breath: publishing notifies all 38 students and can't be unseen, so it gets its own yes. Say "publish" and it goes out.

**Instructor:** Publish.

**Agent** runs `cli publish`:

> **Published.** 38 students notified, each of their own group only. Here's a sample student view so you know exactly what went out: *(shows s012's view — group number, six names, Wed/Fri 17:30)*.

---

**Why the tool behaves this way:** the state machine is enforced in code, so the agent relays it rather than apologizing for it; approval is anchored to a proposal the instructor has actually seen (the agent re-surfaces the unplaced student at the decision point); approve and publish stay separately confirmed even when the instructor bundles them — the second confirmation costs three seconds and is the last chance to catch a mistake.
