"""The matcher core (spec section 4.2).

Pure function match(students, config) -> MatchResult. No I/O, no global
state, no randomness: all iteration is ordered by student_id, so the same
input always yields the same output (spec section 5, determinism).

Algorithm: schedule-decompose the roster into pairwise-compatible
components, plan a size mix per component (fewest groups, no 3s when a
4s-and-5s mix exists, then most 5s), greedy seed-and-grow with the full
lexicographic group_score (equity safeguard on top), then a bounded swap
repair pass, then remainder resolution (grow / new group / unplaced).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .io_parse import Config, Student
from .objective import (
    equity_isolation_count,
    group_overlap_slots,
    group_score,
    lone_minority_count,
)

REPAIR_SWEEPS = 2


@dataclass
class MatchResult:
    groups: list[list[Student]] = field(default_factory=list)
    meeting_slots: list[tuple[int, ...]] = field(default_factory=list)
    unplaced: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def plan_group_sizes(n: int, config: Config) -> list[int]:
    """Fewest groups within [min_size, max_size]; among those, fewest 3s,
    then most 5s (spec section 4.4, uneven counts)."""
    if n < config.min_size:
        return []
    k = -(-n // config.max_size)  # ceil
    while True:
        best = None
        for fives in range(k, -1, -1):
            for fours in range(k - fives, -1, -1):
                threes = k - fives - fours
                if 5 * fives + 4 * fours + 3 * threes == n:
                    candidate = (threes, -fives)
                    if best is None or candidate < best[0]:
                        best = (candidate, [5] * fives + [4] * fours + [3] * threes)
        if best:
            return best[1]
        k += 1


def _pairwise_compatible(a: Student, b: Student, config: Config) -> bool:
    shared = sum(1 for x, y in zip(a.availability, b.availability) if x and y)
    return shared >= config.min_overlap


def _components(students: list[Student], config: Config) -> list[list[Student]]:
    """Connected components of the pairwise-compatibility graph, each sorted
    by student_id; components ordered by their smallest member id."""
    remaining = sorted(students, key=lambda s: s.student_id)
    comps: list[list[Student]] = []
    unvisited = {s.student_id: s for s in remaining}
    for s in remaining:
        if s.student_id not in unvisited:
            continue
        comp = [unvisited.pop(s.student_id)]
        frontier = [s]
        while frontier:
            cur = frontier.pop()
            for other_id in sorted(unvisited):
                other = unvisited[other_id]
                if _pairwise_compatible(cur, other, config):
                    frontier.append(unvisited.pop(other_id))
                    comp.append(other)
        comps.append(sorted(comp, key=lambda s: s.student_id))
    return comps


def _feasible(group: list[Student], config: Config) -> bool:
    return len(group_overlap_slots(group)) >= config.min_overlap


def _seed_and_grow(comp: list[Student], config: Config) -> tuple[list[list[Student]], list[Student]]:
    unassigned = {s.student_id: s for s in comp}
    groups: list[list[Student]] = []
    leftovers: list[Student] = []

    def compat_count(s: Student) -> int:
        return sum(
            1
            for oid, o in unassigned.items()
            if oid != s.student_id and _pairwise_compatible(s, o, config)
        )

    for size in plan_group_sizes(len(comp), config):
        if len(unassigned) < config.min_size:
            break
        # Most-constrained seed first: fewest remaining compatible peers,
        # tie broken by smallest id.
        seed = min(unassigned.values(), key=lambda s: (compat_count(s), s.student_id))
        group = [unassigned.pop(seed.student_id)]
        while len(group) < size:
            candidates = [
                unassigned[cid]
                for cid in sorted(unassigned)
                if _feasible(group + [unassigned[cid]], config)
            ]
            if not candidates:
                break
            best = max(candidates, key=lambda c: group_score(group + [c], config))
            group.append(unassigned.pop(best.student_id))
        if len(group) >= config.min_size:
            groups.append(sorted(group, key=lambda s: s.student_id))
        else:
            leftovers.extend(group)
    leftovers.extend(unassigned[cid] for cid in sorted(unassigned))
    return groups, leftovers


def _isolation_totals(groups: list[list[Student]]) -> tuple[int, int]:
    return (
        sum(equity_isolation_count(g) for g in groups),
        sum(lone_minority_count(g) for g in groups),
    )


def repair_pass(groups: list[list[Student]], config: Config) -> list[list[Student]]:
    """Bounded swap sweep: fix equity/lone-minority isolation by swapping
    members between groups, never breaking a hard constraint."""
    groups = [sorted(g, key=lambda s: s.student_id) for g in groups]
    for _ in range(REPAIR_SWEEPS):
        improved = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                for s in list(groups[i]):
                    for t in list(groups[j]):
                        new_i = sorted(
                            [m for m in groups[i] if m is not s] + [t],
                            key=lambda x: x.student_id,
                        )
                        new_j = sorted(
                            [m for m in groups[j] if m is not t] + [s],
                            key=lambda x: x.student_id,
                        )
                        if not (_feasible(new_i, config) and _feasible(new_j, config)):
                            continue
                        before = _isolation_totals([groups[i], groups[j]])
                        after = _isolation_totals([new_i, new_j])
                        if after < before:
                            groups[i], groups[j] = new_i, new_j
                            improved = True
        if not improved:
            break
    return groups


def _resolve_leftovers(
    groups: list[list[Student]],
    leftovers: list[Student],
    config: Config,
    unplaced: list[dict],
) -> None:
    """Spec 4.4 remainder resolution: grow an existing group (<= max_size),
    else form a new group of >= min_size from remainders, else unplaced."""
    still_left: list[Student] = []
    for s in sorted(leftovers, key=lambda x: x.student_id):
        placed = False
        candidates = [
            g for g in groups if len(g) < config.max_size and _feasible(g + [s], config)
        ]
        if candidates:
            best = max(candidates, key=lambda g: group_score(g + [s], config))
            best.append(s)
            best.sort(key=lambda x: x.student_id)
            placed = True
        if not placed:
            still_left.append(s)
    # Try to form new groups from what's left.
    pool = still_left
    while len(pool) >= config.min_size:
        seed, rest = pool[0], pool[1:]
        group = [seed]
        for c in rest:
            if len(group) < config.max_size and _feasible(group + [c], config):
                group.append(c)
        if len(group) >= config.min_size:
            groups.append(sorted(group, key=lambda s: s.student_id))
            taken = {s.student_id for s in group}
            pool = [s for s in pool if s.student_id not in taken]
        else:
            unplaced.append(
                {
                    "student_id": seed.student_id,
                    "reason": "shares fewer than min_overlap slots with any viable group",
                }
            )
            pool = rest
    for s in pool:
        unplaced.append(
            {
                "student_id": s.student_id,
                "reason": "shares fewer than min_overlap slots with any viable group",
            }
        )


def match(students: list[Student], config: Config) -> MatchResult:
    result = MatchResult()
    for comp in _components(students, config):
        if len(comp) < config.min_size:
            for s in comp:
                result.unplaced.append(
                    {
                        "student_id": s.student_id,
                        "reason": "no schedule-compatible classmates (fewer than "
                        f"{config.min_size} students share {config.min_overlap}+ slots)",
                    }
                )
            continue
        groups, leftovers = _seed_and_grow(comp, config)
        groups = repair_pass(groups, config)
        _resolve_leftovers(groups, leftovers, config, result.unplaced)
        groups = repair_pass(groups, config)
        result.groups.extend(groups)

    result.groups.sort(key=lambda g: g[0].student_id)
    for i, g in enumerate(result.groups, start=1):
        shared = group_overlap_slots(g)
        result.meeting_slots.append(shared[: config.min_overlap])
        if equity_isolation_count(g):
            result.warnings.append(
                f"group {i} isolates a lone woman or non-binary student and no "
                "feasible swap was found — flagged for instructor review"
            )
        if lone_minority_count(g):
            result.warnings.append(
                f"group {i} has a lone member with a known disability among "
                "known-non-disabled peers and no feasible swap was found — "
                "flagged for instructor review"
            )
    result.unplaced.sort(key=lambda u: u["student_id"])
    return result
