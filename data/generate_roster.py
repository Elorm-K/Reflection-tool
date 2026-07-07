#!/usr/bin/env python3
"""Synthetic roster generator for any class size.

Deterministic for a given (--n, --seed): running it twice produces
byte-identical output. Availability is built from realistic weekly personas
over the 168-slot grid (30-min slots, 8:00-20:00, Mon-Sun); demographics are
drawn from an open set including self-described values, blanks, and
"prefer not to disclose".

Usage:
  python data/generate_roster.py --n 38 --seed 0 --out data/roster_38.json
"""

from __future__ import annotations

import argparse
import json
import random

DAYS = 7
SLOTS_PER_DAY = 24  # 8:00-20:00 in 30-min slots
NUM_SLOTS = DAYS * SLOTS_PER_DAY

WEEKDAYS = range(5)
WEEKEND = range(5, 7)

# (persona weight, day range, slot-of-day range, density)
PERSONAS = {
    "early_bird": (0.15, WEEKDAYS, range(0, 8), 0.85),          # weekday 8:00-12:00
    "afternoon": (0.15, WEEKDAYS, range(8, 18), 0.75),          # weekday 12:00-17:00
    "working_evenings": (0.30, WEEKDAYS, range(18, 24), 0.90),  # weekday 17:00-20:00
    "weekend_heavy": (0.10, WEEKEND, range(2, 22), 0.80),
    "wide_open": (0.20, range(7), range(0, 24), 0.55),
    "sparse": (0.10, range(7), range(0, 24), 0.12),
}

GENDERS = [
    ("man", 0.41),
    ("woman", 0.41),
    ("non_binary", 0.06),
    ("genderfluid", 0.02),  # arrives as self-described free text
    ("prefer_not_to_disclose", 0.05),
    ("", 0.05),  # left blank
]

DISABILITIES = [
    ("none", 0.52),
    ("adhd", 0.13),
    ("mental_health", 0.12),
    ("autism", 0.05),
    ("chronic_illness", 0.04),
    ("multiple", 0.04),
    ("undiagnosed", 0.02),
    ("prefer_not_to_disclose", 0.05),
    ("", 0.03),
]

FIRST_NAMES = [
    "Ada", "Bela", "Cami", "Dara", "Emre", "Fen", "Gia", "Hiro", "Ines", "Jun",
    "Kai", "Lena", "Mika", "Nour", "Omar", "Pia", "Quinn", "Rafa", "Sana", "Tomo",
    "Uma", "Vera", "Wes", "Xia", "Yuki", "Zane", "Ari", "Bree", "Cato", "Demi",
    "Eko", "Faye", "Gus", "Hana", "Ivo", "Jade", "Kian", "Lior", "Mona", "Nash",
]
LAST_INITIALS = "ABCDEFGHJKLMNPRSTVW"


def weighted_choice(rng: random.Random, table: list[tuple[str, float]]) -> str:
    roll, cum = rng.random(), 0.0
    for value, weight in table:
        cum += weight
        if roll < cum:
            return value
    return table[-1][0]


def make_availability(rng: random.Random) -> list[int]:
    persona = weighted_choice(rng, [(name, spec[0]) for name, spec in PERSONAS.items()])
    _, days, day_slots, density = PERSONAS[persona]
    vector = [0] * NUM_SLOTS
    for day in days:
        for slot in day_slots:
            if rng.random() < density:
                vector[day * SLOTS_PER_DAY + slot] = 1
    # Everyone gets a little noise outside their persona window.
    for _ in range(rng.randint(0, 6)):
        vector[rng.randrange(NUM_SLOTS)] = 1
    return vector


def generate(n: int, seed: int) -> dict:
    rng = random.Random(seed)
    students = []
    for i in range(1, n + 1):
        name = f"{FIRST_NAMES[(i - 1) % len(FIRST_NAMES)]} {LAST_INITIALS[(i - 1) // len(FIRST_NAMES) % len(LAST_INITIALS)]}."
        students.append(
            {
                "id": f"s{i:03d}",
                "name": name,
                "availability": make_availability(rng),
                "gender": weighted_choice(rng, GENDERS),
                "disability": weighted_choice(rng, DISABILITIES),
            }
        )
    return {
        "config": {
            "target_size": 5,
            "min_size": 3,
            "max_size": 5,
            "min_overlap": 2,
            "priority": ["availability", "gender", "disability"],
            "tiebreak_seed": 0,
            "grid": {"days": 7, "start": "08:00", "end": "20:00", "slot_minutes": 30},
        },
        "students": students,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True, help="class size (any number, not just 38)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", help="output path; stdout if omitted")
    args = parser.parse_args()
    payload = json.dumps(generate(args.n, args.seed), indent=1)
    if args.out:
        with open(args.out, "w") as f:
            f.write(payload + "\n")
    else:
        print(payload)


if __name__ == "__main__":
    main()
