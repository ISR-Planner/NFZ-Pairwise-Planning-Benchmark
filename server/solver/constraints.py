"""Ordering-constraint helpers for solver orchestration."""

from typing import Any, Dict, Optional


def _normalize_constraints(c: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Coerce a raw constraints dict into the canonical shape, or None if empty."""
    if not c:
        return None
    first = c.get("first") or None
    last = c.get("last") or None
    before = [(str(a), str(b)) for a, b in (c.get("before") or []) if a and b]
    adjacent = [(str(y), str(x)) for y, x in (c.get("adjacent") or []) if y and x]
    if not (first or last or before or adjacent):
        return None
    return {
        "first": str(first) if first else None,
        "last": str(last) if last else None,
        "before": before,
        "adjacent": adjacent,
    }


def _constraints_for_drone(
    constraints: Optional[Dict[str, Any]], did: str
) -> Optional[Dict[str, Any]]:
    """Resolve constraints that apply to a physical or virtual drone id."""
    if not constraints:
        return None
    if any(k in constraints for k in ("first", "last", "before", "adjacent")):
        return _normalize_constraints(constraints)

    try:
        from .virtual_drones import parent_of as _parent_of

        phys = _parent_of(did)
    except Exception:
        phys = did

    per = constraints.get(str(did)) or constraints.get(str(phys))
    return _normalize_constraints(per)


def _subset_constraints_for_leg(
    constraints: Optional[Dict[str, Any]],
    leg_target_ids,
    is_first_leg: bool,
    is_last_leg: bool,
) -> Optional[Dict[str, Any]]:
    """Restrict a drone's constraints to a single refuel leg."""
    if not constraints:
        return None
    ids = set(str(t) for t in (leg_target_ids or []))

    first = constraints.get("first") if is_first_leg else None
    if first and first not in ids:
        first = None
    last = constraints.get("last") if is_last_leg else None
    if last and last not in ids:
        last = None

    before = [(a, b) for a, b in constraints.get("before", []) if a in ids and b in ids]

    adjacent = []
    for y, x in constraints.get("adjacent", []):
        y_in, x_in = y in ids, x in ids
        if y_in and x_in:
            adjacent.append((y, x))
        elif y_in ^ x_in:
            raise ValueError(
                f"Cross-leg adjacency constraint ({y} right after {x}) cannot be "
                "split across a refuel boundary - both targets must be on the "
                "same leg."
            )
    return _normalize_constraints(
        {"first": first, "last": last, "before": before, "adjacent": adjacent}
    )


def _ordering_legal(route, constraints: Optional[Dict[str, Any]]) -> bool:
    """Return True when a full route list satisfies ordering constraints."""
    if not constraints:
        return True
    pos = {node: i for i, node in enumerate(route)}

    first = constraints.get("first")
    if first is not None:
        if len(route) < 2 or route[1] != first:
            return False

    last = constraints.get("last")
    if last is not None:
        if len(route) < 2 or route[-2] != last:
            return False

    for a, b in constraints.get("before", []):
        if a in pos and b in pos and pos[a] > pos[b]:
            return False

    for y, x in constraints.get("adjacent", []):
        if y in pos and x in pos and pos[x] != pos[y] + 1:
            return False

    return True
