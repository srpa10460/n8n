"""Object Catalog: client-extensible, append-only versioned definitions."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path

AXES = ("x", "y", "z")


@dataclass(frozen=True)
class DimensionSpec:
    key: str
    label: str
    required: bool
    axis: str            # x=width, y=depth, z=height of the box shape template
    datum: str           # measurement reference point (e.g. "left outer edge to right outer edge")
    method: str          # e.g. "steel tape", "laser"
    tolerance_mm: Decimal  # allowed measurement tolerance
    min_mm: Decimal
    max_mm: Decimal
    source: str = "client-defined"  # provenance of this spec


SIDES = ("front", "back", "left", "right", "top")
SPACE_KINDS = ("service", "opening")


@dataclass(frozen=True)
class ServiceSpace:
    """Space that must stay free of other objects. Depth is a client/spec-supplied input;
    `basis` (where the number comes from) is mandatory - the system never fills it in."""
    kind: str        # service (work/maintenance) | opening (door/drawer sweep)
    side: str        # front|back|left|right|top  (front faces +y at rotation 0)
    depth_mm: Decimal
    basis: str


@dataclass(frozen=True)
class ObjectDefinition:
    definition_id: str
    name: str
    category: str
    dimensions: tuple[DimensionSpec, ...]
    shape_template: str = "box"
    required_photos: tuple[str, ...] = ()
    required_annotations: tuple[str, ...] = ()
    required_spaces: tuple[ServiceSpace, ...] = ()
    has_opening: bool = False   # door/drawer: needs an "opening" space, else reported UNCHECKED
    version: int = 0  # assigned by Catalog.publish

    def dim(self, key: str) -> DimensionSpec:
        for d in self.dimensions:
            if d.key == key:
                return d
        raise KeyError(key)

    def validate_definition(self) -> None:
        keys = [d.key for d in self.dimensions]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate dimension keys")
        if self.shape_template == "box":
            axes = sorted(d.axis for d in self.dimensions if d.required)
            if axes != list(AXES):
                raise ValueError("box template needs exactly one required dimension per axis x,y,z")
        else:
            raise ValueError(f"unsupported shape_template: {self.shape_template}")
        for sp in self.required_spaces:
            if sp.kind not in SPACE_KINDS or sp.side not in SIDES or sp.depth_mm <= 0 or not sp.basis.strip():
                raise ValueError(f"bad required space (kind/side/depth>0/basis needed): {sp}")
        for d in self.dimensions:
            if d.axis not in AXES or d.min_mm <= 0 or d.max_mm <= d.min_mm or d.tolerance_mm < 0:
                raise ValueError(f"bad dimension spec: {d.key}")


def _enc(o):
    if isinstance(o, Decimal):
        return str(o)
    raise TypeError(type(o))


class Catalog:
    """Published versions are immutable; updating a definition appends a new version."""

    def __init__(self) -> None:
        self._defs: dict[str, list[ObjectDefinition]] = {}

    def publish(self, d: ObjectDefinition) -> ObjectDefinition:
        d.validate_definition()
        versions = self._defs.setdefault(d.definition_id, [])
        new = ObjectDefinition(**{**d.__dict__, "version": len(versions) + 1})
        versions.append(new)
        return new

    def get(self, definition_id: str, version: int | None = None) -> ObjectDefinition:
        versions = self._defs.get(definition_id)
        if not versions:
            raise KeyError(f"unknown definition {definition_id}")
        if version is None:
            return versions[-1]
        if not 1 <= version <= len(versions):
            raise KeyError(f"unknown version {version} of {definition_id}")
        return versions[version - 1]

    def to_dict(self) -> dict:
        return json.loads(json.dumps({k: [asdict(v) for v in vs] for k, vs in self._defs.items()}, default=_enc))

    @classmethod
    def from_dict(cls, data: dict) -> "Catalog":
        c = cls()
        for k, vs in data.items():
            for v in vs:
                dims = tuple(
                    DimensionSpec(**{**d, "tolerance_mm": Decimal(d["tolerance_mm"]),
                                     "min_mm": Decimal(d["min_mm"]), "max_mm": Decimal(d["max_mm"])})
                    for d in v["dimensions"])
                sps = tuple(ServiceSpace(**{**x, "depth_mm": Decimal(x["depth_mm"])})
                            for x in v.get("required_spaces", []))
                c._defs.setdefault(k, []).append(ObjectDefinition(
                    **{**v, "dimensions": dims, "required_spaces": sps,
                       "required_photos": tuple(v["required_photos"]),
                       "required_annotations": tuple(v["required_annotations"])}))
        return c

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))

    @classmethod
    def load(cls, path: Path) -> "Catalog":
        return cls.from_dict(json.loads(path.read_text()))

    def merge_definitions(self, other: dict) -> None:
        """Server-side: add versions from a client catalog dict. Existing id@version must be identical."""
        theirs = Catalog.from_dict(other)
        for k, vs in theirs._defs.items():
            mine = self._defs.setdefault(k, [])
            for v in vs:
                if v.version <= len(mine):
                    if mine[v.version - 1] != v:
                        raise ValueError(f"catalog conflict: {k}@v{v.version} differs from server")
                elif v.version == len(mine) + 1:
                    mine.append(v)
                else:
                    raise ValueError(f"catalog gap: {k}@v{v.version} but server has {len(mine)} versions")


def definition_from_dict(d: dict) -> ObjectDefinition:
    """Build a definition from plain JSON (UI/API input). Raises ValueError/KeyError on bad input."""
    dims = tuple(DimensionSpec(
        key=x["key"], label=x.get("label") or x["key"], required=bool(x.get("required", True)),
        axis=x["axis"], datum=x["datum"], method=x["method"], tolerance_mm=Decimal(str(x["tolerance_mm"])),
        min_mm=Decimal(str(x["min_mm"])), max_mm=Decimal(str(x["max_mm"])), source=x.get("source") or "client-defined")
        for x in d["dimensions"])
    sps = tuple(ServiceSpace(x["kind"], x["side"], Decimal(str(x["depth_mm"])), x.get("basis", ""))
                for x in d.get("required_spaces", []))
    if not d.get("definition_id") or not d.get("name"):
        raise ValueError("definition_id and name required")
    return ObjectDefinition(d["definition_id"], d["name"], d.get("category", ""), dims,
                            d.get("shape_template", "box"), tuple(d.get("required_photos", [])),
                            tuple(d.get("required_annotations", [])), sps, bool(d.get("has_opening", False)))
