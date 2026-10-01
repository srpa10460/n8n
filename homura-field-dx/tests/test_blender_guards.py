"""B input guards (no bpy needed): Blender build must refuse unapproved or tampered exports."""
import json, shutil, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hoa_field.blender_build import _verify_inputs
from hoa_field.export import export_all
from hoa_field.sample_case import build_project


class Guards(unittest.TestCase):
    def export(self, approve):
        p = build_project()
        if approve:
            p.submit_for_review(); p.approve("dev")
        d = Path(tempfile.mkdtemp()); export_all(p, d); return d

    def test_approved_ok(self):
        man, snap, h = _verify_inputs(self.export(True))
        self.assertEqual(h, man["content_hash"])

    def test_unapproved_refused(self):
        with self.assertRaises(SystemExit): _verify_inputs(self.export(False))

    def test_tampered_snapshot_refused(self):
        d = self.export(True); f = d / "snapshot.json"; s = json.loads(f.read_text())
        s["objects"]["O-VAN"]["measurements"]["width"]["mm"] = "999.000"; f.write_text(json.dumps(s, sort_keys=True))
        with self.assertRaises(SystemExit): _verify_inputs(d)


if __name__ == "__main__":
    unittest.main()
