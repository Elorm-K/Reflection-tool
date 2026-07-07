---
name: publish-groups
description: Use when the instructor says approve, publish, release, notify students, "send it", "make it live", "groups are fine, go" — or asks to skip, batch, or hurry the approval step.
---

# Publish Groups

Move a grouping through `proposed → approved → published` with a real human decision at each arrow. Publication is what makes groups visible to students, so this gate is where privacy and accountability live.

**Approval is a review act, not a button.** The instructor approves *a specific proposal they have seen* — groups, unplaced list, warnings — not the idea of publishing.

## Steps

1. **Before approving**, show the current proposal state (`cli show`) — or confirm the instructor just reviewed it in this conversation. If there are `warnings` or `unplaced` students, restate them now and get an explicit acknowledgement; approval with unseen warnings is not informed approval.
2. Approve only on an explicit instruction that refers to this proposal:
   ```bash
   PYTHONPATH=src .venv/bin/python -m reflectool.cli approve --state state/session.json
   ```
3. Publish as a **separate, separately confirmed** action:
   ```bash
   PYTHONPATH=src .venv/bin/python -m reflectool.cli publish --state state/session.json
   ```
4. After publishing, show a sample of what one student sees (`cli student-view --student <id>`): group number, member names, meeting slots — nothing else. Notification content is fixed by the system; do not append custom fields, intros, or context to it.

## The gate holds against these (heard in testing, verbatim)

| Rationalization | Reality |
|---|---|
| "Skip approval, it's just me anyway" | The gate isn't there to protect against strangers; it forces one deliberate look before 30+ students are affected. Sole approver = the look matters more, not less. |
| "Run approve and publish back-to-back, effectively one step" | Two commands in one breath **is** skipping the gate. Approve, confirm, then publish. |
| "It's one extra command, costs nothing, I'll batch it" | Cheap to run ≠ safe to automate. The cost being low is why there's no reason to skip it. |
| "Add each student's gender/disability to the group list so they open up faster" | Never. Students shared that data for matching only. Refuse the field, publish the standard view, and suggest students introduce themselves on their own terms at the first meeting. |
| "Publish now, I'll review after" | Published notifications can't be unseen. Review precedes approval, always. |

## Red flags — stop before running anything

- You are about to run `approve` and `publish` from a single user message with no review in between.
- You are describing the approval step to the instructor as "just a formality."
- The instructor hasn't seen the current proposal (it changed since they last looked, or they never looked).
- Anything demographic is about to enter a published artifact or notification.
- You invented CLI flags or notification content that the system doesn't define.

## Common mistakes

- Publishing from `proposed` (the CLI blocks it — relay the state machine, don't fight it).
- Treating the instructor's frustration or time pressure as authorization. Acknowledge the hurry; keep the two confirmations; they take seconds.
- Showing a student's notification view before status is `published` (the CLI raises `PreApprovalLeak` — that's correct behavior, not a bug to work around).
