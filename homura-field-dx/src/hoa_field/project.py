"""Project / instances / measurements / validation / review-approval state.

Measured values are the dimensional source of truth. Photo estimates are stored separately
(source=ESTIMATED_PHOTO), never counted as confirmed, and block approval.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from .catalog import Catalog, ObjectDefinition
from .units import parse_length


class Source(str, Enum):
    MEASURED = "MEASURED"
    ESTIMATED_PHOTO = "ESTIMATED_PHOTO"


class Status(str, Enum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"


class ApprovalError(RuntimeError):
    pass


@dataclass
class Measurement:
    mm: Decimal
    source: Source
    original_input: str      # what the operator typed (unit preserved for traceability)
    measured_by: str = ""


@dataclass
class Placement:
    x_mm: Decimal            # plan position of footprint min corner (before rotation)
    y_mm: Decimal
    z_mm: Decimal = Decimal(0)   # bottom height (e.g. wall-cabinet mounting height)
    rotation_deg: int = 0    # 0/90/180/270


@dataclass
class ObjectInstance:
    object_id: str
    definition_id: str
    definition_version: int  # pinned: later catalog versions never change this instance's meaning
    label: str
    measurements: dict[str, Measurement] = field(default_factory=dict)
    photo_ids: list[str] = field(default_factory=list)       # Asset IDs, tagged by requirement
    photo_tags: dict[str, str] = field(default_factory=dict)  # asset_id -> required photo tag
    annotations: dict[str, str] = field(default_factory=dict)
    placement: Placement | None = None


@dataclass(frozen=True)
class Issue:
    severity: str  # ERROR | WARN
    code: str
    object_id: str
    detail: str


@dataclass
class Approval:
    approved_version: int
    content_hash: str
    approver: str
    at: str
    waivers: dict[str, str]
    valid: bool = True
    invalidated_reason: str = ""


class Project:
    def __init__(self, project_id: str, catalog: Catalog, room_w: str, room_d: str, room_h: str):
        self.project_id = project_id
        self.catalog = catalog
        self.room = {"w": parse_length(room_w), "d": parse_length(room_d), "h": parse_length(room_h)}
        self.instances: dict[str, ObjectInstance] = {}
        self.data_version = 1
        self.status = Status.DRAFT
        self.approvals: list[Approval] = []
        self.history: list[str] = ["v1 created"]

    # ---- mutation (every change bumps data_version; approved data is never edited in place)
    def _touch(self, msg: str) -> None:
        if self.status is Status.APPROVED:
            for a in self.approvals:
                if a.valid:
                    a.valid, a.invalidated_reason = False, f"changed after approval: {msg}"
        self.status = Status.DRAFT
        self.data_version += 1
        self.history.append(f"v{self.data_version} {msg}")

    def add_instance(self, object_id: str, definition_id: str, label: str,
                     definition_version: int | None = None) -> ObjectInstance:
        d = self.catalog.get(definition_id, definition_version)  # pins current version if None
        inst = ObjectInstance(object_id, definition_id, d.version, label)
        self.instances[object_id] = inst
        self._touch(f"add {object_id}")
        return inst

    def set_measurement(self, object_id: str, key: str, text: str,
                        source: Source = Source.MEASURED, by: str = "", default_unit: str = "mm") -> None:
        inst = self.instances[object_id]
        inst.definition_version  # noqa: B018 (pinned)
        self.catalog.get(inst.definition_id, inst.definition_version).dim(key)  # KeyError if not in def
        inst.measurements[key] = Measurement(parse_length(text, default_unit), source, text, by)
        self._touch(f"measure {object_id}.{key}")

    def place(self, object_id: str, x: str, y: str, z: str = "0", rotation_deg: int = 0) -> None:
        if rotation_deg not in (0, 90, 180, 270):
            raise ValueError("rotation must be 0/90/180/270")
        self.instances[object_id].placement = Placement(
            parse_length(x), parse_length(y), parse_length(z), rotation_deg)
        self._touch(f"place {object_id}")

    def add_photo(self, object_id: str, asset_id: str, tag: str) -> None:
        i = self.instances[object_id]
        i.photo_ids.append(asset_id)
        i.photo_tags[asset_id] = tag
        self._touch(f"photo {object_id}:{asset_id}")

    def annotate(self, object_id: str, key: str, text: str) -> None:
        self.instances[object_id].annotations[key] = text
        self._touch(f"annotate {object_id}.{key}")

    # ---- definition access
    def definition(self, inst: ObjectInstance) -> ObjectDefinition:
        return self.catalog.get(inst.definition_id, inst.definition_version)

    # ---- validation
    def validate(self) -> list[Issue]:
        out: list[Issue] = []
        for inst in self.instances.values():
            d = self.definition(inst)
            for s in d.dimensions:
                m = inst.measurements.get(s.key)
                if m is None:
                    if s.required:
                        out.append(Issue("ERROR", "MISSING_REQUIRED", inst.object_id, s.key))
                    continue
                if m.mm <= 0:
                    out.append(Issue("ERROR", "INVALID_VALUE", inst.object_id, f"{s.key}={m.mm}"))
                elif not (s.min_mm <= m.mm <= s.max_mm):
                    out.append(Issue("ERROR", "OUT_OF_RANGE", inst.object_id,
                                     f"{s.key}={m.mm} not in [{s.min_mm},{s.max_mm}]"))
                if m.source is not Source.MEASURED:
                    out.append(Issue("ERROR", "NOT_MEASURED", inst.object_id,
                                     f"{s.key} is {m.source.value}; enter a measured value"))
            tags = set(inst.photo_tags.values())
            for req in d.required_photos:
                if req not in tags:
                    out.append(Issue("ERROR", "MISSING_PHOTO", inst.object_id, req))
            for req in d.required_annotations:
                if not inst.annotations.get(req):
                    out.append(Issue("ERROR", "MISSING_ANNOTATION", inst.object_id, req))
            if inst.placement is None:
                out.append(Issue("WARN", "NOT_PLACED", inst.object_id, "no placement; excluded from interference"))
        return out

    def dims_confirmed(self, inst: ObjectInstance) -> bool:
        d = self.definition(inst)
        for s in d.dimensions:
            if not s.required:
                continue
            m = inst.measurements.get(s.key)
            if m is None or m.source is not Source.MEASURED or not (s.min_mm <= m.mm <= s.max_mm):
                return False
        return True

    # ---- canonical content + hash
    def snapshot(self) -> dict:
        def meas(m: Measurement):
            return {"mm": str(m.mm), "source": m.source.value, "input": m.original_input}
        return {
            "project_id": self.project_id,
            "room_mm": {k: str(v) for k, v in self.room.items()},
            "objects": {
                oid: {
                    "definition": [i.definition_id, i.definition_version],
                    "label": i.label,
                    "measurements": {k: meas(m) for k, m in sorted(i.measurements.items())},
                    "photos": sorted(i.photo_tags.items()),
                    "annotations": dict(sorted(i.annotations.items())),
                    "placement": None if i.placement is None else {
                        "x": str(i.placement.x_mm), "y": str(i.placement.y_mm),
                        "z": str(i.placement.z_mm), "rot": i.placement.rotation_deg},
                } for oid, i in sorted(self.instances.items())
            },
        }

    def content_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.snapshot(), sort_keys=True).encode()).hexdigest()

    # ---- review / approval
    def submit_for_review(self) -> None:
        errs = [i for i in self.validate() if i.severity == "ERROR"]
        if errs:
            raise ApprovalError(f"validation errors block review: {[(e.code, e.object_id) for e in errs]}")
        self.status = Status.IN_REVIEW

    def approve(self, approver: str, waivers: dict[str, str] | None = None) -> Approval:
        """Human Final Review gate. approver must be a named human; UNCHECKED interference
        pairs need an explicit waiver with a reason, FAIL can never be waived."""
        from .interference import check_all  # local import: avoid cycle
        if self.status is not Status.IN_REVIEW:
            raise ApprovalError("must be IN_REVIEW")
        if not approver.strip():
            raise ApprovalError("approver required")
        waivers = waivers or {}
        res = check_all(self)
        if any(r.status == "FAIL" for r in res):
            raise ApprovalError("interference FAIL cannot be approved")
        for r in res:
            if r.status == "UNCHECKED" and not waivers.get(r.pair_id, "").strip():
                raise ApprovalError(f"unchecked item needs waiver with reason: {r.pair_id}")
        self.status = Status.APPROVED
        a = Approval(self.data_version, self.content_hash(), approver,
                     datetime.now(timezone.utc).isoformat(timespec="seconds"), dict(waivers))
        self.approvals.append(a)
        self.history.append(f"v{self.data_version} approved by {approver}")
        return a

    def current_approval(self) -> Approval | None:
        for a in reversed(self.approvals):
            if a.valid and a.approved_version == self.data_version and a.content_hash == self.content_hash():
                return a
        return None
