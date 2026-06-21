"""Objective scoring helpers for topology candidates."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping

from pns.cases import case_to_complex_values, load_case
from pns.rfmath import complex_to_mag_phase, db20, phase_error_deg, polar_to_complex


@dataclass(frozen=True)
class ObjectiveWeights:
    """Weights applied to squared objective error components."""

    magnitude_error_db: float = 1.0
    phase_error_deg: float = 1.0
    input_r_error_ohms: float = 1.0
    input_x_error_ohms: float = 1.0


@dataclass(frozen=True)
class TopologyAScore:
    """Score components for a Topology A candidate."""

    magnitude_error_db: float
    phase_error_deg: float
    input_r_error_ohms: float
    input_x_error_ohms: float
    swr: float
    total_score: float


@dataclass(frozen=True)
class CaseTargets:
    """Complex target values loaded from a case JSON file."""

    target_ratio: complex
    target_input_impedance: complex


def score_topology_a_result(
    result,
    target_ratio: complex,
    target_input_impedance: complex = 50 + 0j,
    weights: ObjectiveWeights | Mapping[str, float] | None = None,
) -> TopologyAScore:
    """Score a Topology A result against target ratio and input impedance."""
    if target_ratio == 0:
        raise ValueError("target_ratio must not be zero")

    objective_weights = _coerce_weights(weights)

    actual_magnitude, actual_phase_deg = complex_to_mag_phase(
        result.v_ratio_v2_over_v1
    )
    target_magnitude, target_phase_deg = complex_to_mag_phase(target_ratio)

    if actual_magnitude <= 0:
        magnitude_error_db = -math.inf
    else:
        magnitude_error_db = db20(actual_magnitude / target_magnitude)

    ratio_phase_error_deg = phase_error_deg(actual_phase_deg, target_phase_deg)
    input_r_error_ohms = result.z_input.real - target_input_impedance.real
    input_x_error_ohms = result.z_input.imag - target_input_impedance.imag

    total_score = (
        objective_weights.magnitude_error_db * magnitude_error_db**2
        + objective_weights.phase_error_deg * ratio_phase_error_deg**2
        + objective_weights.input_r_error_ohms * input_r_error_ohms**2
        + objective_weights.input_x_error_ohms * input_x_error_ohms**2
    )

    return TopologyAScore(
        magnitude_error_db=magnitude_error_db,
        phase_error_deg=ratio_phase_error_deg,
        input_r_error_ohms=input_r_error_ohms,
        input_x_error_ohms=input_x_error_ohms,
        swr=result.swr,
        total_score=total_score,
    )


def case_target_ratio(data: dict) -> complex:
    """Build the complex target V2/V1 ratio from validated case data."""
    values = case_to_complex_values(data)
    return polar_to_complex(
        values["target_voltage_ratio_magnitude"],
        values["target_voltage_ratio_phase_deg"],
    )


def case_targets(data: dict) -> CaseTargets:
    """Build complex objective targets from validated case data."""
    values = case_to_complex_values(data)
    return CaseTargets(
        target_ratio=polar_to_complex(
            values["target_voltage_ratio_magnitude"],
            values["target_voltage_ratio_phase_deg"],
        ),
        target_input_impedance=values["target_input_impedance_ohms"],
    )


def load_case_targets(path: str | Path) -> CaseTargets:
    """Load a case JSON file and return complex objective targets."""
    return case_targets(load_case(path))


def _coerce_weights(
    weights: ObjectiveWeights | Mapping[str, float] | None,
) -> ObjectiveWeights:
    if weights is None:
        return ObjectiveWeights()

    if isinstance(weights, ObjectiveWeights):
        return weights

    return ObjectiveWeights(
        magnitude_error_db=weights.get("magnitude_error_db", 1.0),
        phase_error_deg=weights.get("phase_error_deg", 1.0),
        input_r_error_ohms=weights.get("input_r_error_ohms", 1.0),
        input_x_error_ohms=weights.get("input_x_error_ohms", 1.0),
    )
