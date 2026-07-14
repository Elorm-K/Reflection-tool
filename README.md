# Reflectool

Reflectool sorts a class roster into small weekly reflection groups of 3–5 members, based on the preference or group-matching method the instructor chooses and the details the students/participants provide.

## What it does

Weekly reflection groups work best when the members can reliably meet *and* share
enough background that people feel safe being honest. Doing that by hand for a
whole class is fiddly and easy to get subtly unfair. Reflectool does it with a
**deterministic algorithm** — a plain Python program the team wrote, not AI and
not a black box. Give it the same roster and settings and it always produces the
same groups.

It groups students so that everyone in a group shares enough free time to meet,
and it tends to place people with others who share their background (gender,
disability experience) — while making sure no woman, non-binary, or disabled
student is left as the lone one of their kind in a group. An instructor always
reviews and approves the groups before students see anything, and students are
only ever told their own group's members and meeting times — never anyone's
personal details.

For how the matching actually works — the priority order, the constraints, the
data formats, and the module layout — see **[docs/SPEC.md](docs/SPEC.md)**.

## Quickstart

Requires Python 3.11+. The core has no third-party dependencies; `pytest` is only
needed to run the tests.

```bash
# set up a virtualenv and install the test runner
python3 -m venv .venv && .venv/bin/pip install pytest

# run the core test suite (104 tests)
.venv/bin/python -m pytest tests/ -q --ignore=tests/web

# make a proposal from the bundled 6-student example
PYTHONPATH=src .venv/bin/python -m reflectool.cli match \
  --roster data/demo_roster_6.json --state state/session.json

# instructor-only: see per-group composition before approving
PYTHONPATH=src .venv/bin/python -m reflectool.cli composition --state state/session.json

# approve, then publish (two deliberate steps), then a student's own view
PYTHONPATH=src .venv/bin/python -m reflectool.cli approve --state state/session.json
PYTHONPATH=src .venv/bin/python -m reflectool.cli publish --state state/session.json
PYTHONPATH=src .venv/bin/python -m reflectool.cli student-view --state state/session.json --student s01
```

Need a bigger roster to play with? `data/roster_38.json` and `data/roster_120.json`
are included, or generate one:

```bash
.venv/bin/python data/generate_roster.py --n 60 --seed 1 --out data/roster_60.json
```

## Input

A JSON file with a `students` array and an optional `config`. Each student has an
`id`, an `availability` bit-vector (one entry per time slot — the default grid is
7 days × 24 half-hour slots from 08:00–20:00 = 168 slots), an optional `gender`
and `disability`, and an optional `name`:

```json
{
  "students": [
    {"id": "s01", "name": "Ada P.", "availability": [1, 1, 0, 0],
     "gender": "woman", "disability": "adhd"}
  ]
}
```

Demographics are optional — a blank is treated as "prefer not to say" and never
counts against a student. See [docs/SPEC.md](docs/SPEC.md#data) for the full field
list and config options.

## Output

The `match` command prints a **proposal**: numbered groups with their member ids
and meeting-time slots, plus an `unplaced` list (anyone who couldn't be placed,
with the reason) and any equity `warnings`. It never contains demographic data.
After the instructor approves and publishes, each student can see only their own
group — group number, member names, and meeting slots.

## Lifecycle

```
match  →  composition / edit  →  approve  →  publish  →  student-view
```

Nothing reaches students until the instructor explicitly approves and then
publishes — two separate steps, in that order.

---

*The `src/reflectool/` matcher and CLI are the whole story here. The repo also
contains a FastAPI + React web pilot (`src/reflectool_web/`, `web/`), which this
README does not cover.*
