"""Length units. Canonical internal unit: millimetre, Decimal, quantised to 0.001 mm.

Conversion factors are exact (in = 25.4 mm, ft = 304.8 mm, by definition).
Decimal arithmetic avoids binary float drift; rounding is ROUND_HALF_UP at 0.001 mm.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

INTERNAL_UNIT = "mm"
QUANTUM = Decimal("0.001")
_TO_MM = {
    "mm": Decimal(1),
    "cm": Decimal(10),
    "m": Decimal(1000),
    "in": Decimal("25.4"),
    "ft": Decimal("304.8"),
}
_ALIASES = {'"': "in", "inch": "in", "inches": "in", "'": "ft", "feet": "ft", "foot": "ft"}
_RE = re.compile(r"^\s*([-+]?\d+(?:\.\d+)?)\s*([A-Za-z\"']*)\s*$")


class UnitError(ValueError):
    pass


def supported_units() -> tuple[str, ...]:
    return tuple(_TO_MM)


def to_mm(value: Decimal | int | str, unit: str) -> Decimal:
    unit = _ALIASES.get(unit.lower(), unit.lower())
    if unit not in _TO_MM:
        raise UnitError(f"unsupported unit: {unit!r}")
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as e:
        raise UnitError(f"not a number: {value!r}") from e
    if not d.is_finite():
        raise UnitError(f"non-finite value: {value!r}")
    return (d * _TO_MM[unit]).quantize(QUANTUM, rounding=ROUND_HALF_UP)


def parse_length(text: str | int | Decimal, default_unit: str = "mm") -> Decimal:
    """Parse '1.2 m', '48in', '900' (default unit) into canonical mm. Floats are rejected
    (pass strings/Decimals) so that binary representation never enters the data."""
    if isinstance(text, float):
        raise UnitError("float input rejected; pass str or Decimal")
    if isinstance(text, (int, Decimal)):
        return to_mm(text, default_unit)
    m = _RE.match(text)
    if not m:
        raise UnitError(f"cannot parse length: {text!r}")
    return to_mm(m.group(1), m.group(2) or default_unit)


def from_mm(mm: Decimal, unit: str, places: int = 3) -> Decimal:
    unit = _ALIASES.get(unit.lower(), unit.lower())
    if unit not in _TO_MM:
        raise UnitError(f"unsupported unit: {unit!r}")
    return (mm / _TO_MM[unit]).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
