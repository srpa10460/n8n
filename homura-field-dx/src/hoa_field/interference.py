"""Interference checks. Three separate questions, never merged into one number:

 1. OVERLAP   - do two solids occupy the same volume?
                Boxes A,B overlap iff the penetration depth is > 0 on ALL three axes, where
                penetration_i = min(A.max_i, B.max_i) - max(A.min_i, B.min_i).
                penetration == 0 on an axis (face contact) is NOT overlap; it is reported as CONTACT in metrics.
 2. DISTANCE  - how far apart are two solids? Euclidean distance between the boxes:
                sqrt(sum_i max(0, gap_i)^2), gap_i = max(A.min_i - B.max_i, B.min_i - A.max_i).
                Per-axis gaps are reported too. Status INFO: a distance alone has no pass/fail without a requirement.
 3. SERVICE   - work / maintenance / opening space an object REQUIRES. The required depth and its
                basis are input values on the definition (ServiceSpace); nothing is assumed.
                The space is a box extruded from one face of the object (face width x depth_mm).
                PASS: it overlaps no other object and stays inside the room.  FAIL: it does.
                UNCHECKED: no space defined, other objects unconfirmed/unplaced (cannot rule out),
                door/drawer object without an "opening" space, or unsupported shape.
 Also ROOM: solid inside room bounds.

Scope limits (reported as UNCHECKED, never PASS): non-box shapes; opening envelopes not declared;
objects not registered in the project; rotations other than 0/90/180/270.
Front faces +y at rotation 0; rotation is counter-clockwise in plan (0:+y, 90:-x, 180:-y, 270:+x).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from itertools import combinations

from .project import ObjectInstance, Project

ZERO = Decimal(0)
_NORMAL = {0: {"front": (0, 1), "back": (0, -1), "left": (-1, 0), "right": (1, 0)}}
# local (rot 0) normals rotated CCW by rot
def _rot(n, rot):
    x, y = n
    for _ in range(rot // 90):
        x, y = -y, x
    return x, y


@dataclass(frozen=True)
class Box:
    x0: Decimal; y0: Decimal; z0: Decimal; x1: Decimal; y1: Decimal; z1: Decimal


@dataclass(frozen=True)
class Result:
    pair_id: str                 # stable id used for waivers
    kind: str                    # OVERLAP | DISTANCE | SERVICE | OPENING | ROOM
    status: str                  # PASS | FAIL | UNCHECKED | INFO
    reason: str
    metrics: dict = field(default_factory=dict, compare=False)


def scope_notes() -> list[str]:
    return ["box shapes only", "opening envelopes only if declared as 'opening' spaces",
            "service-space depth/basis are client inputs, not defaults", "objects outside the project are unknown"]


def box_of(p: Project, inst: ObjectInstance) -> Box | None:
    d = p.definition(inst)
    if d.shape_template != "box" or inst.placement is None or not p.dims_confirmed(inst):
        return None
    ext = {s.axis: inst.measurements[s.key].mm for s in d.dimensions if s.required}
    w, dp, h = ext["x"], ext["y"], ext["z"]
    if inst.placement.rotation_deg in (90, 270):
        w, dp = dp, w
    pl = inst.placement
    return Box(pl.x_mm, pl.y_mm, pl.z_mm, pl.x_mm + w, pl.y_mm + dp, pl.z_mm + h)


def axis_gaps(a: Box, b: Box) -> tuple[Decimal, Decimal, Decimal]:
    return (max(a.x0 - b.x1, b.x0 - a.x1), max(a.y0 - b.y1, b.y0 - a.y1), max(a.z0 - b.z1, b.z0 - a.z1))


def euclid(gaps) -> Decimal:
    return sum((max(ZERO, g) ** 2 for g in gaps), ZERO).sqrt()


def overlaps(a: Box, b: Box) -> bool:
    return all(g < 0 for g in axis_gaps(a, b))


def space_box(b: Box, rot: int, side: str, depth: Decimal) -> Box:
    if side == "top":
        return Box(b.x0, b.y0, b.z1, b.x1, b.y1, b.z1 + depth)
    nx, ny = _rot(_NORMAL[0][side], rot)
    x0, x1, y0, y1 = b.x0, b.x1, b.y0, b.y1
    if nx > 0: x0, x1 = b.x1, b.x1 + depth
    elif nx < 0: x0, x1 = b.x0 - depth, b.x0
    if ny > 0: y0, y1 = b.y1, b.y1 + depth
    elif ny < 0: y0, y1 = b.y0 - depth, b.y0
    return Box(x0, y0, b.z0, x1, y1, b.z1)


def check_all(p: Project) -> list[Result]:
    res: list[Result] = []
    insts = sorted(p.instances.values(), key=lambda i: i.object_id)
    boxes = {i.object_id: box_of(p, i) for i in insts}
    W, Dp, H = p.room["w"], p.room["d"], p.room["h"]
    for i in insts:
        b = boxes[i.object_id]
        if b is None:
            why = ("unsupported shape" if p.definition(i).shape_template != "box"
                   else "dimensions not confirmed (measured) or not placed")
            res.append(Result(f"{i.object_id}@room", "ROOM", "UNCHECKED", why))
            continue
        ok = b.x0 >= 0 and b.y0 >= 0 and b.z0 >= 0 and b.x1 <= W and b.y1 <= Dp and b.z1 <= H
        res.append(Result(f"{i.object_id}@room", "ROOM", "PASS" if ok else "FAIL",
                          "inside room" if ok else "outside room bounds"))
    for a, c in combinations(insts, 2):
        ba, bc = boxes[a.object_id], boxes[c.object_id]
        pid = f"{a.object_id}|{c.object_id}"
        if ba is None or bc is None:
            res.append(Result(f"{pid}#overlap", "OVERLAP", "UNCHECKED", "an object is unconfirmed/unplaced"))
            continue
        g = axis_gaps(ba, bc)
        pen = tuple(-x for x in g)
        if all(x > 0 for x in pen):
            res.append(Result(f"{pid}#overlap", "OVERLAP", "FAIL",
                              f"solids overlap (penetration x/y/z = {pen[0]}/{pen[1]}/{pen[2]} mm)",
                              {"penetration": [str(x) for x in pen]}))
        else:
            contact = max(g) == 0
            res.append(Result(f"{pid}#overlap", "OVERLAP", "PASS", "contact (0 mm), no overlap" if contact
                              else "no overlap", {"contact": contact}))
        e = euclid(g)
        res.append(Result(f"{pid}#distance", "DISTANCE", "INFO", f"distance {e.quantize(Decimal('0.001'))} mm "
                          f"(axis gaps x/y/z {g[0]}/{g[1]}/{g[2]})",
                          {"euclid_mm": str(e.quantize(Decimal('0.001'))), "gaps": [str(x) for x in g]}))
    for i in insts:
        d = p.definition(i)
        b = boxes[i.object_id]
        spaces = [s for s in d.required_spaces]
        if not spaces:
            res.append(Result(f"{i.object_id}#service", "SERVICE", "UNCHECKED",
                              "no required service space defined for this definition version"))
        if d.has_opening and not any(s.kind == "opening" for s in spaces):
            res.append(Result(f"{i.object_id}#opening", "OPENING", "UNCHECKED",
                              "door/drawer object without a declared opening envelope"))
        if b is None:
            continue
        others_unknown = [o.object_id for o in insts if o is not i and boxes[o.object_id] is None]
        for s in spaces:
            sid = f"{i.object_id}#{s.kind}-{s.side}"
            zone = space_box(b, i.placement.rotation_deg, s.side, s.depth_mm)
            hits = [o.object_id for o in insts if o is not i and boxes[o.object_id] and overlaps(zone, boxes[o.object_id])]
            outside = not (zone.x0 >= 0 and zone.y0 >= 0 and zone.z0 >= 0 and zone.x1 <= W and zone.y1 <= Dp and zone.z1 <= H)
            basis = f"{s.depth_mm} mm, basis: {s.basis}"
            if hits or outside:
                why = []
                if hits: why.append("blocked by " + ",".join(hits))
                if outside: why.append("extends outside room")
                res.append(Result(sid, "OPENING" if s.kind == "opening" else "SERVICE", "FAIL", "; ".join(why) + f" ({basis})"))
            elif others_unknown:
                res.append(Result(sid, "OPENING" if s.kind == "opening" else "SERVICE", "UNCHECKED",
                                  f"clear of known objects, but unconfirmed objects exist: {','.join(others_unknown)} ({basis})"))
            else:
                res.append(Result(sid, "OPENING" if s.kind == "opening" else "SERVICE", "PASS", f"space free ({basis})"))
    return res


def overall(results: list[Result]) -> str:
    rel = [r for r in results if r.status != "INFO"]
    if any(r.status == "FAIL" for r in rel):
        return "FAIL"
    if any(r.status == "UNCHECKED" for r in rel) or not rel:
        return "INCOMPLETE"
    return "PASS"
