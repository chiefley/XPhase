"""Center-frequency feedline sweep helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from pns.feedline import (
    LosslessCoaxLine,
    feet_to_meters,
    meters,
    transform_two_feedpoints_to_box_end,
)
from pns.objectives import ObjectiveWeights
from pns.optimize import (
    DEFAULT_TOPOLOGY_A_BOUNDS,
    TopologyBOptimizationResult,
    optimize_topology_b,
)
from pns.rfmath import polar_to_complex
from pns.stress import TopologyBStressReport, estimate_topology_b_stress


@dataclass(frozen=True)
class EqualLengthFeedlineCandidate:
    """One equal physical feedline length transformed to box-end impedances."""

    common_length: float
    length_unit: str
    common_length_m: float
    port1_box_impedance_ohms: complex
    port2_box_impedance_ohms: complex
    port1_electrical_length_deg: float
    port2_electrical_length_deg: float


@dataclass(frozen=True)
class EqualLengthOptimizationSweepResult:
    """Topology B optimization result for one feedline sweep candidate."""

    candidate: EqualLengthFeedlineCandidate
    optimization_result: TopologyBOptimizationResult
    achieved_ratio_magnitude: float
    achieved_ratio_phase_deg: float
    zin_ohms: complex
    swr: float
    score_or_objective: float
    stress_report: TopologyBStressReport | None = None


@dataclass(frozen=True)
class OffsetFeedlineCandidate:
    """One common length plus port-2 offset transformed to box-end impedances."""

    common_length: float
    offset: float
    length_unit: str
    port1_length: float
    port2_length: float
    port1_length_m: float
    port2_length_m: float
    port1_box_impedance_ohms: complex
    port2_box_impedance_ohms: complex
    port1_electrical_length_deg: float
    port2_electrical_length_deg: float


@dataclass(frozen=True)
class OffsetOptimizationSweepResult:
    """Topology B optimization result for one offset feedline sweep candidate."""

    candidate: OffsetFeedlineCandidate
    optimization_result: TopologyBOptimizationResult
    achieved_ratio_magnitude: float
    achieved_ratio_phase_deg: float
    zin_ohms: complex
    swr: float
    score_or_objective: float
    stress_report: TopologyBStressReport | None = None


def equal_length_grid(
    start: float,
    stop: float,
    step: float,
) -> tuple[float, ...]:
    """Return an inclusive length grid for an equal-length sweep."""
    if start < 0:
        raise ValueError("start must be nonnegative")
    if stop < 0:
        raise ValueError("stop must be nonnegative")
    if step <= 0:
        raise ValueError("step must be greater than 0")
    if stop < start:
        raise ValueError("stop must be greater than or equal to start")
    if start == stop:
        return (start,)

    values = []
    index = 0
    tolerance = max(abs(step), abs(stop - start), 1.0) * 1e-12
    while True:
        value = start + index * step
        if value > stop + tolerance:
            break
        values.append(stop if abs(value - stop) <= tolerance else value)
        index += 1

    return tuple(values)


def offset_grid(
    start: float,
    stop: float,
    step: float,
) -> tuple[float, ...]:
    """Return an inclusive offset grid. Offsets may be negative."""
    if step <= 0:
        raise ValueError("step must be greater than 0")
    if stop < start:
        raise ValueError("stop must be greater than or equal to start")
    if start == stop:
        return (start,)

    values = []
    index = 0
    tolerance = max(abs(step), abs(stop - start), 1.0) * 1e-12
    while True:
        value = start + index * step
        if value > stop + tolerance:
            break
        values.append(stop if abs(value - stop) <= tolerance else value)
        index += 1

    return tuple(values)


def generate_equal_length_feedline_candidates(
    z1_feedpoint_ohms: complex,
    z2_feedpoint_ohms: complex,
    frequency_hz: float,
    characteristic_impedance_ohms: float,
    velocity_factor: float,
    start_length: float,
    stop_length: float,
    step: float,
    length_unit: str = "ft",
) -> tuple[EqualLengthFeedlineCandidate, ...]:
    """Generate equal-length transformed feedline candidates."""
    lengths = equal_length_grid(start_length, stop_length, step)
    return tuple(
        _equal_length_candidate(
            z1_feedpoint_ohms=z1_feedpoint_ohms,
            z2_feedpoint_ohms=z2_feedpoint_ohms,
            frequency_hz=frequency_hz,
            characteristic_impedance_ohms=characteristic_impedance_ohms,
            velocity_factor=velocity_factor,
            common_length=length,
            length_unit=length_unit,
        )
        for length in lengths
    )


def generate_offset_feedline_candidates(
    z1_feedpoint_ohms: complex,
    z2_feedpoint_ohms: complex,
    frequency_hz: float,
    characteristic_impedance_ohms: float,
    velocity_factor: float,
    start_common_length: float,
    stop_common_length: float,
    common_step: float,
    start_offset: float,
    stop_offset: float,
    offset_step: float,
    length_unit: str = "ft",
) -> tuple[OffsetFeedlineCandidate, ...]:
    """Generate transformed candidates for common length plus port-2 offset.

    Sign convention: port 2 is the forward +Y element and the NEC voltage
    phase-reference source. Positive offset adds physical coax length to port 2
    relative to port 1.
    """
    common_lengths = equal_length_grid(
        start_common_length,
        stop_common_length,
        common_step,
    )
    offsets = offset_grid(start_offset, stop_offset, offset_step)
    candidates = []
    for common_length in common_lengths:
        for offset in offsets:
            port2_length = common_length + offset
            if port2_length < 0:
                continue
            candidates.append(
                _offset_candidate(
                    z1_feedpoint_ohms=z1_feedpoint_ohms,
                    z2_feedpoint_ohms=z2_feedpoint_ohms,
                    frequency_hz=frequency_hz,
                    characteristic_impedance_ohms=characteristic_impedance_ohms,
                    velocity_factor=velocity_factor,
                    common_length=common_length,
                    offset=offset,
                    length_unit=length_unit,
                )
            )
    return tuple(candidates)


def optimize_equal_length_feedline_sweep(
    z1_feedpoint_ohms: complex,
    z2_feedpoint_ohms: complex,
    frequency_hz: float,
    target_voltage_ratio_magnitude: float,
    target_voltage_ratio_phase_deg: float,
    target_input_impedance_ohms: complex = 50 + 0j,
    characteristic_impedance_ohms: float = 50.0,
    velocity_factor: float = 0.66,
    start_length: float = 0.0,
    stop_length: float = 0.0,
    step: float = 1.0,
    length_unit: str = "ft",
    weights: ObjectiveWeights | Mapping[str, float] | None = None,
    maxiter: int = 60,
    bound_penalty_weight: float = 0.0,
    input_power_watts: float | None = None,
    inductor_q: float = 250.0,
    capacitor_q: float = 1000.0,
) -> tuple[EqualLengthOptimizationSweepResult, ...]:
    """Run Topology B optimization over equal-length feedline candidates."""
    candidates = generate_equal_length_feedline_candidates(
        z1_feedpoint_ohms=z1_feedpoint_ohms,
        z2_feedpoint_ohms=z2_feedpoint_ohms,
        frequency_hz=frequency_hz,
        characteristic_impedance_ohms=characteristic_impedance_ohms,
        velocity_factor=velocity_factor,
        start_length=start_length,
        stop_length=stop_length,
        step=step,
        length_unit=length_unit,
    )
    target_ratio = polar_to_complex(
        target_voltage_ratio_magnitude,
        target_voltage_ratio_phase_deg,
    )
    results = []
    for candidate in candidates:
        optimization_result = optimize_topology_b(
            frequency_hz=frequency_hz,
            z1=candidate.port1_box_impedance_ohms,
            z2=candidate.port2_box_impedance_ohms,
            target_ratio=target_ratio,
            target_input_impedance=target_input_impedance_ohms,
            weights=weights,
            maxiter=maxiter,
            bound_penalty_weight=bound_penalty_weight,
        )
        stress_report = None
        if input_power_watts is not None:
            stress_report = estimate_topology_b_stress(
                result=optimization_result.result,
                frequency_hz=frequency_hz,
                z1=candidate.port1_box_impedance_ohms,
                z2=candidate.port2_box_impedance_ohms,
                input_power_watts=input_power_watts,
                inductor_q=inductor_q,
                capacitor_q=capacitor_q,
            )
        results.append(
            EqualLengthOptimizationSweepResult(
                candidate=candidate,
                optimization_result=optimization_result,
                achieved_ratio_magnitude=optimization_result.v_ratio_magnitude,
                achieved_ratio_phase_deg=optimization_result.v_ratio_phase_deg,
                zin_ohms=optimization_result.z_input,
                swr=optimization_result.swr,
                score_or_objective=optimization_result.score.total_score,
                stress_report=stress_report,
            )
        )

    return tuple(sorted(results, key=_ranking_key))


def optimize_offset_feedline_sweep(
    z1_feedpoint_ohms: complex,
    z2_feedpoint_ohms: complex,
    frequency_hz: float,
    target_voltage_ratio_magnitude: float,
    target_voltage_ratio_phase_deg: float,
    target_input_impedance_ohms: complex = 50 + 0j,
    characteristic_impedance_ohms: float = 50.0,
    velocity_factor: float = 0.66,
    start_common_length: float = 0.0,
    stop_common_length: float = 0.0,
    common_step: float = 1.0,
    start_offset: float = 0.0,
    stop_offset: float = 0.0,
    offset_step: float = 1.0,
    length_unit: str = "ft",
    weights: ObjectiveWeights | Mapping[str, float] | None = None,
    maxiter: int = 60,
    bound_penalty_weight: float = 0.0,
    input_power_watts: float | None = None,
    inductor_q: float = 250.0,
    capacitor_q: float = 1000.0,
) -> tuple[OffsetOptimizationSweepResult, ...]:
    """Run Topology B optimization over common-length plus port-2 offsets.

    Ranking uses existing optimizer score, SWR, then total physical feedline
    length as a deterministic tie-breaker. It is not a practicality score.
    """
    candidates = generate_offset_feedline_candidates(
        z1_feedpoint_ohms=z1_feedpoint_ohms,
        z2_feedpoint_ohms=z2_feedpoint_ohms,
        frequency_hz=frequency_hz,
        characteristic_impedance_ohms=characteristic_impedance_ohms,
        velocity_factor=velocity_factor,
        start_common_length=start_common_length,
        stop_common_length=stop_common_length,
        common_step=common_step,
        start_offset=start_offset,
        stop_offset=stop_offset,
        offset_step=offset_step,
        length_unit=length_unit,
    )
    target_ratio = polar_to_complex(
        target_voltage_ratio_magnitude,
        target_voltage_ratio_phase_deg,
    )
    results = []
    for candidate in candidates:
        optimization_result = optimize_topology_b(
            frequency_hz=frequency_hz,
            z1=candidate.port1_box_impedance_ohms,
            z2=candidate.port2_box_impedance_ohms,
            target_ratio=target_ratio,
            target_input_impedance=target_input_impedance_ohms,
            weights=weights,
            maxiter=maxiter,
            bound_penalty_weight=bound_penalty_weight,
        )
        stress_report = None
        if input_power_watts is not None:
            stress_report = estimate_topology_b_stress(
                result=optimization_result.result,
                frequency_hz=frequency_hz,
                z1=candidate.port1_box_impedance_ohms,
                z2=candidate.port2_box_impedance_ohms,
                input_power_watts=input_power_watts,
                inductor_q=inductor_q,
                capacitor_q=capacitor_q,
            )
        results.append(
            OffsetOptimizationSweepResult(
                candidate=candidate,
                optimization_result=optimization_result,
                achieved_ratio_magnitude=optimization_result.v_ratio_magnitude,
                achieved_ratio_phase_deg=optimization_result.v_ratio_phase_deg,
                zin_ohms=optimization_result.z_input,
                swr=optimization_result.swr,
                score_or_objective=optimization_result.score.total_score,
                stress_report=stress_report,
            )
        )

    return tuple(sorted(results, key=_offset_ranking_key))


def format_component_value(component_type: str, value_si: float) -> str:
    """Return a compact human-readable L/C value."""
    if component_type == "L":
        return f"{_format_scaled_value(value_si * 1e6)} uH"
    if component_type == "C":
        return f"{_format_scaled_value(value_si * 1e12)} pF"
    raise ValueError(f"unknown component type: {component_type}")


def practical_warnings(
    result: EqualLengthOptimizationSweepResult | OffsetOptimizationSweepResult,
) -> tuple[str, ...]:
    """Return conservative practicality warnings for one sweep result."""
    warnings: list[str] = []
    optimization_result = result.optimization_result
    component_values = {
        "L1": ("L", optimization_result.components.l1_h),
        "C1": ("C", optimization_result.components.c1_f),
        "C2": ("C", optimization_result.components.c2_f),
        "L2": ("L", optimization_result.components.l2_h),
        "input_series": (
            optimization_result.input_match_solution.series_component_type,
            optimization_result.input_match_solution.series_value_si,
        ),
        "input_shunt": (
            optimization_result.input_match_solution.shunt_component_type,
            optimization_result.input_match_solution.shunt_value_si,
        ),
    }
    for name, (component_type, value_si) in component_values.items():
        warnings.extend(_component_value_warnings(name, component_type, value_si))

    warnings.extend(_branch_bound_warnings(optimization_result))

    if result.stress_report is not None:
        warnings.extend(_stress_warnings(result.stress_report))

    return tuple(warnings)


def _equal_length_candidate(
    z1_feedpoint_ohms: complex,
    z2_feedpoint_ohms: complex,
    frequency_hz: float,
    characteristic_impedance_ohms: float,
    velocity_factor: float,
    common_length: float,
    length_unit: str,
) -> EqualLengthFeedlineCandidate:
    common_length_m = _length_to_meters(common_length, length_unit)
    feedline = LosslessCoaxLine(
        characteristic_impedance_ohms=characteristic_impedance_ohms,
        velocity_factor=velocity_factor,
        length_m=common_length_m,
    )
    z1_box, z2_box = transform_two_feedpoints_to_box_end(
        z1_feedpoint_ohms,
        z2_feedpoint_ohms,
        frequency_hz,
        feedline,
        feedline,
    )
    electrical_length_deg = _electrical_length_deg(
        common_length_m,
        frequency_hz,
        velocity_factor,
    )
    return EqualLengthFeedlineCandidate(
        common_length=common_length,
        length_unit=length_unit,
        common_length_m=common_length_m,
        port1_box_impedance_ohms=z1_box,
        port2_box_impedance_ohms=z2_box,
        port1_electrical_length_deg=electrical_length_deg,
        port2_electrical_length_deg=electrical_length_deg,
    )


def _offset_candidate(
    z1_feedpoint_ohms: complex,
    z2_feedpoint_ohms: complex,
    frequency_hz: float,
    characteristic_impedance_ohms: float,
    velocity_factor: float,
    common_length: float,
    offset: float,
    length_unit: str,
) -> OffsetFeedlineCandidate:
    port1_length = common_length
    port2_length = common_length + offset
    port1_length_m = _length_to_meters(port1_length, length_unit)
    port2_length_m = _length_to_meters(port2_length, length_unit)
    feedline1 = LosslessCoaxLine(
        characteristic_impedance_ohms=characteristic_impedance_ohms,
        velocity_factor=velocity_factor,
        length_m=port1_length_m,
    )
    feedline2 = LosslessCoaxLine(
        characteristic_impedance_ohms=characteristic_impedance_ohms,
        velocity_factor=velocity_factor,
        length_m=port2_length_m,
    )
    z1_box, z2_box = transform_two_feedpoints_to_box_end(
        z1_feedpoint_ohms,
        z2_feedpoint_ohms,
        frequency_hz,
        feedline1,
        feedline2,
    )
    return OffsetFeedlineCandidate(
        common_length=common_length,
        offset=offset,
        length_unit=length_unit,
        port1_length=port1_length,
        port2_length=port2_length,
        port1_length_m=port1_length_m,
        port2_length_m=port2_length_m,
        port1_box_impedance_ohms=z1_box,
        port2_box_impedance_ohms=z2_box,
        port1_electrical_length_deg=_electrical_length_deg(
            port1_length_m,
            frequency_hz,
            velocity_factor,
        ),
        port2_electrical_length_deg=_electrical_length_deg(
            port2_length_m,
            frequency_hz,
            velocity_factor,
        ),
    )


def _length_to_meters(length: float, unit: str) -> float:
    normalized = unit.lower()
    if normalized in {"ft", "foot", "feet"}:
        return feet_to_meters(length)
    if normalized in {"m", "meter", "meters"}:
        return meters(length)
    raise ValueError("length_unit must be 'ft' or 'm'")


def _electrical_length_deg(
    length_m: float,
    frequency_hz: float,
    velocity_factor: float,
) -> float:
    wavelength_on_line_m = 299_792_458.0 * velocity_factor / frequency_hz
    return 360.0 * length_m / wavelength_on_line_m


def _ranking_key(result: EqualLengthOptimizationSweepResult):
    score = result.score_or_objective
    if not math.isfinite(score):
        score = math.inf
    return (
        score,
        result.swr,
        result.candidate.common_length_m,
    )


def _offset_ranking_key(result: OffsetOptimizationSweepResult):
    score = result.score_or_objective
    if not math.isfinite(score):
        score = math.inf
    total_feedline_length_m = (
        result.candidate.port1_length_m + result.candidate.port2_length_m
    )
    return (
        score,
        result.swr,
        total_feedline_length_m,
    )


def _component_value_warnings(
    name: str,
    component_type: str,
    value_si: float,
) -> list[str]:
    if component_type == "C":
        value_pf = value_si * 1e12
        if value_pf < 10.0:
            return [f"{name} < 10 pF"]
        if value_pf > 3000.0:
            return [f"{name} > 3000 pF"]
        return []

    if component_type == "L":
        value_uh = value_si * 1e6
        if value_uh < 0.05:
            return [f"{name} < 0.05 uH"]
        if value_uh > 10.0:
            return [f"{name} > 10 uH"]
        return []

    return [f"{name} has unknown component type"]


def _branch_bound_warnings(
    optimization_result: TopologyBOptimizationResult,
) -> list[str]:
    warnings = []
    for name, (lower, upper) in DEFAULT_TOPOLOGY_A_BOUNDS.items():
        value = getattr(optimization_result.components, name)
        label = name.upper().replace("_H", "").replace("_F", "")
        if value <= lower * 1.01:
            warnings.append(f"{label} near lower bound")
        elif value >= upper * 0.99:
            warnings.append(f"{label} near upper bound")
    return warnings


def _stress_warnings(stress_report: TopologyBStressReport) -> list[str]:
    warnings = []
    for component in stress_report.component_stresses:
        if component.rms_voltage >= 1000.0:
            warnings.append(f"{component.name} high voltage")
        if component.rms_current >= 5.0:
            warnings.append(f"{component.name} high current")
        if component.loss_watts >= 5.0:
            warnings.append(f"{component.name} high loss")
    return warnings


def _format_scaled_value(value: float) -> str:
    if abs(value) >= 100.0:
        return f"{value:.0f}"
    if abs(value) >= 10.0:
        return f"{value:.1f}"
    return f"{value:.3g}"
