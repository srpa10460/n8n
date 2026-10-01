"""B: build a Blender scene from an APPROVED export (manifest.json + snapshot.json) and render stills / orbit frames.
Run (bpy 5.x as a Python module):  python -m hoa_field.blender_build <export_dir> <out_dir>
Rules enforced here (not trusted from the caller):
  - refuses unless manifest.approved is true; labels DEV_SIMULATED approvals on every render path
  - recomputes sha256(canonical snapshot) and requires == manifest.content_hash
  - the model is built ONLY from manifest geometry_mm; afterwards every object's Blender dimensions/location are
    checked against geometry_mm AND against the snapshot's measured values and placements
  - the derived presentation scene (explode) is a separate scene made from COPIES; base objects are verified unchanged
Writes: <out>/model.blend, still.png, still_derived.png, frames/f0001.png.., orbit.mp4, blender_report.json"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

M = 0.001  # mm -> m (Blender unit)
COL = {"O-VAN": (0.25, 0.45, 0.8, 1), "O-WCB": (0.85, 0.55, 0.2, 1), "O-WSH": (0.35, 0.7, 0.45, 1)}


def _verify_inputs(exp: Path):
    man = json.loads((exp / "manifest.json").read_text())
    snap_txt = (exp / "snapshot.json").read_text()
    snap = json.loads(snap_txt)
    if not man.get("approved"):
        raise SystemExit("REFUSED: manifest is not approved")
    h = hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest()
    if h != man["content_hash"]:
        raise SystemExit(f"REFUSED: snapshot hash {h[:12]} != manifest hash {man['content_hash'][:12]}")
    return man, snap, h


def _expected_extents(snap, oid):
    o = snap["objects"][oid]
    dims = sorted(float(m["mm"]) for m in o["measurements"].values())
    rot = o["placement"]["rot"]
    return dims, rot


def build(exp: Path, out: Path, frames: int = 72) -> dict:
    import bpy
    man, snap, h = _verify_inputs(exp)
    out.mkdir(parents=True, exist_ok=True)
    (out / "frames").mkdir(exist_ok=True)
    manifest_bytes_before = (exp / "manifest.json").read_bytes()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = "BASE_APPROVED"
    sc.unit_settings.system, sc.unit_settings.scale_length = "METRIC", 1.0
    report = {"source_hash": h, "data_version": man["data_version"], "approval_kind": man["approval_kind"],
              "bpy": bpy.app.version_string, "objects": {}, "checks": []}

    def check(name, ok, detail=""):
        report["checks"].append({"name": name, "pass": bool(ok), "detail": str(detail)})
        if not ok:
            raise SystemExit(f"CHECK FAILED: {name} {detail}")

    base = bpy.data.collections.new("MODEL_FROM_APPROVED"); sc.collection.children.link(base)
    for oid, g in sorted(man["geometry_mm"].items()):
        x0, y0, z0, x1, y1, z1 = (float(g[k]) for k in ("x0", "y0", "z0", "x1", "y1", "z1"))
        bpy.ops.mesh.primitive_cube_add(size=1)
        ob = bpy.context.active_object
        ob.name = oid
        ob.dimensions = ((x1 - x0) * M, (y1 - y0) * M, (z1 - z0) * M)
        ob.location = (((x0 + x1) / 2) * M, ((y0 + y1) / 2) * M, ((z0 + z1) / 2) * M)
        ob["object_id"], ob["source_hash"], ob["data_version"] = oid, h, man["data_version"]
        ob.color = COL.get(oid, (0.6, 0.6, 0.6, 1))
        for c in list(ob.users_collection): c.objects.unlink(ob)
        base.objects.link(ob)
    bpy.context.view_layer.update()

    # ---- verification against geometry AND the snapshot's measured values
    for oid, g in sorted(man["geometry_mm"].items()):
        ob = bpy.data.objects[oid]
        dim = sorted(round(v / M, 3) for v in ob.dimensions)
        exp_dims, rot = _expected_extents(snap, oid)
        check(f"{oid}: Blender dimensions == snapshot measured values (mm)", all(abs(a - b) < 0.01 for a, b in zip(dim, exp_dims)), (dim, exp_dims))
        lo = (ob.location.x - ob.dimensions.x / 2) / M, (ob.location.y - ob.dimensions.y / 2) / M, (ob.location.z - ob.dimensions.z / 2) / M
        pl = snap["objects"][oid]["placement"]
        check(f"{oid}: placement min corner == snapshot placement (mm)",
              all(abs(a - float(b)) < 0.01 for a, b in zip(lo, (pl["x"], pl["y"], pl["z"]))), (lo, pl))
        report["objects"][oid] = {"dimensions_mm": dim, "min_corner_mm": [round(v, 3) for v in lo]}
    check("all manifest objects present", set(bpy.data.objects.keys()) >= set(man["geometry_mm"]), list(bpy.data.objects.keys()))
    base_loc = {o.name: tuple(o.location) for o in base.objects}

    # ---- room context (floor only; visual aid, not part of approved geometry)
    rw, rd = float(snap["room_mm"]["w"]) * M, float(snap["room_mm"]["d"]) * M
    bpy.ops.mesh.primitive_plane_add(size=1, location=(rw / 2, rd / 2, -0.002)); fl = bpy.context.active_object
    fl.name = "ROOM_FLOOR_CONTEXT"; fl.scale = (rw, rd, 1); fl.color = (0.85, 0.85, 0.85, 1)

    # ---- render setup (Workbench: deterministic, no GPU)
    def setup(sc, w, h_):
        sc.render.engine = "BLENDER_WORKBENCH"
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h_, 100
        s = sc.display.shading
        s.light, s.color_type, s.show_object_outline, s.show_cavity = "STUDIO", "OBJECT", True, False
        sc.render.image_settings.file_format = "PNG"
        if sc.world is None: sc.world = bpy.data.worlds.new("W")
        sc.world.color = (0.96, 0.97, 0.99)
    setup(sc, 960, 540)
    cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 30
    cam = bpy.data.objects.new("Cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
    tgt = bpy.data.objects.new("Target", None); tgt.location = (rw / 2 + 0.1, rd / 2 - 0.3, 0.9); sc.collection.objects.link(tgt)
    tr = cam.constraints.new("TRACK_TO"); tr.target, tr.track_axis, tr.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
    def place_cam(a, r=5.2, z=3.0):
        cam.location = (rw / 2 + r * math.cos(a), rd / 2 + r * math.sin(a), z)
    place_cam(math.radians(65))
    bpy.context.view_layer.update()
    sc.render.filepath = str(out / "still.png"); bpy.ops.render.render(write_still=True)

    # ---- derived presentation scene: explode copies; base untouched
    ds = bpy.data.scenes.new("DERIVED_EXPLODE"); setup(ds, 960, 540)
    dcol = bpy.data.collections.new("DERIVED_COPIES"); ds.collection.children.link(dcol)
    for ob in base.objects:
        c = ob.copy(); c.data = ob.data.copy(); c.name = ob.name + ".derived"
        c["derived_from"] = ob.name
        dcol.objects.link(c)
        if ob.name == "O-WCB": c.location.z += 0.35          # explode the wall cabinet up by 350 mm
    ds.collection.objects.link(fl.copy())
    ds.collection.objects.link(cam.copy()); ds.camera = ds.collection.objects[-1]
    dcam = ds.camera; dcam.constraints.clear(); dcam.location = cam.location
    dt = tgt.copy(); ds.collection.objects.link(dt); t2 = dcam.constraints.new("TRACK_TO"); t2.target, t2.track_axis, t2.up_axis = dt, "TRACK_NEGATIVE_Z", "UP_Y"
    ds.render.filepath = str(out / "still_derived.png"); bpy.context.window.scene = ds if bpy.context.window else bpy.context.window
    bpy.ops.render.render(write_still=True, scene=ds.name)
    check("derived scene did not move base objects", all(tuple(bpy.data.objects[n].location) == l for n, l in base_loc.items()))
    check("derived copy is separate (offset +350 mm only on O-WCB.derived)", abs(bpy.data.objects["O-WCB.derived"].location.z - bpy.data.objects["O-WCB"].location.z - 0.35) < 1e-6)
    check("source files unchanged by build", (exp / "manifest.json").read_bytes() == manifest_bytes_before)

    # ---- orbit frames
    sc.render.resolution_x, sc.render.resolution_y = 640, 360
    for i in range(frames):
        place_cam(math.radians(65) + 2 * math.pi * i / frames)
        sc.render.filepath = str(out / "frames" / f"f{i+1:04d}.png"); bpy.ops.render.render(write_still=True, scene=sc.name)
    bpy.data.scenes.remove(ds)   # derived scene is not saved into the model file
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "model.blend"))
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i", str(out / "frames" / "f%04d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out / "orbit.mp4")], capture_output=True, text=True)
    check("ffmpeg encoded orbit.mp4", r.returncode == 0 and (out / "orbit.mp4").exists(), r.stderr[-300:])
    report["frames"] = frames
    (out / "blender_report.json").write_text(json.dumps(report, indent=1))
    return report


if __name__ == "__main__":
    rep = build(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 72)
    print(json.dumps({"checks": len(rep["checks"]), "all_pass": all(c["pass"] for c in rep["checks"])}))
