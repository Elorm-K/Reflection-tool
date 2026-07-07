# Reflectool

A prototype AI agent that sorts students in a class into small weekly discussion groups of 3–5, based on when they're free to meet and who they'd feel comfortable opening up around. It groups students with others who share their background (gender, disability experience) because people reflect more honestly where they don't feel like the odd one out — and it especially avoids leaving any one woman, non-binary, or disabled student alone in a group of people unlike them. The instructor always reviews and approves groups before students see them; students are told only who's in their group and when to meet — never anyone's personal details.

The agent is a set of **Claude Skills** in front of a **deterministic, stdlib-only Python matcher**: the model narrates and gates, the code decides and enforces.

## Layout

| Path | What |
|---|---|
| `CLAUDE.md` | Agent constitution: privacy invariants, approval gate, role rules |
| `.claude/skills/` | Five skills: `intake-roster`, `match-groups`, `review-groups`, `publish-groups`, `explain-match` |
| `src/reflectool/` | Matcher core, review state machine, notifications, CLI |
| `data/` | Roster generator (any class size) + fixtures: demo (6), test (38), scale (120), edge cases |
| `docs/workflow.md` | End-to-end lifecycle and which skill fires where |
| `docs/skills-plan.md` | Skill design rationale + adversarial test evidence |
| `docs/interactions/` | Annotated transcripts: P1–P5 (beneficial), N1–N6 (misuse & failure modes) |
| `tests/` | 94 pytest tests: constraints, privacy, determinism, state machine, edge cases |

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest tests/ -q                     # run the suite
.venv/bin/python data/generate_roster.py --n 60 --seed 1 --out data/roster_60.json
PYTHONPATH=src .venv/bin/python -m reflectool.cli match --roster data/roster_38.json --state state/session.json
PYTHONPATH=src .venv/bin/python -m reflectool.cli composition --state state/session.json
```

Lifecycle: `match` → (`composition`, `edit`) → `approve` → `publish` → `student-view`.

## Guarantees

- Every group has 3–5 members sharing ≥ `min_overlap` mutually free slots; no student is ever silently dropped.
- Women and non-binary students are never isolated when a feasible alternative exists; unavoidable cases arrive as explicit warnings.
- No output a student can see — and no persisted artifact — contains gender or disability data (enforced in code, asserted in tests).
- Same input → same groups. All tie-breaks are deterministic; there is no randomness in the matcher.

Based on the draft spec "Reflection-Group Matching Function — Technical Specification".
