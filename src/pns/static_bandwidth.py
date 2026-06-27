"""Level 1 static/frozen network bandwidth evaluation."""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
import math
from pathlib import Path

from pns.feedline import (
    LosslessCoaxLine,
    feet_to_meters,
    meters,
    transform_two_feedpoints_to_box_end,
)
from pns.feedline_sweep import adjusted_target_ratio_for_polarity
from pns.lmatch import LMatchSolution
from pns.rfmath import (
    complex_to_mag_phase,
    phase_error_deg,
    polar_to_complex,
)
from pns.stress import estimate_topology_b_stress
from pns.sweep_reporting import (
    KNOWN_COMPONENT_STRESS_NAMES,
    ComponentStressSummary,
)
from pns.topology_b import TopologyBResult, evaluate_topology_b_from_components


def _component_stress_csv_fieldnames() -> tuple[str, ...]:
    return tuple(
        field_name
        for component_name in KNOWN_COMPONENT_STRESS_NAMES
        for field_name in (
            f"{component_name}_rms_voltage",
            f"{component_name}_rms_current",
            f"{component_name}_loss_watts",
        )
    )


STATIC_BANDWIDTH_CSV_FIELDNAMES = (
    "candidate_index",
    "candidate_label",
    "mode",
    "polarity",
    "common_length",
    "offset",
    "port1_length",
    "port2_length",
    "length_unit",
    "frequency_hz",
    "frequency_mhz",
    "port1_box_r_ohms",
    "port1_box_x_ohms",
    "port2_box_r_ohms",
    "port2_box_x_ohms",
    "achieved_v2_over_v1_magnitude",
    "achieved_v2_over_v1_phase_deg",
    "target_v2_over_v1_magnitude",
    "target_v2_over_v1_phase_deg",
    "magnitude_error",
    "phase_error_deg",
    "zin_r_ohms",
    "zin_x_ohms",
    "swr",
    "total_estimated_loss_watts",
    "estimated_efficiency_percent",
    *_component_stress_csv_fieldnames(),
)


@dataclass(frozen=True)
class CandidateFeedlineLengths:
    """Physical feedline lengths extracted from a solved sweep result."""

    mode: str
    common_length: float
    offset: float | None
    port1_length: float
    port2_length: float
    length_unit: str


@dataclass(frozen=True)
class StaticBandwidthPoint:
    """Frozen-network result at one frequency."""

    frequency_hz: float
    port1_box_impedance_ohms: complex
    port2_box_impedance_ohms: complex
    achieved_ratio_magnitude: float
    achieved_ratio_phase_deg: float
    target_ratio_magnitude: float
    target_ratio_phase_deg: float
    magnitude_error: float
    phase_error_deg: float
    zin_ohms: complex
    swr: float
    total_estimated_loss_watts: float | None
    estimated_efficiency_percent: float | None
    component_stresses: tuple[ComponentStressSummary, ...]
    worst_rms_voltage: float | None
    worst_rms_voltage_component: str | None
    worst_rms_current: float | None
    worst_rms_current_component: str | None
    worst_component_loss_watts: float | None
    worst_component_loss_name: str | None


@dataclass(frozen=True)
class StaticBandwidthSummary:
    """Level 1 bandwidth summary for one frozen solved candidate."""

    candidate_label: str
    mode: str
    polarity: str
    common_length: float
    offset: float | None
    port1_length: float
    port2_length: float
    length_unit: str
    center_frequency_hz: float
    points: tuple[StaticBandwidthPoint, ...]
    max_swr: float
    max_magnitude_error: float
    max_abs_phase_error_deg: float
    max_total_estimated_loss_watts: float | None
    min_estimated_efficiency_percent: float | None
    max_component_stresses: tuple[ComponentStressSummary, ...]


def frequency_grid_hz(
    start_hz: float,
    stop_hz: float,
    step_hz: float,
) -> tuple[float, ...]:
    """Return a positive frequency grid with both endpoints included."""
    _require_positive_finite("start_hz", start_hz)
    _require_positive_finite("stop_hz", stop_hz)
    _require_positive_finite("step_hz", step_hz)
    if stop_hz < start_hz:
        raise ValueError("stop_hz must be greater than or equal to start_hz")
    if start_hz == stop_hz:
        return (start_hz,)

    tolerance = max(step_hz, stop_hz - start_hz, 1.0) * 1e-12
    values = []
    index = 0
    while True:
        value = start_hz + index * step_hz
        if value > stop_hz + tolerance:
            break
        values.append(stop_hz if abs(value - stop_hz) <= tolerance else value)
        index += 1
    if not values or values[-1] < stop_hz - tolerance:
        values.append(stop_hz)
    return tuple(values)


def extract_candidate_feedline_lengths(result) -> CandidateFeedlineLengths:
    """Extract equal-length or offset physical lengths from a sweep result."""
    candidate = result.candidate
    if hasattr(candidate, "offset"):
        return CandidateFeedlineLengths(
            mode="offset",
            common_length=candidate.common_length,
            offset=candidate.offset,
            port1_length=candidate.port1_length,
            port2_length=candidate.port2_length,
            length_unit=candidate.length_unit,
        )
    return CandidateFeedlineLengths(
        mode="equal_length",
        common_length=candidate.common_length,
        offset=None,
        port1_length=candidate.common_length,
        port2_length=candidate.common_length,
        length_unit=candidate.length_unit,
    )


def evaluate_frozen_topology_b(
    *,
    frequency_hz: float,
    z1_box_ohms: complex,
    z2_box_ohms: complex,
    components,
    input_match_solution: LMatchSolution,
    target_input_impedance_ohms: complex = 50 + 0j,
) -> TopologyBResult:
    """Evaluate fixed Topology B component values at one frequency.

    The input L-match orientation and physical L/C values remain fixed. Its
    reactances are reconstructed at ``frequency_hz`` before using the existing
    Topology B evaluator. No optimizer is called.
    """
    _require_positive_finite("frequency_hz", frequency_hz)
    target_resistance = target_input_impedance_ohms.real
    if target_resistance <= 0 or abs(target_input_impedance_ohms.imag) > 1e-12:
        raise ValueError("target_input_impedance_ohms must be a positive real impedance")

    frequency_match = _lmatch_at_frequency(input_match_solution, frequency_hz)
    result = evaluate_topology_b_from_components(
        frequency_hz=frequency_hz,
        z1=z1_box_ohms,
        z2=z2_box_ohms,
        l1_h=components.l1_h,
        c1_f=components.c1_f,
        c2_f=components.c2_f,
        l2_h=components.l2_h,
        input_match_solution=frequency_match,
        target_resistance=target_resistance,
        z0=target_resistance,
    )
    evaluated_match = replace(
        frequency_match,
        input_impedance=result.z_input,
        swr=result.swr,
    )
    return replace(result, lmatch_solution=evaluated_match)


def evaluate_static_bandwidth_for_result(
    result,
    *,
    z1_feedpoint_ohms: complex,
    z2_feedpoint_ohms: complex,
    center_frequency_hz: float,
    frequencies_hz: tuple[float, ...],
    target_voltage_ratio_magnitude: float,
    target_voltage_ratio_phase_deg: float,
    target_input_impedance_ohms: complex = 50 + 0j,
    characteristic_impedance_ohms: float = 50.0,
    velocity_factor: float = 0.66,
    input_power_watts: float | None = None,
    inductor_q: float = 250.0,
    capacitor_q: float = 1000.0,
) -> StaticBandwidthSummary:
    """Evaluate one solved sweep candidate without off-center reoptimization."""
    _require_positive_finite("center_frequency_hz", center_frequency_hz)
    if not frequencies_hz:
        raise ValueError("frequencies_hz must contain at least one frequency")

    lengths = extract_candidate_feedline_lengths(result)
    port1_length_m = _length_to_meters(lengths.port1_length, lengths.length_unit)
    port2_length_m = _length_to_meters(lengths.port2_length, lengths.length_unit)
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
    target_ratio = adjusted_target_ratio_for_polarity(
        polar_to_complex(
            target_voltage_ratio_magnitude,
            target_voltage_ratio_phase_deg,
        ),
        getattr(result, "polarity", "normal"),
    )
    target_magnitude, target_phase_deg = complex_to_mag_phase(target_ratio)
    optimization_result = result.optimization_result
    points = []

    for frequency_hz in frequencies_hz:
        _require_positive_finite("frequency_hz", frequency_hz)
        z1_box, z2_box = transform_two_feedpoints_to_box_end(
            z1_feedpoint_ohms,
            z2_feedpoint_ohms,
            frequency_hz,
            feedline1,
            feedline2,
        )
        fixed_result = evaluate_frozen_topology_b(
            frequency_hz=frequency_hz,
            z1_box_ohms=z1_box,
            z2_box_ohms=z2_box,
            components=optimization_result.components,
            input_match_solution=optimization_result.input_match_solution,
            target_input_impedance_ohms=target_input_impedance_ohms,
        )
        achieved_magnitude, achieved_phase_deg = complex_to_mag_phase(
            fixed_result.v_ratio_v2_over_v1
        )
        stress_report = None
        if input_power_watts is not None:
            stress_report = estimate_topology_b_stress(
                result=fixed_result,
                frequency_hz=frequency_hz,
                z1=z1_box,
                z2=z2_box,
                input_power_watts=input_power_watts,
                inductor_q=inductor_q,
                capacitor_q=capacitor_q,
            )
        component_stresses = _component_stress_summaries(stress_report)
        worst = _worst_component_values(component_stresses)
        points.append(
            StaticBandwidthPoint(
                frequency_hz=frequency_hz,
                port1_box_impedance_ohms=z1_box,
                port2_box_impedance_ohms=z2_box,
                achieved_ratio_magnitude=achieved_magnitude,
                achieved_ratio_phase_deg=achieved_phase_deg,
                target_ratio_magnitude=target_magnitude,
                target_ratio_phase_deg=target_phase_deg,
                magnitude_error=achieved_magnitude - target_magnitude,
                phase_error_deg=phase_error_deg(
                    achieved_phase_deg,
                    target_phase_deg,
                ),
                zin_ohms=fixed_result.z_input,
                swr=fixed_result.swr,
                total_estimated_loss_watts=(
                    stress_report.total_estimated_loss_watts
                    if stress_report is not None
                    else None
                ),
                estimated_efficiency_percent=(
                    stress_report.estimated_efficiency_percent
                    if stress_report is not None
                    else None
                ),
                component_stresses=component_stresses,
                worst_rms_voltage=worst["voltage"],
                worst_rms_voltage_component=worst["voltage_component"],
                worst_rms_current=worst["current"],
                worst_rms_current_component=worst["current_component"],
                worst_component_loss_watts=worst["loss"],
                worst_component_loss_name=worst["loss_component"],
            )
        )

    point_tuple = tuple(points)
    return StaticBandwidthSummary(
        candidate_label=_candidate_label(lengths, getattr(result, "polarity", "normal")),
        mode=lengths.mode,
        polarity=getattr(result, "polarity", "normal"),
        common_length=lengths.common_length,
        offset=lengths.offset,
        port1_length=lengths.port1_length,
        port2_length=lengths.port2_length,
        length_unit=lengths.length_unit,
        center_frequency_hz=center_frequency_hz,
        points=point_tuple,
        max_swr=max(point.swr for point in point_tuple),
        max_magnitude_error=max(abs(point.magnitude_error) for point in point_tuple),
        max_abs_phase_error_deg=max(abs(point.phase_error_deg) for point in point_tuple),
        max_total_estimated_loss_watts=_optional_max(
            point.total_estimated_loss_watts for point in point_tuple
        ),
        min_estimated_efficiency_percent=_optional_min(
            point.estimated_efficiency_percent for point in point_tuple
        ),
        max_component_stresses=_maximum_component_stresses(point_tuple),
    )


def static_bandwidth_point_to_csv_row(
    summary: StaticBandwidthSummary,
    point: StaticBandwidthPoint,
    *,
    candidate_index: int,
) -> dict[str, object]:
    """Convert one static-bandwidth point to a CSV row.

    Missing optional stress/loss values and absent known components are written
    as empty strings.
    """
    row = {
        "candidate_index": candidate_index,
        "candidate_label": summary.candidate_label,
        "mode": summary.mode,
        "polarity": summary.polarity,
        "common_length": summary.common_length,
        "offset": _csv_optional(summary.offset),
        "port1_length": summary.port1_length,
        "port2_length": summary.port2_length,
        "length_unit": summary.length_unit,
        "frequency_hz": point.frequency_hz,
        "frequency_mhz": point.frequency_hz / 1e6,
        "port1_box_r_ohms": point.port1_box_impedance_ohms.real,
        "port1_box_x_ohms": point.port1_box_impedance_ohms.imag,
        "port2_box_r_ohms": point.port2_box_impedance_ohms.real,
        "port2_box_x_ohms": point.port2_box_impedance_ohms.imag,
        "achieved_v2_over_v1_magnitude": point.achieved_ratio_magnitude,
        "achieved_v2_over_v1_phase_deg": point.achieved_ratio_phase_deg,
        "target_v2_over_v1_magnitude": point.target_ratio_magnitude,
        "target_v2_over_v1_phase_deg": point.target_ratio_phase_deg,
        "magnitude_error": point.magnitude_error,
        "phase_error_deg": point.phase_error_deg,
        "zin_r_ohms": point.zin_ohms.real,
        "zin_x_ohms": point.zin_ohms.imag,
        "swr": point.swr,
        "total_estimated_loss_watts": _csv_optional(
            point.total_estimated_loss_watts
        ),
        "estimated_efficiency_percent": _csv_optional(
            point.estimated_efficiency_percent
        ),
    }
    stress_by_name = {
        component.name: component for component in point.component_stresses
    }
    for component_name in KNOWN_COMPONENT_STRESS_NAMES:
        component = stress_by_name.get(component_name)
        row[f"{component_name}_rms_voltage"] = _component_value(
            component,
            "rms_voltage",
        )
        row[f"{component_name}_rms_current"] = _component_value(
            component,
            "rms_current",
        )
        row[f"{component_name}_loss_watts"] = _component_value(
            component,
            "loss_watts",
        )
    return row


def write_static_bandwidth_csv(path, summaries) -> Path:
    """Write point-level static bandwidth summaries to CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=STATIC_BANDWIDTH_CSV_FIELDNAMES)
        writer.writeheader()
        for candidate_index, summary in enumerate(summaries, start=1):
            for point in summary.points:
                writer.writerow(
                    static_bandwidth_point_to_csv_row(
                        summary,
                        point,
                        candidate_index=candidate_index,
                    )
                )
    return path


def _lmatch_at_frequency(
    solution: LMatchSolution,
    frequency_hz: float,
) -> LMatchSolution:
    return replace(
        solution,
        series_reactance_ohms=_component_reactance(
            solution.series_component_type,
            solution.series_value_si,
            frequency_hz,
        ),
        shunt_reactance_ohms=_component_reactance(
            solution.shunt_component_type,
            solution.shunt_value_si,
            frequency_hz,
        ),
        input_impedance=0j,
        swr=math.inf,
    )


def _component_reactance(
    component_type: str,
    value_si: float,
    frequency_hz: float,
) -> float:
    _require_positive_finite("component value", value_si)
    omega = 2.0 * math.pi * frequency_hz
    if component_type == "L":
        return omega * value_si
    if component_type == "C":
        return -1.0 / (omega * value_si)
    raise ValueError(f"unknown component type: {component_type}")


def _component_stress_summaries(stress_report) -> tuple[ComponentStressSummary, ...]:
    if stress_report is None:
        return ()
    return tuple(
        ComponentStressSummary(
            name=component.name,
            rms_voltage=component.rms_voltage,
            rms_current=component.rms_current,
            loss_watts=component.loss_watts,
        )
        for component in stress_report.component_stresses
    )


def _worst_component_values(component_stresses) -> dict[str, float | str | None]:
    if not component_stresses:
        return {
            "voltage": None,
            "voltage_component": None,
            "current": None,
            "current_component": None,
            "loss": None,
            "loss_component": None,
        }
    worst_voltage = max(component_stresses, key=lambda value: value.rms_voltage)
    worst_current = max(component_stresses, key=lambda value: value.rms_current)
    worst_loss = max(component_stresses, key=lambda value: value.loss_watts)
    return {
        "voltage": worst_voltage.rms_voltage,
        "voltage_component": worst_voltage.name,
        "current": worst_current.rms_current,
        "current_component": worst_current.name,
        "loss": worst_loss.loss_watts,
        "loss_component": worst_loss.name,
    }


def _maximum_component_stresses(points) -> tuple[ComponentStressSummary, ...]:
    maximum_by_name = {}
    for point in points:
        for component in point.component_stresses:
            previous = maximum_by_name.get(component.name)
            if previous is None:
                maximum_by_name[component.name] = component
                continue
            maximum_by_name[component.name] = ComponentStressSummary(
                name=component.name,
                rms_voltage=max(previous.rms_voltage, component.rms_voltage),
                rms_current=max(previous.rms_current, component.rms_current),
                loss_watts=max(previous.loss_watts, component.loss_watts),
            )
    return tuple(maximum_by_name.values())


def _length_to_meters(length: float, length_unit: str) -> float:
    normalized = length_unit.lower()
    if normalized in {"ft", "foot", "feet"}:
        return feet_to_meters(length)
    if normalized in {"m", "meter", "meters"}:
        return meters(length)
    raise ValueError("length_unit must be 'ft' or 'm'")


def _candidate_label(lengths: CandidateFeedlineLengths, polarity: str) -> str:
    return (
        f"{lengths.mode}:{polarity}:"
        f"{lengths.port1_length:g}/{lengths.port2_length:g}{lengths.length_unit}"
    )


def _optional_max(values) -> float | None:
    available = tuple(value for value in values if value is not None)
    return max(available) if available else None


def _optional_min(values) -> float | None:
    available = tuple(value for value in values if value is not None)
    return min(available) if available else None


def _csv_optional(value):
    return "" if value is None else value


def _component_value(component, attribute: str):
    return "" if component is None else getattr(component, attribute)


def _require_positive_finite(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite value greater than 0")
