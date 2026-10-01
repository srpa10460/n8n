"""Outputs (2D SVG, 3D OBJ, manifest). Unapproved data is always visibly marked.
Writes are atomic (temp + rename) and idempotent (same input => same bytes)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .interference import box_of, check_all, overall
from .project import Project


class ExportError(RuntimeError):
    pass


def _banner(p: Project) -> str:
    a = p.current_approval()
    if not a:
        return "UNAPPROVED PREVIEW"
    return "DEV SIMULATED APPROVAL" if a.kind == "DEV_SIMULATED" else ""


def atomic_write(path: Path, data: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as e:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise ExportError(f"write failed: {path}: {e}") from e


def svg_plan(p: Project) -> str:
    W, D = float(p.room["w"]), float(p.room["d"])
    s = 0.2  # px per mm
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W*s+80:.0f}" height="{D*s+160:.0f}" '
           f'viewBox="-40 -40 {W*s+80:.0f} {D*s+160:.0f}" font-family="sans-serif" font-size="12">',
           f'<rect x="0" y="0" width="{W*s:.1f}" height="{D*s:.1f}" fill="none" stroke="#222" stroke-width="2"/>',
           f'<text x="0" y="-12">{p.project_id}  data v{p.data_version}  hash {p.content_hash()[:12]}</text>']
    legend: list[str] = []
    for n, (oid, inst) in enumerate(sorted(p.instances.items())):
        b = box_of(p, inst)
        if b is None:
            out.append(f'<text x="0" y="{D*s+20+14*n:.0f}" fill="#b00">{oid}: not drawn (dimensions unconfirmed / not placed)</text>')
            continue
        w, d = float(b.x1 - b.x0), float(b.y1 - b.y0)
        elevated = b.z0 > 0
        dash = ' stroke-dasharray="5 3"' if elevated else ""
        # labels go in a legend below the room (stacked objects overlap in plan view)
        out.append(f'<g data-object-id="{oid}"><rect x="{float(b.x0)*s:.1f}" y="{float(b.y0)*s:.1f}" '
                   f'width="{w*s:.1f}" height="{d*s:.1f}" fill="#cfe3ff" fill-opacity="0.45" stroke="#036"{dash}/>'
                   f'<text x="{float(b.x0)*s+4:.1f}" y="{float(b.y0)*s+14+(14 if elevated else 0):.1f}">{n+1}</text></g>')
        legend.append(f'<text x="0" y="{D*s+22+16*n:.0f}">{n+1}: {oid} {inst.label}  '
                      f'{b.x1-b.x0:g} x {b.y1-b.y0:g} mm, z {b.z0:g}-{b.z1:g}{" (dashed = elevated)" if elevated else ""}</text>')
    out.extend(legend)
    banner = _banner(p)
    if banner:
        out.append(f'<text x="{W*s/2:.0f}" y="{D*s/2:.0f}" text-anchor="middle" font-size="40" fill="#e00" '
                   f'fill-opacity="0.35">{banner}</text>')
    out.append(f'<text x="0" y="{D*s+22+16*len(p.instances):.0f}">interference: {overall(check_all(p))} (see manifest)</text></svg>')
    return "\n".join(out)


def obj_model(p: Project) -> str:
    lines = [f"# {p.project_id} data_version={p.data_version} hash={p.content_hash()}",
             f"# {_banner(p) or 'APPROVED'}"]
    n = 0
    for oid, inst in sorted(p.instances.items()):
        b = box_of(p, inst)
        if b is None:
            lines.append(f"# {oid}: skipped (unconfirmed/unplaced)")
            continue
        lines.append(f"o {oid}")
        xs, ys, zs = (b.x0, b.x1), (b.y0, b.y1), (b.z0, b.z1)
        for z in zs:
            for y in ys:
                for x in xs:
                    lines.append(f"v {x} {z} {-y}")  # Y-up export, mm
        f = [(1, 2, 4, 3), (5, 7, 8, 6), (1, 5, 6, 2), (3, 4, 8, 7), (1, 3, 7, 5), (2, 6, 8, 4)]
        for q in f:
            lines.append("f " + " ".join(str(n + i) for i in q))
        n += 8
    return "\n".join(lines) + "\n"


def manifest(p: Project) -> dict:
    a = p.current_approval()
    res = check_all(p)
    return {
        "project_id": p.project_id, "data_version": p.data_version, "content_hash": p.content_hash(),
        "approved": a is not None,
        "approved_version": a.approved_version if a else None,
        "approver": a.approver if a else None,
        "approval_kind": a.kind if a else None,
        "unit": "mm",
        "geometry_mm": {oid: {k: str(v) for k, v in zip(("x0", "y0", "z0", "x1", "y1", "z1"),
                              (b.x0, b.y0, b.z0, b.x1, b.y1, b.z1))}
                        for oid, i in sorted(p.instances.items()) if (b := box_of(p, i)) is not None},
        "waivers": a.waivers if a else {},
        "unit": "mm",
        "objects": {oid: {"asset_object_id": oid, "definition": f"{i.definition_id}@v{i.definition_version}",
                          "photos": i.photo_ids} for oid, i in sorted(p.instances.items())},
        "interference": {"overall": overall(res),
                         "results": [{"id": r.pair_id, "kind": r.kind, "status": r.status, "reason": r.reason,
                                      "metrics": r.metrics} for r in res]},
        "validation": [{"severity": i.severity, "code": i.code, "object": i.object_id, "detail": i.detail}
                       for i in p.validate()],
        "status_note": "UNAPPROVED PREVIEW" if a is None else (
            "approved (DEV SIMULATED - not a real-case approval)" if a.kind == "DEV_SIMULATED" else "approved (human final)"),
    }


def export_files(p: Project) -> dict[str, str]:
    """Pure: file name -> text. Same bytes for same input (idempotent)."""
    return {"plan.svg": svg_plan(p), "model.obj": obj_model(p),
            "snapshot.json": json.dumps(p.snapshot(), sort_keys=True),
            "manifest.json": json.dumps(manifest(p), indent=2, sort_keys=True, ensure_ascii=False)}


def export_all(p: Project, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    files = export_files(p)
    written = []
    for name, data in files.items():
        atomic_write(outdir / name, data)
        written.append(outdir / name)
    return written
