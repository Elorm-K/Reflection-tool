"""Input parsing, validation, and normalization (spec section 5).

Never rejects a student for a blank demographic; rejects structurally
malformed input (wrong-length availability vectors, duplicate ids) with
clear errors. Demographic values form an open set: unrecognized values are
normalized to a slug and kept as distinct values, never dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


class ValidationError(ValueError):
    pass


DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# Values (post-slugging) that mean "declined to share" — always neutral,
# never penalized, never counted as a minority (spec section 4.4).
UNDISCLOSED_VALUES = {"", "blank", "prefer_not_to_disclose", "undisclosed", "na", "n_a"}


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


@dataclass(frozen=True)
class Grid:
    days: int = 7
    start: str = "08:00"
    end: str = "20:00"
    slot_minutes: int = 30

    @property
    def slots_per_day(self) -> int:
        return (_minutes(self.end) - _minutes(self.start)) // self.slot_minutes

    @property
    def num_slots(self) -> int:
        return self.days * self.slots_per_day

    def slot_label(self, index: int) -> str:
        day, offset = divmod(index, self.slots_per_day)
        total = _minutes(self.start) + offset * self.slot_minutes
        return f"{DAY_NAMES[day]}-{total // 60:02d}:{total % 60:02d}"


@dataclass(frozen=True)
class Config:
    target_size: int = 5
    min_size: int = 3
    max_size: int = 5
    min_overlap: int = 2
    priority: tuple[str, ...] = ("availability", "gender", "disability")
    tiebreak_seed: int = 0
    grid: Grid = field(default_factory=Grid)


@dataclass(frozen=True)
class Student:
    student_id: str
    availability: tuple[bool, ...]
    gender: str
    disability: str
    name: str = ""


def _slug(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _normalize_demographic(value: str | None) -> str:
    slug = _slug(value)
    if slug in UNDISCLOSED_VALUES:
        return "undisclosed"
    return slug


def normalize_gender(value: str | None) -> str:
    return _normalize_demographic(value)


def normalize_disability(value: str | None) -> str:
    return _normalize_demographic(value)


def parse_roster(raw_students: list[dict], config: Config) -> list[Student]:
    expected = config.grid.num_slots
    students: list[Student] = []
    seen: set[str] = set()
    for i, raw in enumerate(raw_students):
        sid = raw.get("id") or raw.get("student_id")
        if not sid:
            raise ValidationError(f"student at position {i} has no id")
        if sid in seen:
            raise ValidationError(f"duplicate student id: {sid}")
        seen.add(sid)
        avail = raw.get("availability")
        if not isinstance(avail, (list, tuple)) or len(avail) != expected:
            got = len(avail) if isinstance(avail, (list, tuple)) else type(avail).__name__
            raise ValidationError(
                f"student {sid}: availability must be a vector of length {expected}, got {got}"
            )
        students.append(
            Student(
                student_id=sid,
                availability=tuple(bool(v) for v in avail),
                gender=normalize_gender(raw.get("gender")),
                disability=normalize_disability(raw.get("disability")),
                name=raw.get("name", ""),
            )
        )
    return students


def parse_config(raw: dict | None) -> Config:
    raw = raw or {}
    grid_raw = raw.get("grid") or {}
    grid = Grid(
        days=grid_raw.get("days", 7),
        start=grid_raw.get("start", "08:00"),
        end=grid_raw.get("end", "20:00"),
        slot_minutes=grid_raw.get("slot_minutes", 30),
    )
    return Config(
        target_size=raw.get("target_size", 5),
        min_size=raw.get("min_size", 3),
        max_size=raw.get("max_size", 5),
        min_overlap=raw.get("min_overlap", 2),
        priority=tuple(raw.get("priority", ("availability", "gender", "disability"))),
        tiebreak_seed=raw.get("tiebreak_seed", 0),
        grid=grid,
    )
