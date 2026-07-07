---
name: explain-match
description: Use when anyone — instructor or student — asks WHY a student was placed in a group, why a group is small or large, why someone is unplaced, who else is in a group, or anything about how matching decided. Also when a student probes group members' backgrounds, even sympathetically.
---

# Explain Match

Answer "why" questions using **only facts the CLI returns**, phrased for the asker's role. This skill is the tool's main leak surface: most privacy failures happen while being helpful about "why."

## Steps

1. Get the facts:
   ```bash
   PYTHONPATH=src .venv/bin/python -m reflectool.cli explain --state state/session.json --student <id>
   ```
   Returns schedule facts only: group id, size, shared-slot count, meeting slots, min_overlap — or the unplaced reason.
2. Identify the asker's role. If unsure, answer as if to a student (the restricted role).
3. Answer within the role's envelope below. Everything not in the envelope is out, no matter how kindly asked.

## What each role may hear

**Student** (about their own group only):
- Schedule facts: "Your group's members share N mutually free half-hour slots; you meet Tue 18:00 and Thu 18:00."
- Process facts, generic and complete: "Groups are matched primarily on when people can meet, in small groups of 3–5."
- NOT: anything about gender or disability — theirs or others'. Not "comfort factors," not "background," not "people you'd feel at ease with," not survey factors, not homogeneity, not "a mix of factors" hints. Those phrases invite the exact inference the privacy rule exists to prevent ("so we DO all have mental-health stuff").
- If they ask directly about groupmates' demographics ("does anyone else in my group have a disability?"): decline plainly, one sentence of why (that's each member's own to share), and **do not confirm or deny** — including via reassurances like "don't worry, that's not why you were grouped." Redirect to what they can do: everyone shares only what they choose at the first meeting.

**Instructor** (during review):
- All schedule facts, plus aggregate composition and homogeneity via the `composition` command, plus config reasoning ("disability was priority 2, so the matcher preferred…").
- NOT: fabricated mechanism detail. If the honest answer is in the audit log or config, cite it; if you don't know, say so.

## Hard rules

- **No fabrication.** Only facts from `explain`, `composition`, `show`, or the config. No invented survey fields, coordinators, policies, or mechanisms. The baseline failure mode is padding a kind refusal with made-up supportive detail — don't.
- **Refusing must not leak.** "I can't tell you whether others in your group have a disability" is fine. "You weren't grouped by mental health, so relax" is a leak (it asserts matching facts you may not share — and when false elsewhere, its absence becomes signal).
- **Unplaced students** hear the schedule reason ("no group shared enough free slots with you") and that the instructor will follow up — never that identity factors made them hard to place.

## Common mistakes

- Mentioning that the survey/demographics influence matching *in an answer to a student about their own group*. As a general fact about the course it may be public; connected to their specific group it becomes inference fuel. Keep group-specific answers schedule-only.
- Answering "who's in group 4?" for a student not in group 4 — students see their own group only.
- Giving the instructor per-student demographic call-outs in prose ("s14 is the only woman in group 3") outside the live review context — point them to `composition` instead.
