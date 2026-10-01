import sys, tempfile, unittest, json, os
from decimal import Decimal as D
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hoa_field import units
from hoa_field.catalog import Catalog
from hoa_field.project import ApprovalError, Source, Status
from hoa_field.interference import check_all, overall
from hoa_field.export import ExportError, export_all, manifest, svg_plan
from hoa_field.scene import SceneError, derive_scene
from hoa_field.sample_case import build_project, build_catalog


def codes(p, sev="ERROR"):
    return {(i.code, i.object_id) for i in p.validate() if i.severity == sev}


class Units(unittest.TestCase):
    def test_conversions_exact(self):
        self.assertEqual(units.parse_length("1.2 m"), D("1200.000"))
        self.assertEqual(units.parse_length("48 in"), D("1219.200"))
        self.assertEqual(units.parse_length('48"'), D("1219.200"))
        self.assertEqual(units.parse_length("3 ft"), D("914.400"))
        self.assertEqual(units.parse_length("90 cm"), D("900.000"))
        self.assertEqual(units.parse_length("900"), D("900.000"))

    def test_roundtrip_precision(self):
        mm = units.parse_length("33.333 in")
        self.assertEqual(units.from_mm(mm, "in"), D("33.333"))

    def test_rounding_half_up_at_quantum(self):
        self.assertEqual(units.to_mm("0.0005", "mm"), D("0.001"))

    def test_rejects(self):
        for bad in ("abc", "1..2 mm", "5 parsecs", "NaN", "inf mm", ""):
            with self.assertRaises(units.UnitError, msg=bad):
                units.parse_length(bad)
        with self.assertRaises(units.UnitError):
            units.parse_length(0.1)  # float rejected


class Catalog_(unittest.TestCase):
    def test_version_pinning_survives_catalog_update(self):
        p = build_project()
        before = p.content_hash()
        d = p.catalog.get("vanity")
        from dataclasses import replace
        v2 = p.catalog.publish(replace(d, required_photos=d.required_photos + ("side",), clearance_mm=D("100")))
        self.assertEqual(v2.version, 2)
        self.assertEqual(p.instances["O-VAN"].definition_version, 1)
        self.assertEqual(p.content_hash(), before)           # past case meaning unchanged
        self.assertEqual(codes(p), set())                    # still valid under v1
        p.add_instance("O-VAN2", "vanity", "new vanity")      # new instance pins v2
        self.assertEqual(p.instances["O-VAN2"].definition_version, 2)
        self.assertIn(("MISSING_PHOTO", "O-VAN2"), codes(p))

    def test_published_version_immutable_and_unknown(self):
        c = build_catalog()
        with self.assertRaises(KeyError): c.get("nope")
        with self.assertRaises(KeyError): c.get("vanity", 9)

    def test_save_load_roundtrip(self):
        c = build_catalog()
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "c.json"; c.save(f)
            c2 = Catalog.load(f)
        self.assertEqual(c2.get("washer"), c.get("washer"))

    def test_client_can_add_definition_but_bad_ones_rejected(self):
        from dataclasses import replace
        c = build_catalog(); d = c.get("washer")
        with self.assertRaises(ValueError):
            c.publish(replace(d, definition_id="x", dimensions=d.dimensions[:2]))


class Validation(unittest.TestCase):
    def test_complete_case_valid(self):
        p = build_project()
        self.assertEqual(codes(p), set())

    def test_missing_required_dimension(self):
        p = build_project()
        del p.instances["O-VAN"].measurements["depth"]
        self.assertIn(("MISSING_REQUIRED", "O-VAN"), codes(p))
        self.assertEqual({r.status for r in check_all(p) if "O-VAN" in r.pair_id}, {"UNCHECKED"})
        with self.assertRaises(ApprovalError): p.submit_for_review()

    def test_invalid_and_out_of_range(self):
        p = build_project()
        p.set_measurement("O-VAN", "width", "-5 mm")
        p.set_measurement("O-WSH", "height", "9 m")
        self.assertIn(("INVALID_VALUE", "O-VAN"), codes(p))
        self.assertIn(("OUT_OF_RANGE", "O-WSH"), codes(p))

    def test_unknown_dimension_key(self):
        p = build_project()
        with self.assertRaises(KeyError): p.set_measurement("O-VAN", "weight", "10")

    def test_estimate_never_confirmed(self):
        p = build_project()
        p.set_measurement("O-VAN", "width", "800", Source.ESTIMATED_PHOTO)
        self.assertIn(("NOT_MEASURED", "O-VAN"), codes(p))
        self.assertFalse(p.dims_confirmed(p.instances["O-VAN"]))
        res = {r.pair_id: r.status for r in check_all(p)}
        self.assertEqual(res["O-VAN@room"], "UNCHECKED")
        with self.assertRaises(ApprovalError): p.submit_for_review()

    def test_missing_photo_and_annotation(self):
        p = build_project(complete=False)
        c = codes(p)
        self.assertIn(("MISSING_PHOTO", "O-VAN"), c)
        self.assertIn(("MISSING_ANNOTATION", "O-WSH"), c)

    def test_unit_mix_equal_geometry(self):
        a, b = build_project(), build_project()
        b.set_measurement("O-VAN", "width", "29.5276 in")  # ~750.0 mm
        self.assertAlmostEqual(float(b.instances["O-VAN"].measurements["width"].mm), 750.0, delta=0.01)
        self.assertEqual(b.instances["O-VAN"].measurements["width"].original_input, "29.5276 in")


class Interference(unittest.TestCase):
    def test_base_case_pass(self):
        r = check_all(build_project())
        self.assertEqual(overall(r), "PASS", [x for x in r if x.status != "PASS"])

    def test_overlap_fail(self):
        p = build_project(); p.place("O-WSH", "700", "0")
        st = {x.pair_id: x.status for x in check_all(p)}
        self.assertEqual(st["O-VAN|O-WSH"], "FAIL")

    def test_clearance_fail_and_boundary(self):
        p = build_project()
        p.place("O-WSH", "769", "0")   # gap 19 < 20
        self.assertEqual({x.pair_id: x.status for x in check_all(p)}["O-VAN|O-WSH"], "FAIL")
        p.place("O-WSH", "770", "0")   # gap 20 == 20
        self.assertEqual({x.pair_id: x.status for x in check_all(p)}["O-VAN|O-WSH"], "PASS")

    def test_outside_room_fail(self):
        p = build_project(); p.place("O-WSH", "1900", "0")
        self.assertEqual({x.pair_id: x.status for x in check_all(p)}["O-WSH@room"], "FAIL")

    def test_rotation_swaps_footprint(self):
        p = build_project(); p.place("O-WSH", "1000", "0", rotation_deg=90)
        # footprint becomes 600x640 -> still inside; place so rotated depth exceeds room
        p.place("O-WSH", "1000", "1300", rotation_deg=90)
        self.assertEqual({x.pair_id: x.status for x in check_all(p)}["O-WSH@room"], "FAIL")

    def test_no_clearance_defined_is_unchecked_not_pass(self):
        from dataclasses import replace
        p = build_project()
        d = p.catalog.get("wall-cabinet"); p.catalog._defs["wall-cabinet"][0] = replace(d, clearance_mm=None)
        st = {x.pair_id: x.status for x in check_all(p)}
        self.assertEqual(st["O-VAN|O-WCB"], "UNCHECKED")
        self.assertEqual(overall(check_all(p)), "INCOMPLETE")

    def test_vertical_separation_allows_stacking(self):
        r = {x.pair_id: x for x in check_all(build_project())}
        self.assertEqual(r["O-VAN|O-WCB"].status, "PASS")


class Approval(unittest.TestCase):
    def ready(self):
        p = build_project(); p.submit_for_review(); return p

    def test_approve_and_hash_bound(self):
        p = self.ready(); a = p.approve("Isa")
        self.assertIs(p.status, Status.APPROVED)
        self.assertIsNotNone(p.current_approval())
        self.assertEqual(a.content_hash, p.content_hash())

    def test_requires_review_and_named_approver(self):
        p = build_project()
        with self.assertRaises(ApprovalError): p.approve("Isa")
        p.submit_for_review()
        with self.assertRaises(ApprovalError): p.approve("  ")

    def test_fail_cannot_be_approved_even_with_waiver(self):
        p = build_project(); p.place("O-WSH", "700", "0"); p.submit_for_review()
        with self.assertRaises(ApprovalError): p.approve("Isa", {"O-VAN|O-WSH": "ok"})

    def test_unchecked_needs_reasoned_waiver(self):
        from dataclasses import replace
        p = build_project()
        d = p.catalog.get("wall-cabinet"); p.catalog._defs["wall-cabinet"][0] = replace(d, clearance_mm=None)
        p.submit_for_review()
        with self.assertRaises(ApprovalError): p.approve("Isa")
        a = p.approve("Isa", {"O-VAN|O-WCB": "clearance not defined; visually confirmed on site"})
        self.assertIn("O-VAN|O-WCB", manifest(p)["waivers"])

    def test_change_after_approval_invalidates(self):
        p = self.ready(); p.approve("Isa")
        v = p.data_version
        p.set_measurement("O-VAN", "width", "751")
        self.assertEqual(p.data_version, v + 1)
        self.assertIs(p.status, Status.DRAFT)
        self.assertIsNone(p.current_approval())
        self.assertFalse(p.approvals[-1].valid)
        self.assertIn("changed after approval", p.approvals[-1].invalidated_reason)
        self.assertTrue(manifest(p)["status_note"].startswith("UNAPPROVED"))

    def test_reapproval_after_change(self):
        p = self.ready(); p.approve("Isa"); p.set_measurement("O-VAN", "width", "751")
        p.submit_for_review(); p.approve("Isa")
        self.assertEqual(len([a for a in p.approvals if a.valid]), 1)


class Outputs(unittest.TestCase):
    def test_unapproved_is_marked_everywhere(self):
        p = build_project()
        self.assertIn("UNAPPROVED PREVIEW", svg_plan(p))
        self.assertFalse(manifest(p)["approved"])

    def test_approved_not_marked(self):
        p = build_project(); p.submit_for_review(); p.approve("Isa")
        self.assertNotIn("UNAPPROVED", svg_plan(p)); self.assertTrue(manifest(p)["approved"])

    def test_unconfirmed_object_not_drawn(self):
        p = build_project(); p.set_measurement("O-VAN", "width", "800", Source.ESTIMATED_PHOTO)
        self.assertIn("O-VAN: not drawn", svg_plan(p))

    def test_export_failure_then_rerun_idempotent(self):
        p = build_project(); p.submit_for_review(); p.approve("Isa")
        with tempfile.TemporaryDirectory() as t:
            blocked = Path(t) / "blocked"; blocked.write_text("i am a file, not a dir")
            with self.assertRaises((ExportError, OSError)): export_all(p, blocked / "sub")
            out = Path(t) / "out"
            first = {f.name: f.read_bytes() for f in export_all(p, out)}
            second = {f.name: f.read_bytes() for f in export_all(p, out)}
            self.assertEqual(first, second)
            self.assertFalse(list(out.glob("*.tmp")))

    def test_failed_write_leaves_no_partial(self):
        from hoa_field import export
        with tempfile.TemporaryDirectory() as t:
            target = Path(t) / "dir"; target.mkdir()   # os.replace(file -> dir) fails
            with self.assertRaises(ExportError): export.atomic_write(target, "x")
            self.assertEqual(list(Path(t).glob("*.tmp")), [])

    def test_obj_valid_faces(self):
        from hoa_field.export import obj_model
        txt = obj_model(build_project()); v = sum(l.startswith("v ") for l in txt.splitlines())
        mx = max(int(i) for l in txt.splitlines() if l.startswith("f ") for i in l.split()[1:])
        self.assertEqual((v, mx), (24, 24))


class SceneTests(unittest.TestCase):
    def test_requires_approval(self):
        p = build_project()
        with self.assertRaises(SceneError): derive_scene(p, "S1")
        s = derive_scene(p, "S1", allow_unapproved_preview=True)
        self.assertIn("UNAPPROVED", s.preview_label)

    def test_derived_scene_does_not_mutate_source(self):
        p = build_project(); p.submit_for_review(); p.approve("Isa")
        h = p.content_hash(); s = derive_scene(p, "S1")
        s.explode_object("O-WCB", "0", "0", "300"); s.section_plane = {"axis": "y", "at_mm": "275"}
        s.add_camera_key(0.0, [3000, 1500, 2000], [375, 275, 400])
        self.assertEqual(p.content_hash(), h)
        self.assertTrue(s.verify_integrity()); self.assertEqual(s.source_hash, h)
        s.source_snapshot["objects"]["O-VAN"]["measurements"]["width"]["mm"] = "1"  # tamper
        self.assertFalse(s.verify_integrity())

    def test_source_change_leaves_scene_stale_detectable(self):
        p = build_project(); p.submit_for_review(); p.approve("Isa"); s = derive_scene(p, "S1")
        p.set_measurement("O-VAN", "width", "760")
        self.assertNotEqual(s.source_hash, p.content_hash())


if __name__ == "__main__":
    unittest.main()
