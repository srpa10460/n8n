"""B interface: derived presentation Scene. Derived from an APPROVED project snapshot;
never writes back to the source. Section / explode / camera live only in the Scene."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from decimal import Decimal

from .project import Project


class SceneError(RuntimeError):
    pass


@dataclass
class Scene:
    scene_id: str
    source_project_id: str
    source_data_version: int
    source_hash: str
    approved_source: bool
    source_snapshot: dict            # frozen deep copy; read-only by convention + hash check
    section_plane: dict | None = None
    explode: dict[str, list[str]] = field(default_factory=dict)  # object_id -> offset [dx,dy,dz] mm
    camera_path: list[dict] = field(default_factory=list)

    @property
    def preview_label(self) -> str:
        return "" if self.approved_source else "UNAPPROVED SOURCE - PREVIEW ONLY"

    def source_hash_of_snapshot(self) -> str:
        import hashlib
        return hashlib.sha256(json.dumps(self.source_snapshot, sort_keys=True).encode()).hexdigest()

    def verify_integrity(self) -> bool:
        return self.source_hash_of_snapshot() == self.source_hash

    def explode_object(self, object_id: str, dx: str, dy: str, dz: str) -> None:
        if object_id not in self.source_snapshot["objects"]:
            raise SceneError("unknown object")
        self.explode[object_id] = [str(Decimal(dx)), str(Decimal(dy)), str(Decimal(dz))]

    def add_camera_key(self, t: float, pos: list[float], target: list[float]) -> None:
        self.camera_path.append({"t": t, "pos": pos, "target": target})


def derive_scene(p: Project, scene_id: str, allow_unapproved_preview: bool = False) -> Scene:
    a = p.current_approval()
    if a is None and not allow_unapproved_preview:
        raise SceneError("source not approved (current data version has no valid approval)")
    return Scene(scene_id, p.project_id, p.data_version, p.content_hash(), a is not None,
                 copy.deepcopy(p.snapshot()))
