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

def bound_approve(p, approver="Isa", waivers=None, kind="DEV_SIMULATED", confirmations=None, **kw):
    """Approve with mandatory version+hash binding (F-2)."""
    return p.approve(
        approver,
        waivers or {},
        kind=kind,
        expect_version=kw.get("expect_version", p.data_version),
        expect_hash=kw.get("expect_hash", p.content_hash()),
        confirmations=confirmations,
    )



def codes(p, sev="ERROR"):
    return {(i.code, i.object_id) for i in p.validate() if i.severity == sev}



def do_approve(p, approver="Isa", waivers=None, kind="DEV_SIMULATED", confirmations=None,
               expect_version=None, expect_hash=None):
    """Test helper: bind expect_version/hash unless the test is deliberately omitting them."""
    return p.approve(
        approver, waivers, kind,
        expect_version=p.data_version if expect_version is None else expect_version,
        expect_hash=p.content_hash() if expect_hash is None else expect_hash,
        confirmations=confirmations,
    )


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
        v2 = p.catalog.publish(replace(d, required_photos=d.required_photos + ("side",)))
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
    def st(self, p):
        return {x.pair_id: x.status for x in check_all(p)}

    def test_base_case_pass(self):
        r = check_all(build_project())
        self.assertEqual(overall(r), "PASS", [x for x in r if x.status not in ("PASS", "INFO")])

    def test_overlap_fail(self):
        p = build_project(); p.place("O-WSH", "700", "0")
        self.assertEqual(self.st(p)["O-VAN|O-WSH#overlap"], "FAIL")

    def test_outside_room_fail(self):
        p = build_project(); p.place("O-WSH", "1900", "0")
        self.assertEqual(self.st(p)["O-WSH@room"], "FAIL")

    def test_rotation_swaps_footprint(self):
        p = build_project(); p.place("O-WSH", "1000", "1300", rotation_deg=90)
        self.assertEqual(self.st(p)["O-WSH@room"], "FAIL")

    def test_service_space_blocked_by_washer(self):
        p = build_project(); p.place("O-WSH", "0", "560")   # inside vanity front 500mm zone (y 550-1050)
        self.assertEqual(self.st(p)["O-VAN#service-front"], "FAIL")

    def test_no_service_space_defined_is_unchecked_not_pass(self):
        from dataclasses import replace
        p = build_project()
        d = p.catalog.get("vanity"); p.catalog._defs["vanity"][0] = replace(d, required_spaces=())
        self.assertEqual(self.st(p)["O-VAN#service"], "UNCHECKED")
        self.assertEqual(overall(check_all(p)), "INCOMPLETE")

    def test_vertical_separation_allows_stacking(self):
        self.assertEqual(self.st(build_project())["O-VAN|O-WCB#overlap"], "PASS")


class Approval(unittest.TestCase):
    def ready(self):
        p = build_project(); p.submit_for_review(); return p

    def test_approve_and_hash_bound(self):
        p = self.ready(); a = do_approve(p, "Isa")
        self.assertIs(p.status, Status.APPROVED)
        self.assertIsNotNone(p.current_approval())
        self.assertEqual(a.content_hash, p.content_hash())

    def test_requires_review_and_named_approver(self):
        p = build_project()
        with self.assertRaises(ApprovalError): do_approve(p, "Isa")
        p.submit_for_review()
        with self.assertRaises(ApprovalError): do_approve(p, "  ")

    def test_fail_cannot_be_approved_even_with_waiver(self):
        p = build_project(); p.place("O-WSH", "700", "0"); p.submit_for_review()
        with self.assertRaises(ApprovalError): do_approve(p, "Isa", {"O-VAN|O-WSH#overlap": "ok"})

    def test_unchecked_needs_reasoned_waiver(self):
        from dataclasses import replace
        p = build_project()
        d = p.catalog.get("vanity"); p.catalog._defs["vanity"][0] = replace(d, required_spaces=())
        p.submit_for_review()
        with self.assertRaises(ApprovalError): do_approve(p, "Isa")
        do_approve(p, "Isa", {"O-VAN#service": "service space not defined; site check by Human"})
        self.assertIn("O-VAN#service", manifest(p)["waivers"])

    def test_change_after_approval_invalidates(self):
        p = self.ready(); do_approve(p, "Isa")
        v = p.data_version
        p.set_measurement("O-VAN", "width", "751")
        self.assertEqual(p.data_version, v + 1)
        self.assertIs(p.status, Status.DRAFT)
        self.assertIsNone(p.current_approval())
        self.assertFalse(p.approvals[-1].valid)
        self.assertIn("changed after approval", p.approvals[-1].invalidated_reason)
        self.assertTrue(manifest(p)["status_note"].startswith("UNAPPROVED"))

    def test_reapproval_after_change(self):
        p = self.ready(); do_approve(p, "Isa"); p.set_measurement("O-VAN", "width", "751")
        p.submit_for_review(); do_approve(p, "Isa")
        self.assertEqual(len([a for a in p.approvals if a.valid]), 1)


class ApprovalBinding(unittest.TestCase):
    def test_stale_version_or_hash_refused(self):
        p = build_project(); p.submit_for_review()
        v, h = p.data_version, p.content_hash()
        with self.assertRaises(ApprovalError): do_approve(p, "Isa", expect_version=v - 1, expect_hash=h)
        with self.assertRaises(ApprovalError): do_approve(p, "Isa", expect_version=v, expect_hash="0" * 64)
        a = do_approve(p, "Isa", expect_version=v, expect_hash=h, kind="HUMAN_FINAL")
        self.assertEqual(a.kind, "HUMAN_FINAL")

    def test_kind_distinguished_in_outputs(self):
        p = build_project(); p.submit_for_review(); do_approve(p, "dev")
        self.assertIn("DEV SIMULATED", svg_plan(p)); self.assertIn("DEV SIMULATED", manifest(p)["status_note"])
        p2 = build_project(); p2.submit_for_review(); do_approve(p2, "Isa", kind="HUMAN_FINAL")
        self.assertNotIn("DEV SIMULATED", svg_plan(p2))

    def test_unknown_kind(self):
        p = build_project(); p.submit_for_review()
        with self.assertRaises(ApprovalError): do_approve(p, "Isa", kind="MAYBE")

    def test_persistence_roundtrip(self):
        p = build_project(); p.submit_for_review(); do_approve(p, "dev")
        from hoa_field.project import Project
        q = Project.from_dict(json.loads(json.dumps(p.to_dict())), p.catalog)
        self.assertEqual(q.content_hash(), p.content_hash())
        self.assertIsNotNone(q.current_approval())


class EngineView(unittest.TestCase):
    def test_spec_source_not_overwritten_by_measurement_source(self):
        from hoa_field.engine import call
        p = build_project(); st = {"catalog": p.catalog.to_dict(), "project": p.to_dict()}
        dims = call("detail", st, {})["result"]["detail"]["instances"][0]["dims"]
        self.assertTrue(all(d["source"] == "client-defined" and d["meas_source"] == "MEASURED" for d in dims), dims[0])


class PhotoRules(unittest.TestCase):
    def test_same_photo_cannot_be_attached_twice_to_one_object(self):
        p = build_project(complete=False)
        p.add_photo("O-VAN", "A-1", "front", {"sha256": "a"})
        with self.assertRaises(ValueError): p.add_photo("O-VAN", "A-1", "wall-context", {"sha256": "a"})
        self.assertEqual(p.instances["O-VAN"].photo_tags["A-1"], "front")   # not silently retagged
        p.add_photo("O-WCB", "A-1", "front", {"sha256": "a"})                  # other object may reference the same asset


class Outputs(unittest.TestCase):
    def test_unapproved_is_marked_everywhere(self):
        p = build_project()
        self.assertIn("UNAPPROVED PREVIEW", svg_plan(p))
        self.assertFalse(manifest(p)["approved"])

    def test_approved_not_marked(self):
        p = build_project(); p.submit_for_review(); do_approve(p, "Isa")
        self.assertNotIn("UNAPPROVED", svg_plan(p)); self.assertTrue(manifest(p)["approved"])

    def test_unconfirmed_object_not_drawn(self):
        p = build_project(); p.set_measurement("O-VAN", "width", "800", Source.ESTIMATED_PHOTO)
        self.assertIn("O-VAN: not drawn", svg_plan(p))

    def test_export_failure_then_rerun_idempotent(self):
        p = build_project(); p.submit_for_review(); do_approve(p, "Isa")
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
        p = build_project(); p.submit_for_review(); do_approve(p, "Isa")
        h = p.content_hash(); s = derive_scene(p, "S1")
        s.explode_object("O-WCB", "0", "0", "300"); s.section_plane = {"axis": "y", "at_mm": "275"}
        s.add_camera_key(0.0, [3000, 1500, 2000], [375, 275, 400])
        self.assertEqual(p.content_hash(), h)
        self.assertTrue(s.verify_integrity()); self.assertEqual(s.source_hash, h)
        s.source_snapshot["objects"]["O-VAN"]["measurements"]["width"]["mm"] = "1"  # tamper
        self.assertFalse(s.verify_integrity())

    def test_source_change_leaves_scene_stale_detectable(self):
        p = build_project(); p.submit_for_review(); do_approve(p, "Isa"); s = derive_scene(p, "S1")
        p.set_measurement("O-VAN", "width", "760")
        self.assertNotEqual(s.source_hash, p.content_hash())




class ApprovalBindingRequired(unittest.TestCase):
    """F-2: expect_version + expect_hash are mandatory (Fail Closed)."""

    def ready(self):
        p = build_project(); p.submit_for_review(); return p

    def test_version_omitted_rejects(self):
        p = self.ready()
        with self.assertRaises(ApprovalError):
            p.approve("Isa", expect_version=None, expect_hash=p.content_hash())

    def test_hash_omitted_rejects(self):
        p = self.ready()
        with self.assertRaises(ApprovalError):
            p.approve("Isa", expect_version=p.data_version, expect_hash=None)

    def test_both_omitted_rejects(self):
        p = self.ready()
        with self.assertRaises(ApprovalError):
            p.approve("Isa")  # both expect_version and expect_hash omitted
    def test_wrong_version_rejects(self):
        p = self.ready()
        with self.assertRaises(ApprovalError):
            do_approve(p, expect_version=p.data_version - 1)

    def test_wrong_hash_rejects(self):
        p = self.ready()
        with self.assertRaises(ApprovalError):
            do_approve(p, expect_hash="0" * 64)

    def test_correct_version_hash_passes(self):
        p = self.ready()
        a = do_approve(p, kind="HUMAN_FINAL")
        self.assertEqual(a.kind, "HUMAN_FINAL")
        self.assertIsNotNone(p.current_approval())

    def test_post_approval_snapshot_change_invalidates(self):
        p = self.ready(); do_approve(p)
        p.set_measurement("O-VAN", "width", "751")
        self.assertIsNone(p.current_approval())
        self.assertFalse(p.approvals[-1].valid)


class EmptyProjectApproval(unittest.TestCase):
    """F-3: empty / incomplete projects cannot be approved."""

    def test_empty_project_rejects(self):
        from hoa_field.project import Project
        cat = build_catalog()
        p = Project("P-EMPTY", cat, "2400 mm", "1800 mm", "2400 mm")
        # empty has no validation ERRORs -> can enter review, but must not approve
        p.submit_for_review()
        with self.assertRaises(ApprovalError):
            do_approve(p, "Isa")

    def test_required_data_missing_rejects_review(self):
        p = build_project(complete=False)
        with self.assertRaises(ApprovalError):
            p.submit_for_review()

    def test_unchecked_without_waiver_rejects(self):
        from dataclasses import replace
        p = build_project()
        d = p.catalog.get("vanity"); p.catalog._defs["vanity"][0] = replace(d, required_spaces=())
        p.submit_for_review()
        with self.assertRaises(ApprovalError):
            do_approve(p, "Isa")
        self.assertEqual(overall(check_all(p)), "INCOMPLETE")

    def test_complete_valid_project_still_approves(self):
        p = build_project(); p.submit_for_review(); do_approve(p, "Isa")
        self.assertIs(p.status, Status.APPROVED)


class CatalogKeyInjection(unittest.TestCase):
    """F-1 / Fail Closed: malicious catalog keys rejected at Engine + Catalog."""

    PAYLOADS = ["'", '"', "<", ">", "&", ");", "//",
                "k',this);window.__pwn=1;//",
                "x onerror=alert(1)",
                "a);evil("]

    def test_engine_measure_rejects_bad_keys(self):
        from hoa_field.engine import call, EngineError
        p = build_project()
        st = {"catalog": p.catalog.to_dict(), "project": p.to_dict()}
        for bad in self.PAYLOADS:
            with self.assertRaises(EngineError, msg=bad):
                call("measure", st, {"object_id": "O-VAN", "key": bad, "value": "1", "unit": "mm",
                                     "source": "MEASURED", "by": "x"})

    def test_engine_annotate_rejects_bad_keys(self):
        from hoa_field.engine import call, EngineError
        p = build_project()
        st = {"catalog": p.catalog.to_dict(), "project": p.to_dict()}
        for bad in self.PAYLOADS:
            with self.assertRaises(EngineError, msg=bad):
                call("annotate", st, {"object_id": "O-VAN", "key": bad, "text": "x"})

    def test_publish_definition_rejects_bad_dimension_key(self):
        from hoa_field.engine import call, EngineError
        st = {"catalog": {}, "project": None}
        payload = {
            "definition_id": "box1", "name": "Box", "category": "t", "shape_template": "box",
            "dimensions": [
                {"key": "k',this);window.__pwn=1;//", "label": "w", "axis": "x", "required": True,
                 "datum": "d", "method": "m", "tolerance_mm": "1", "min_mm": "10", "max_mm": "1000"},
                {"key": "depth", "label": "d", "axis": "y", "required": True,
                 "datum": "d", "method": "m", "tolerance_mm": "1", "min_mm": "10", "max_mm": "1000"},
                {"key": "height", "label": "h", "axis": "z", "required": True,
                 "datum": "d", "method": "m", "tolerance_mm": "1", "min_mm": "10", "max_mm": "1000"},
            ],
            "required_photos": [], "required_annotations": [], "required_spaces": [],
        }
        with self.assertRaises((EngineError, ValueError)):
            out = call("publish_definition", st, payload)
            if out.get("error"):
                raise EngineError(out["error"])

    def test_engine_approve_requires_version_hash(self):
        from hoa_field.engine import call, EngineError
        from hoa_field.engine import REQUIRED_CONFIRMATIONS
        p = build_project(); p.submit_for_review()
        st = {"catalog": p.catalog.to_dict(), "project": p.to_dict()}
        base = {"approver": "Isa", "kind": "HUMAN_FINAL", "confirmations": list(REQUIRED_CONFIRMATIONS), "waivers": {}}
        with self.assertRaises(EngineError):
            call("approve", st, {**base})  # both omitted
        with self.assertRaises(EngineError):
            call("approve", st, {**base, "expect_hash": p.content_hash()})  # version omitted
        with self.assertRaises(EngineError):
            call("approve", st, {**base, "expect_version": p.data_version})  # hash omitted
        out = call("approve", st, {**base, "expect_version": p.data_version, "expect_hash": p.content_hash()})
        self.assertEqual(out["result"]["detail"]["status"], "APPROVED")


if __name__ == "__main__":
    unittest.main()
