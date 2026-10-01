"""Interference check with explicit PASS / FAIL / UNCHECKED. Never passes what it could not check.

Geometry: axis-aligned boxes from the definition's box template and the placement
(rotation 0/180 keep x/y extents, 90/270 swap them). Scope: object-vs-object and
object-vs-room bounds. Door swings, non-box shapes, obstacles not in the project are OUT OF SCOPE
and are reported as such in the result of `scope_notes()`.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations

from .project import Project, ObjectInstance


@dataclass(frozen=True)
class Box:
    x0: Decimal; y0: Decimal; z0: Decimal; x1: Decimal; y1: Decimal; z1: Decimal


@dataclass(frozen=True)
class Result:
    pair_id: str
    status: str   # PASS | FAIL | UNCHECKED
    reason: str


def scope_notes() -> list[str]:
    return ["box templates only", "no door/drawer swing envelopes", "objects not in project are unknown",
            "clearance checked only where the definition declares clearance_mm"]


def box_of(p: Project, inst: ObjectInstance) -> Box | None:
    if inst.placement is None or not p.dims_confirmed(inst):
        return None
    d = p.definition(inst)
    ext = {s.axis: inst.measurements[s.key].mm for s in d.dimensions if s.required}
    w, dp, h = ext["x"], ext["y"], ext["z"]
    if inst.placement.rotation_deg in (90, 270):
        w, dp = dp, w
    pl = inst.placement
    return Box(pl.x_mm, pl.y_mm, pl.z_mm, pl.x_mm + w, pl.y_mm + dp, pl.z_mm + h)


def _gap(a: Box, b: Box) -> Decimal:
    """Smallest axis separation; negative => overlapping in that axis. Returns max over axes
    (>=0 means separated; overlap in all axes => negative)."""
    gx = max(a.x0 - b.x1, b.x0 - a.x1)
    gy = max(a.y0 - b.y1, b.y0 - a.y1)
    gz = max(a.z0 - b.z1, b.z0 - a.z1)
    return max(gx, gy, gz)


def check_all(p: Project) -> list[Result]:
    res: list[Result] = []
    insts = list(p.instances.values())
    for inst in insts:
        pid = f"{inst.object_id}@room"
        b = box_of(p, inst)
        if b is None:
            res.append(Result(pid, "UNCHECKED", "dimensions not confirmed or not placed"))
            continue
        inside = (b.x0 >= 0 and b.y0 >= 0 and b.z0 >= 0 and
                  b.x1 <= p.room["w"] and b.y1 <= p.room["d"] and b.z1 <= p.room["h"])
        res.append(Result(pid, "PASS" if inside else "FAIL", "inside room" if inside else "outside room bounds"))
    for a, c in combinations(insts, 2):
        pid = f"{a.object_id}|{c.object_id}"
        ba, bc = box_of(p, a), box_of(p, c)
        if ba is None or bc is None:
            res.append(Result(pid, "UNCHECKED", "dimensions not confirmed or not placed"))
            continue
        gap = _gap(ba, bc)
        if gap < 0:
            res.append(Result(pid, "FAIL", f"solids overlap (penetration {-gap} mm)"))
            continue
        reqs = [r for r in (p.definition(a).clearance_mm, p.definition(c).clearance_mm) if r is not None]
        if not reqs:
            res.append(Result(pid, "UNCHECKED", f"no clearance defined (gap {gap} mm, no overlap)"))
        elif gap >= max(reqs):
            res.append(Result(pid, "PASS", f"gap {gap} mm >= required {max(reqs)} mm"))
        else:
            res.append(Result(pid, "FAIL", f"gap {gap} mm < required {max(reqs)} mm"))
    return res


def overall(results: list[Result]) -> str:
    if any(r.status == "FAIL" for r in results):
        return "FAIL"
    if any(r.status == "UNCHECKED" for r in results) or not results:
        return "INCOMPLETE"
    return "PASS"
