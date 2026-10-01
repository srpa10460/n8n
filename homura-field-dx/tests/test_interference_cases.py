"""Interference case table: expected vs actual. Writes evidence/interference_cases.md."""
import sys, unittest
from decimal import Decimal as D
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hoa_field.catalog import Catalog, DimensionSpec, ObjectDefinition, ServiceSpace
from hoa_field.interference import check_all
from hoa_field.project import Project, Source

BASIS = "test input (synthetic)"


def mkdims():
    return tuple(DimensionSpec(k, k, True, ax, "datum", "tape", D(1), D(1), D(5000), "test")
                 for k, ax in (("w", "x"), ("d", "y"), ("h", "z")))


def catalog():
    c = Catalog()
    c.publish(ObjectDefinition("blk", "plain", "t", mkdims()))
    c.publish(ObjectDefinition("svc", "front service 500", "t", mkdims(),
                               required_spaces=(ServiceSpace("service", "front", D(500), BASIS),)))
    c.publish(ObjectDefinition("door", "door obj", "t", mkdims(), has_opening=True))
    return c


def proj(a_def, a_pos, b_pos, a_rot=0, b_est=False):
    p = Project("T", catalog(), "5000", "5000", "3000")
    for oid, did, pos, rot in (("A", a_def, a_pos, a_rot), ("B", "blk", b_pos, 0)):
        p.add_instance(oid, did, oid)
        for k in "w", "d", "h":
            src = Source.ESTIMATED_PHOTO if (oid == "B" and b_est) else Source.MEASURED
            p.set_measurement(oid, k, "1000", src)
        p.place(oid, *pos, rotation_deg=rot)
    return p


def get(res, suffix):
    return [r for r in res if r.pair_id.endswith(suffix)]


Z = "0"
CASES = [
    # name, builder, (check suffix, expected status, expected text fragment)
    ("contact (face touching)", lambda: proj("blk", ("0", "0", Z), ("1000", "0", Z)),
     [("#overlap", "PASS", "contact"), ("#distance", "INFO", "distance 0.000")]),
    ("overlap x by 100", lambda: proj("blk", ("0", "0", Z), ("900", "0", Z)),
     [("#overlap", "FAIL", "100.000/1000.000/1000.000"), ("#distance", "INFO", "distance 0.000")]),
    ("single-axis gap 300", lambda: proj("blk", ("0", "0", Z), ("1300", "0", Z)),
     [("#overlap", "PASS", "no overlap"), ("#distance", "INFO", "distance 300.000")]),
    ("diagonal gap 30/40 (Euclid 50, per-axis max 40)", lambda: proj("blk", ("0", "0", Z), ("1030", "1040", Z)),
     [("#overlap", "PASS", "no overlap"), ("#distance", "INFO", "distance 50.000")]),
    ("stacked above, gap 200", lambda: proj("blk", ("0", "0", Z), ("0", "0", "1200")),
     [("#overlap", "PASS", "no overlap"), ("#distance", "INFO", "distance 200.000")]),
    ("stacked, contact z", lambda: proj("blk", ("0", "0", Z), ("0", "0", "1000")),
     [("#overlap", "PASS", "contact")]),
    ("vertical partial overlap 100", lambda: proj("blk", ("0", "0", Z), ("0", "0", "900")),
     [("#overlap", "FAIL", "1000.000/1000.000/100.000")]),
    ("service space blocked (B at y=1300 inside 500 zone)", lambda: proj("svc", ("0", "0", Z), ("0", "1300", Z)),
     [("A#service-front", "FAIL", "blocked by B")]),
    ("service space free, B touching zone edge y=1500", lambda: proj("svc", ("0", "0", Z), ("0", "1500", Z)),
     [("A#service-front", "PASS", "space free")]),
    ("service zone vs diagonal object outside zone footprint", lambda: proj("svc", ("0", "0", Z), ("1000", "1000", Z)),
     [("A#service-front", "PASS", "space free")]),
    ("service undefined -> UNCHECKED, not PASS", lambda: proj("blk", ("0", "0", Z), ("0", "3000", Z)),
     [("A#service", "UNCHECKED", "no required service space")]),
    ("rotation 90: front faces -x, B at x=200 blocks", lambda: proj("svc", ("600", "0", Z), ("200", "0", Z), a_rot=90),
     [("A#service-front", "FAIL", "blocked by B")]),
    ("rotation 180: front faces -y, zone leaves room", lambda: proj("svc", ("0", "0", Z), ("3000", "3000", Z), a_rot=180),
     [("A#service-front", "FAIL", "outside room")]),
    ("B estimated (unconfirmed) -> overlap/service UNCHECKED", lambda: proj("svc", ("0", "0", Z), ("0", "3000", Z), b_est=True),
     [("#overlap", "UNCHECKED", "unconfirmed"), ("A#service-front", "UNCHECKED", "unconfirmed objects exist")]),
    ("door object without opening envelope -> UNCHECKED", lambda: proj("door", ("0", "0", Z), ("0", "3000", Z)),
     [("A#opening", "UNCHECKED", "without a declared opening")]),
]


class Cases(unittest.TestCase):
    def test_table(self):
        rows, bad = [], []
        for name, build, exps in CASES:
            res = check_all(build())
            for suffix, st, frag in exps:
                got = get(res, suffix)
                actual = got[0] if got else None
                ok = bool(actual) and actual.status == st and frag in actual.reason
                rows.append((name, suffix, st, frag, actual.status if actual else "-", actual.reason if actual else "-", ok))
                if not ok:
                    bad.append(rows[-1])
        md = ["# Interference case table (expected vs actual)", "",
              "| case | check | expected | expected text | actual | actual text | match |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            md.append("| " + " | ".join(str(x).replace("|", "/") for x in r[:6]) + f" | {'OK' if r[6] else 'NG'} |")
        out = ROOT / "evidence" / "interference_cases.md"
        out.write_text("\n".join(md) + "\n")
        self.assertEqual(bad, [])

    def test_non_box_shape_cannot_be_registered(self):
        from dataclasses import replace
        c = catalog()
        with self.assertRaises(ValueError):
            c.publish(replace(c.get("blk"), definition_id="cyl", shape_template="cylinder"))

    def test_space_without_basis_rejected(self):
        from dataclasses import replace
        c = catalog()
        with self.assertRaises(ValueError):
            c.publish(replace(c.get("blk"), definition_id="x",
                              required_spaces=(ServiceSpace("service", "front", D(500), " "),)))


if __name__ == "__main__":
    unittest.main()
