"""Human-readable differences between two project snapshots (for conflict display)."""
from __future__ import annotations


def _flat(prefix: str, v, out: dict) -> None:
    if isinstance(v, dict):
        for k, x in v.items():
            _flat(f"{prefix}.{k}" if prefix else str(k), x, out)
    else:
        out[prefix] = v


def diff_snapshots(mine: dict, theirs: dict) -> list[dict]:
    a, b = {}, {}
    _flat("", mine, a)
    _flat("", theirs, b)
    out = []
    for k in sorted(set(a) | set(b)):
        if a.get(k, "<none>") != b.get(k, "<none>"):
            out.append({"path": k, "local": a.get(k, "<none>"), "server": b.get(k, "<none>")})
    return out
