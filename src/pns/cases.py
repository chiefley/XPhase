"""Case loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CaseValidationError(ValueError):
    """Raised when a case file does not match the supported schema."""


def load_case(path: str | Path) -> dict[str, Any]:
    """Load and validate a case JSON file."""
    with Path(path).open(encoding="utf-8") as case_file:
        data = json.load(case_file)

    validate_case(data)
    return data


def validate_case(data: Any) -> None:
    """Validate the current case JSON format."""
    if not isinstance(data, dict):
        raise CaseValidationError("case data must be a JSON object")

    _require_type(data, ("name",), str)
    _require_type(data, ("description",), str)
    _require_numeric(data, ("frequency_hz",), positive=True)
    _require_type(data, ("notes",), list)

    for index, note in enumerate(_get(data, ("notes",))):
        if not isinstance(note, str):
            raise CaseValidationError(f"notes[{index}] must be a string")

    for port_name in ("port1", "port2"):
        _require_numeric(data, ("ports", port_name, "z_ohms", "r"))
        _require_numeric(data, ("ports", port_name, "z_ohms", "x"))

    _require_numeric(
        data,
        ("target", "voltage_ratio_v2_over_v1", "magnitude"),
        positive=True,
    )
    _require_numeric(data, ("target", "voltage_ratio_v2_over_v1", "phase_deg"))
    _require_numeric(data, ("target", "input_impedance_ohms", "r"))
    _require_numeric(data, ("target", "input_impedance_ohms", "x"))

    _require_numeric(data, ("power_watts",), positive=True)
    _require_numeric(
        data,
        ("component_assumptions", "inductor_q"),
        positive=True,
    )
    _require_numeric(
        data,
        ("component_assumptions", "capacitor_q"),
        positive=True,
    )


def case_to_complex_values(data: dict[str, Any]) -> dict[str, complex | float]:
    """Return commonly used numeric case values as Python numbers."""
    validate_case(data)

    z1 = _complex_from_parts(data, ("ports", "port1", "z_ohms"))
    z2 = _complex_from_parts(data, ("ports", "port2", "z_ohms"))
    target_input_impedance = _complex_from_parts(
        data,
        ("target", "input_impedance_ohms"),
    )

    return {
        "frequency_hz": _get(data, ("frequency_hz",)),
        "z1_ohms": z1,
        "z2_ohms": z2,
        "target_voltage_ratio_magnitude": _get(
            data,
            ("target", "voltage_ratio_v2_over_v1", "magnitude"),
        ),
        "target_voltage_ratio_phase_deg": _get(
            data,
            ("target", "voltage_ratio_v2_over_v1", "phase_deg"),
        ),
        "target_input_impedance_ohms": target_input_impedance,
        "power_watts": _get(data, ("power_watts",)),
        "inductor_q": _get(data, ("component_assumptions", "inductor_q")),
        "capacitor_q": _get(data, ("component_assumptions", "capacitor_q")),
    }


def _complex_from_parts(data: dict[str, Any], path: tuple[str, ...]) -> complex:
    return complex(_get(data, (*path, "r")), _get(data, (*path, "x")))


def _require_type(data: dict[str, Any], path: tuple[str, ...], expected: type) -> None:
    value = _get(data, path)
    if not isinstance(value, expected):
        field = ".".join(path)
        raise CaseValidationError(f"{field} must be {expected.__name__}")


def _require_numeric(
    data: dict[str, Any],
    path: tuple[str, ...],
    *,
    positive: bool = False,
) -> None:
    value = _get(data, path)
    field = ".".join(path)

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CaseValidationError(f"{field} must be numeric")

    if positive and value <= 0:
        raise CaseValidationError(f"{field} must be greater than 0")


def _get(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    traversed: list[str] = []

    for key in path:
        traversed.append(key)
        if not isinstance(current, dict) or key not in current:
            raise CaseValidationError(f"missing required field: {'.'.join(traversed)}")
        current = current[key]

    return current
