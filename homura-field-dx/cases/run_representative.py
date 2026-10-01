"""Run representative case 1 end to end. Usage: python3 cases/run_representative.py [outdir]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hoa_field.export import export_all
from hoa_field.sample_case import build_project
from hoa_field.scene import derive_scene

out = Path(sys.argv[1] if len(sys.argv) > 1 else "evidence/case1")
p = build_project()
export_all(p, out / "preview")            # unapproved -> marked
p.submit_for_review()
a = p.approve("Daiki Isa (SIMULATED approval for dev test; not a real review)",
              expect_version=p.data_version, expect_hash=p.content_hash())
export_all(p, out / "approved")
s = derive_scene(p, "S-0001")
s.explode_object("O-WCB", "0", "0", "300")
print("approved v", a.approved_version, a.content_hash[:12], "scene integrity", s.verify_integrity())
