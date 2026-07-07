"""Scoring terms for the matcher (spec sections 4.2-4.4).

group_score returns a lexicographic tuple:
  1. equity safeguard (above every config.priority tier, not reorderable)
  2..n. one tier per config.priority entry
  n+1. lone-minority (disability) penalty
  n+2. size preference

Undisclosed values are neutral everywhere: excluded from homogeneity,
never counted as a minority (spec section 4.4).
"""

from __future__ import annotations

from collections import Counter

from .io_parse import Config, Student

# Genders the equity safeguard protects from isolation (spec section 4.4).
PROTECTED_GENDERS = {"woman", "non_binary"}

# Slots beyond min_overlap + buffer add nothing: availability rewards
# comfortably clearing the floor, not maximizing shared time (spec 4.2).
OVERLAP_BUFFER = 1


def group_overlap_slots(group: list[Student]) -> tuple[int, ...]:
    if not group:
        return ()
    shared = [all(s.availability[i] for s in group) for i in range(len(group[0].availability))]
    return tuple(i for i, free in enumerate(shared) if free)


def homogeneity(group: list[Student], attr: str) -> float | None:
    values = [getattr(s, attr) for s in group]
    known = [v for v in values if v != "undisclosed"]
    if not known:
        return None
    return Counter(known).most_common(1)[0][1] / len(known)


def equity_isolation_count(group: list[Student]) -> int:
    """1 if the group isolates a lone woman-or-non-binary member, else 0.

    Women and non-binary students protect each other: two protected members
    of any protected gender means no isolation. Undisclosed members are never
    counted as isolated by a value they declined to share.
    """
    protected = [s for s in group if s.gender in PROTECTED_GENDERS]
    others = [s for s in group if s.gender not in PROTECTED_GENDERS]
    return 1 if len(protected) == 1 and others else 0


def lone_minority_count(group: list[Student]) -> int:
    """1 if exactly one member has a known disability among known-'none' peers.

    Gender isolation is handled by the higher-weighted equity term; this term
    covers the "one disabled student among non-disabled peers" harm. Disabled
    members protect each other regardless of which disability they named.
    """
    disabled = [s for s in group if s.disability not in ("none", "undisclosed")]
    nones = [s for s in group if s.disability == "none"]
    return 1 if len(disabled) == 1 and nones else 0


def _availability_tier(group: list[Student], config: Config) -> float:
    return min(len(group_overlap_slots(group)), config.min_overlap + OVERLAP_BUFFER)


def group_score(group: list[Student], config: Config) -> tuple:
    tiers = []
    for factor in config.priority:
        if factor == "availability":
            tiers.append(_availability_tier(group, config))
        else:
            h = homogeneity(group, factor)
            tiers.append(1.0 if h is None else h)  # all-undisclosed is neutral, never penalized
    return (
        -equity_isolation_count(group),
        *tiers,
        -lone_minority_count(group),
        -abs(len(group) - config.target_size),
    )
