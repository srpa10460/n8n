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
    kind: str = "DEV_SIMULATED"   # DEV_SIMULATED (development test) | HUMAN_FINAL (real case review by a named Human)
    confirmations: list[str] = field(default_factory=list)
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
        self.assets: dict[str, dict] = {}   # asset_id -> {filename, sha256, bytes}
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

    def add_photo(self, object_id: str, asset_id: str, tag: str, meta: dict | None = None) -> None:
        i = self.instances[object_id]
        if asset_id in i.photo_tags:
            raise ValueError(f"this exact photo is already attached to {object_id} as '{i.photo_tags[asset_id]}'; "
                             "use a different photo file for another tag")
        if meta:
            self.assets[asset_id] = meta
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
                st, detail = self.dimension_status(inst, s.key)
                if st == "MISSING" and s.required:
                    out.append(Issue("ERROR", "MISSING_REQUIRED", inst.object_id, s.key))
                elif st == "INVALID":
                    code = "INVALID_VALUE" if detail.startswith("nonpositive") else "OUT_OF_RANGE"
                    out.append(Issue("ERROR", code, inst.object_id, f"{s.key}: {detail}"))
                elif st == "ESTIMATED":
                    out.append(Issue("ERROR", "NOT_MEASURED", inst.object_id,
                                     f"{s.key} is {inst.measurements[s.key].source.value}; enter a measured value"))
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

    def dimension_status(self, inst: ObjectInstance, key: str) -> tuple[str, str]:
        """Single source of truth for a dimension's state: MISSING | INVALID | ESTIMATED | MEASURED."""
        s = self.definition(inst).dim(key)
        m = inst.measurements.get(key)
        if m is None:
            return "MISSING", ""
        if m.mm <= 0:
            return "INVALID", f"nonpositive value {m.mm} mm"
        if not (s.min_mm <= m.mm <= s.max_mm):
            return "INVALID", f"{m.mm} mm not in [{s.min_mm},{s.max_mm}]"
        if m.source is not Source.MEASURED:
            return "ESTIMATED", m.source.value
        return "MEASURED", ""

    def dims_confirmed(self, inst: ObjectInstance) -> bool:
        return all(self.dimension_status(inst, s.key)[0] == "MEASURED"
                   for s in self.definition(inst).dimensions if s.required)

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
                    "photos": sorted([a, t, self.assets.get(a, {}).get("sha256", "")] for a, t in i.photo_tags.items()),
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

    KINDS = ("DEV_SIMULATED", "HUMAN_FINAL")

    def review_items(self) -> dict:
        """What the reviewer must look at, derived from the same validation/interference logic."""
        from .interference import check_all, overall
        res = check_all(self)
        val = self.validate()
        return {
            "data_version": self.data_version, "content_hash": self.content_hash(),
            "validation_errors": [i for i in val if i.severity == "ERROR"],
            "fail": [r for r in res if r.status == "FAIL"],
            "unchecked": [r for r in res if r.status == "UNCHECKED"],
            "overall": overall(res),
            "estimated": [(i.object_id, k) for i in self.instances.values()
                          for k, m in i.measurements.items() if m.source is not Source.MEASURED],
        }

    def approve(self, approver: str, waivers: dict[str, str] | None = None, kind: str = "DEV_SIMULATED",
                expect_version: int | None = None, expect_hash: str | None = None,
                confirmations: list[str] | None = None) -> Approval:
        """Human Final Review gate for ONE data version. expect_version and expect_hash are REQUIRED
        (Fail Closed if omitted or mismatched). The Engine/API enforces this; UI presence is not trust.
        Empty projects (0 objects) cannot be approved. INCOMPLETE/UNCHECKED never promote to PASS;
        UNCHECKED items need a reasoned waiver; FAIL can never be waived.
        NOTE (F-4 OPEN): HUMAN_FINAL does NOT currently guarantee authenticated approver identity,
        approval integrity, or signed/server-verifiable authenticity. Those are a Production Gate."""
        if kind not in self.KINDS:
            raise ApprovalError("unknown approval kind")
        if self.status is not Status.IN_REVIEW:
            raise ApprovalError("must be IN_REVIEW")
        if not approver.strip():
            raise ApprovalError("approver required")
        if expect_version is None:
            raise ApprovalError("expect_version required (version-bound approval)")
        if expect_hash is None or not str(expect_hash).strip():
            raise ApprovalError("expect_hash required (hash-bound approval)")
        if int(expect_version) != self.data_version:
            raise ApprovalError(f"stale review: reviewed v{expect_version}, current v{self.data_version}")
        if str(expect_hash) != self.content_hash():
            raise ApprovalError("stale review: content hash differs from the reviewed one")
        if len(self.instances) == 0:
            raise ApprovalError("empty project cannot be approved (no objects)")
        waivers = waivers or {}
        items = self.review_items()
        # overall INCOMPLETE is never an auto-PASS; empty already rejected above.
        # UNCHECKED stays UNCHECKED unless each item has an explicit reasoned waiver.
        if items["overall"] == "INCOMPLETE" and not items["unchecked"] and not items["fail"]:
            raise ApprovalError("incomplete project cannot be approved (no checkable interference results)")
        if items["validation_errors"]:
            raise ApprovalError("validation errors present")
        if items["fail"]:
            raise ApprovalError("interference FAIL cannot be approved: " + ",".join(r.pair_id for r in items["fail"]))
        for r in items["unchecked"]:
            if not waivers.get(r.pair_id, "").strip():
                raise ApprovalError(f"unchecked item needs waiver with reason: {r.pair_id}")
        self.status = Status.APPROVED
        a = Approval(self.data_version, self.content_hash(), approver,
                     datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     {k: v for k, v in waivers.items() if k in {r.pair_id for r in items["unchecked"]}},
                     kind, list(confirmations or []))
        self.approvals.append(a)
        self.history.append(f"v{self.data_version} approved ({kind}) by {approver}")
        return a

    def current_approval(self) -> Approval | None:
        for a in reversed(self.approvals):
            if a.valid and a.approved_version == self.data_version and a.content_hash == self.content_hash():
                return a
        return None


    # ---- persistence
    def to_dict(self) -> dict:
        from dataclasses import asdict
        d = {
            "project_id": self.project_id, "room": {k: str(v) for k, v in self.room.items()},
            "data_version": self.data_version, "status": self.status.value, "history": self.history,
            "assets": self.assets,
            "approvals": [asdict(a) for a in self.approvals],
            "instances": {oid: {
                "object_id": i.object_id, "definition_id": i.definition_id,
                "definition_version": i.definition_version, "label": i.label,
                "measurements": {k: {"mm": str(m.mm), "source": m.source.value, "original_input": m.original_input,
                                     "measured_by": m.measured_by} for k, m in i.measurements.items()},
                "photo_ids": i.photo_ids, "photo_tags": i.photo_tags, "annotations": i.annotations,
                "placement": None if i.placement is None else {
                    "x_mm": str(i.placement.x_mm), "y_mm": str(i.placement.y_mm),
                    "z_mm": str(i.placement.z_mm), "rotation_deg": i.placement.rotation_deg}}
                for oid, i in self.instances.items()},
        }
        return d

    @classmethod
    def from_dict(cls, d: dict, catalog: Catalog) -> "Project":
        p = cls.__new__(cls)
        p.project_id, p.catalog = d["project_id"], catalog
        p.room = {k: Decimal(v) for k, v in d["room"].items()}
        p.data_version, p.status, p.history = d["data_version"], Status(d["status"]), list(d["history"])
        p.assets = dict(d.get("assets", {}))
        p.approvals = [Approval(**a) for a in d["approvals"]]
        p.instances = {}
        for oid, i in d["instances"].items():
            inst = ObjectInstance(i["object_id"], i["definition_id"], i["definition_version"], i["label"])
            inst.measurements = {k: Measurement(Decimal(m["mm"]), Source(m["source"]), m["original_input"],
                                                m.get("measured_by", "")) for k, m in i["measurements"].items()}
            inst.photo_ids, inst.photo_tags, inst.annotations = i["photo_ids"], i["photo_tags"], i["annotations"]
            pl = i["placement"]
            inst.placement = None if pl is None else Placement(Decimal(pl["x_mm"]), Decimal(pl["y_mm"]),
                                                               Decimal(pl["z_mm"]), pl["rotation_deg"])
            p.instances[oid] = inst
        return p
