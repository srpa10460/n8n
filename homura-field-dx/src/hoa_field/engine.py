"""Pure operation engine shared by the browser (Pyodide) and tests. No I/O, no globals:
   call(op, state, payload) -> {"state": new_state, "result": ...}
state = {"catalog": <Catalog.to_dict()>, "project": <Project.to_dict()> | None}
The same code validates data on a tablet with no network and on the server at sync time."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

from .catalog import Catalog, definition_from_dict
from .export import manifest, obj_model, svg_plan
from .interference import check_all, overall, scope_notes
from .project import Project, Source

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
MAX_UPLOAD = 8 * 1024 * 1024
MAGIC = {b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpg", b"RIFF": "webp"}
REQUIRED_CONFIRMATIONS = ["version_hash_seen", "plan_seen", "dims_measured", "interference_seen",
                          "no_estimates", "waivers_reasoned"]


class EngineError(ValueError):
    pass


def need_id(v, what="id"):
    if not isinstance(v, str) or not ID_RE.match(v):
        raise EngineError(f"invalid {what}: use letters, digits, _ . - (max 64)")
    return v


def _j(o):
    return json.loads(json.dumps(o, default=str))


def detail(cat: Catalog, p: Project) -> dict:
    res = check_all(p)
    rv = p.review_items()
    insts = []
    for inst in sorted(p.instances.values(), key=lambda i: i.object_id):
        d = p.definition(inst)
        dims = []
        for s in d.dimensions:
            state, why = p.dimension_status(inst, s.key)
            m = inst.measurements.get(s.key)
            dims.append({**_j(asdict(s)), "state": state, "why": why,
                         "mm": str(m.mm) if m else None, "input": m.original_input if m else None,
                         "meas_source": m.source.value if m else None, "by": m.measured_by if m else None})
        insts.append({
            "object_id": inst.object_id, "label": inst.label, "definition": {
                "id": d.definition_id, "version": d.version, "latest_version": cat.get(inst.definition_id).version,
                "name": d.name, "category": d.category, "required_photos": list(d.required_photos),
                "required_annotations": list(d.required_annotations), "has_opening": d.has_opening,
                "required_spaces": _j([asdict(x) for x in d.required_spaces])},
            "dims": dims, "confirmed": p.dims_confirmed(inst),
            "placement": None if inst.placement is None else {
                "x": str(inst.placement.x_mm), "y": str(inst.placement.y_mm), "z": str(inst.placement.z_mm),
                "rot": inst.placement.rotation_deg},
            "photos": [{"asset_id": a, "tag": inst.photo_tags[a], **p.assets.get(a, {})} for a in inst.photo_ids],
            "annotations": inst.annotations})
    cur = p.current_approval()
    return {
        "project_id": p.project_id, "status": p.status.value, "data_version": p.data_version,
        "content_hash": p.content_hash(), "room": {k: str(v) for k, v in p.room.items()},
        "instances": insts, "history": p.history[-30:],
        "validation": [asdict(i) for i in p.validate()],
        "interference": {"overall": overall(res), "scope": scope_notes(),
                         "results": [{"id": r.pair_id, "kind": r.kind, "status": r.status, "reason": r.reason}
                                     for r in res]},
        "review": {"fail": [r.pair_id for r in rv["fail"]], "unchecked": [r.pair_id for r in rv["unchecked"]],
                   "validation_errors": len(rv["validation_errors"]), "estimated": rv["estimated"],
                   "required_confirmations": REQUIRED_CONFIRMATIONS},
        "approvals": _j([asdict(a) for a in p.approvals]),
        "approval_current": None if cur is None else {"kind": cur.kind, "approver": cur.approver,
                                                      "version": cur.approved_version},
        "assets": p.assets,
        "plan_svg": svg_plan(p),
    }


def catalog_view(cat: Catalog) -> dict:
    return {k: [_j(asdict(v)) for v in vs] for k, vs in cat._defs.items()}


def referenced_catalog(cat: Catalog, p: Project) -> dict:
    """Only the definition versions this project pins (what the server needs to re-verify it)."""
    out: dict = {}
    for i in p.instances.values():
        for v in range(1, i.definition_version + 1):
            out.setdefault(i.definition_id, {})[v] = cat.get(i.definition_id, v)
    res = {}
    for k, vs in out.items():
        res[k] = [_j(asdict(vs[v])) for v in sorted(vs)]
    return res


def call(op: str, state: dict, payload: dict | None = None) -> dict:
    payload = payload or {}
    cat = Catalog.from_dict(state.get("catalog") or {})
    p = Project.from_dict(state["project"], cat) if state.get("project") else None
    result: dict = {}
    changed_catalog = changed_project = False

    def need():
        if p is None:
            raise EngineError("no project open")
        return p

    if op == "create_project":
        pid = need_id(payload.get("project_id"), "project_id")
        u = payload.get("unit", "mm")
        p = Project(pid, cat, f"{payload['w']} {u}", f"{payload['d']} {u}", f"{payload['h']} {u}")
        changed_project = True
    elif op == "publish_definition":
        d = definition_from_dict(payload)
        need_id(d.definition_id, "definition_id")
        pub = cat.publish(d)
        result["published"] = f"{pub.definition_id}@v{pub.version}"
        changed_catalog = True
    elif op == "load_sample_catalog":
        from .sample_case import build_catalog
        n = 0
        for k, vs in build_catalog()._defs.items():
            if k not in cat._defs:
                cat.publish(vs[0]); n += 1
        result["added"] = n
        changed_catalog = True
    elif op == "add_instance":
        oid = need_id(payload.get("object_id"), "object_id")
        need_id(payload.get("definition_id"), "definition_id")
        if oid in need().instances:
            raise EngineError("object exists")
        p.add_instance(oid, payload["definition_id"], payload.get("label") or oid)
        changed_project = True
    elif op == "measure":
        oid = need_id(payload.get("object_id"), "object_id")
        key = need_id(payload.get("key"), "dimension key")
        need().set_measurement(oid, key,
                               f"{payload['value']} {payload.get('unit', 'mm')}".strip(),
                               Source(payload.get("source", "MEASURED")), by=payload.get("by", ""))
        changed_project = True
    elif op == "place":
        oid = need_id(payload.get("object_id"), "object_id")
        u = payload.get("unit", "mm")
        need().place(oid, f"{payload['x']} {u}", f"{payload['y']} {u}",
                     f"{payload.get('z', 0)} {u}", int(payload.get("rotation", 0)))
        changed_project = True
    elif op == "photo_check":
        # validate + describe bytes BEFORE the device stores anything
        data = _decode(payload)
        result.update(_photo_meta(data, payload))
    elif op == "add_photo":
        oid = need_id(payload.get("object_id"), "object_id")
        need_id(payload.get("tag"), "photo tag")
        data = _decode(payload)
        meta = _photo_meta(data, payload)
        need().add_photo(oid, meta["asset_id"], payload["tag"], meta["meta"])
        result.update(meta)
        changed_project = True
    elif op == "annotate":
        oid = need_id(payload.get("object_id"), "object_id")
        need().annotate(oid, need_id(payload.get("key"), "annotation key"),
                        str(payload.get("text", ""))[:2000])
        changed_project = True
    elif op == "submit_review":
        need().submit_for_review()
        changed_project = True
    elif op == "approve":
        conf = payload.get("confirmations", [])
        missing = [c for c in REQUIRED_CONFIRMATIONS if c not in conf]
        if missing:
            raise EngineError("all review confirmations must be ticked: " + ",".join(missing))
        # Fail Closed at Engine layer: omit / mismatch of version+hash must reject (do not trust UI).
        if "expect_version" not in payload or payload.get("expect_version") is None:
            raise EngineError("expect_version required (version-bound approval)")
        if "expect_hash" not in payload or payload.get("expect_hash") in (None, ""):
            raise EngineError("expect_hash required (hash-bound approval)")
        need().approve(str(payload.get("approver", "")), payload.get("waivers") or {},
                       payload.get("kind", "DEV_SIMULATED"), payload.get("expect_version"),
                       payload.get("expect_hash"), conf)
        changed_project = True
    elif op == "export":
        from .export import export_files
        result["files"] = export_files(need())
    elif op == "detail":
        pass
    elif op == "merge_catalog":   # fetch from server: append missing versions, refuse silent divergence
        cat.merge_definitions(payload["catalog"])
        changed_catalog = True
    elif op == "sync_package":
        pp = need()
        result["package"] = {"project": pp.to_dict(), "catalog": referenced_catalog(cat, pp),
                             "content_hash": pp.content_hash(), "data_version": pp.data_version,
                             "assets": [{"asset_id": a, **m} for a, m in sorted(pp.assets.items())]}
    elif op == "verify_package":   # server side: recompute from the received package with the same core
        pk = payload
        c2 = Catalog.from_dict(pk["catalog"])
        pr = Project.from_dict(pk["project"], c2)
        result.update({"content_hash": pr.content_hash(), "data_version": pr.data_version,
                       "snapshot": pr.snapshot(), "assets": sorted(pr.assets.items())})
    else:
        raise EngineError(f"unknown op {op}")

    new_state = {"catalog": cat.to_dict() if changed_catalog else state.get("catalog"),
                 "project": p.to_dict() if (p is not None and changed_project) else state.get("project")}
    result["_changed"] = [n for n, f in (("catalog", changed_catalog), ("project", changed_project)) if f]
    if p is not None:
        # catalog object may have been shared by the project; keep project's catalog reference consistent
        result["detail"] = detail(cat, p)
    result["catalog_view"] = catalog_view(cat)
    return {"state": new_state, "result": result}


def _decode(payload):
    raw = payload.get("data_base64", "")
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise EngineError("bad base64")
    if not data or len(data) > MAX_UPLOAD:
        raise EngineError("empty or too large (max 8 MB)")
    return data


def _photo_meta(data: bytes, payload: dict) -> dict:
    ext = next((e for mg, e in MAGIC.items() if data.startswith(mg)), None)
    if ext is None or (ext == "webp" and data[8:12] != b"WEBP"):
        raise EngineError("only png/jpg/webp images accepted")
    sha = hashlib.sha256(data).hexdigest()
    aid = "A-" + sha[:12]
    return {"asset_id": aid, "meta": {"filename": Path(str(payload.get("filename", "photo"))).name[:80],
                                      "sha256": sha, "bytes": len(data), "file": f"{aid}.{ext}"}}


def call_json(op: str, state_json: str, payload_json: str) -> str:
    """Entry point used from Pyodide: strings in, string out; errors are returned, not raised."""
    try:
        return json.dumps(call(op, json.loads(state_json), json.loads(payload_json)), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)
