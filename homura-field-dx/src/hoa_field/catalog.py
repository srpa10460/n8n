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


@dataclass(frozen=True)
class ObjectDefinition:
    definition_id: str
    name: str
    category: str
    dimensions: tuple[DimensionSpec, ...]
    shape_template: str = "box"
    required_photos: tuple[str, ...] = ()
    required_annotations: tuple[str, ...] = ()
    # required clearance in mm; None => undefined (interference clearance stays UNCHECKED)
    clearance_mm: Decimal | None = None
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

    def save(self, path: Path) -> None:
        data = {k: [asdict(v) for v in vs] for k, vs in self._defs.items()}
        path.write_text(json.dumps(data, default=_enc, ensure_ascii=False, indent=2, sort_keys=True))

    @classmethod
    def load(cls, path: Path) -> "Catalog":
        c = cls()
        for k, vs in json.loads(path.read_text()).items():
            for v in vs:
                dims = tuple(
                    DimensionSpec(**{**d, "tolerance_mm": Decimal(d["tolerance_mm"]),
                                     "min_mm": Decimal(d["min_mm"]), "max_mm": Decimal(d["max_mm"])})
                    for d in v["dimensions"])
                cl = Decimal(v["clearance_mm"]) if v["clearance_mm"] is not None else None
                c._defs.setdefault(k, []).append(ObjectDefinition(
                    **{**v, "dimensions": dims, "clearance_mm": cl,
                       "required_photos": tuple(v["required_photos"]),
                       "required_annotations": tuple(v["required_annotations"])}))
        return c
