"""Blender build script (run INSIDE Blender: blender -b -P blender_build.py -- manifest.json model.obj out.blend).
Imports the approved OBJ as-is (mm -> scene unit scale 0.001) and never edits geometry.
STATUS: written, NOT executed (Blender is not installed in this environment)."""
import json
import sys

try:
    import bpy  # type: ignore
except ImportError:  # outside Blender
    bpy = None


def main(argv):
    manifest_path, obj_path, out = argv
    manifest = json.load(open(manifest_path))
    if not manifest["approved"]:
        raise SystemExit("refusing: source manifest is not approved")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.scale_length = 0.001
    bpy.ops.wm.obj_import(filepath=obj_path)
    bpy.context.scene["source_hash"] = manifest["content_hash"]
    bpy.context.scene["source_version"] = manifest["data_version"]
    bpy.ops.wm.save_as_mainfile(filepath=out)


if __name__ == "__main__" and bpy is not None:
    main(sys.argv[sys.argv.index("--") + 1:])
