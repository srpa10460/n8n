"""Representative case 1 (SYNTHETIC, not client data): washroom refit with 3 objects."""
from decimal import Decimal as D

from .catalog import Catalog, DimensionSpec, ObjectDefinition, ServiceSpace
from .project import Project, Source


SYN = "SYNTHETIC test value for dev case; not a design standard or manufacturer spec"


def _dims(wmax="3000", dmax="1500", hmax="2500"):
    mk = lambda k, l, ax, mx, dat: DimensionSpec(
        k, l, True, ax, dat, "steel tape (1 mm graduation)", D("2"), D("10"), D(mx))
    return (mk("width", "Width", "x", wmax, "outer left edge to outer right edge, at mid-height"),
            mk("depth", "Depth", "y", dmax, "wall surface to front-most point, at mid-width"),
            mk("height", "Height", "z", hmax, "bottom edge to top edge, at mid-width"))


def build_catalog() -> Catalog:
    c = Catalog()
    c.publish(ObjectDefinition("vanity", "Vanity unit", "sanitary", _dims(),
                               required_photos=("front", "wall-context"),
                               required_annotations=("plumbing-position",),
                               required_spaces=(ServiceSpace("service", "front", D("500"), SYN),)))
    c.publish(ObjectDefinition("wall-cabinet", "Wall cabinet", "storage", _dims(),
                               required_photos=("front",), has_opening=True,
                               required_spaces=(ServiceSpace("opening", "front", D("300"), SYN),)))
    c.publish(ObjectDefinition("washer", "Washing machine", "appliance", _dims(),
                               required_photos=("front", "wall-context"),
                               required_annotations=("drain-position",),
                               required_spaces=(ServiceSpace("service", "front", D("100"), SYN),)))
    return c


def build_project(complete: bool = True) -> Project:
    p = Project("P-0001", build_catalog(), "2400 mm", "1800 mm", "2400 mm")
    spec = [("O-VAN", "vanity", "Vanity", ("750", "550", "850"), ("0", "0", "0")),
            ("O-WCB", "wall-cabinet", "Wall cabinet", ("750", "200", "700"), ("0", "0", "1500")),
            ("O-WSH", "washer", "Washer", ("0.64 m", "600", "1000"), ("1000", "0", "0"))]
    for oid, did, label, dims, pos in spec:
        p.add_instance(oid, did, label)
        for k, v in zip(("width", "depth", "height"), dims):
            p.set_measurement(oid, k, v, Source.MEASURED, by="field-staff-01")
        p.place(oid, *pos)
        if complete:
            p.add_photo(oid, f"A-{oid}-front", "front")
            if did != "wall-cabinet":
                p.add_photo(oid, f"A-{oid}-ctx", "wall-context")
    if complete:
        p.annotate("O-VAN", "plumbing-position", "supply 120 mm from left wall, centre height 500 mm")
        p.annotate("O-WSH", "drain-position", "drain 80 mm from right edge")
    return p
