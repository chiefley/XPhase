"""Optimization helpers for Topology A."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from scipy.optimize import differential_evolution

from pns.cases import case_to_complex_values
from pns.objectives import (
    ObjectiveWeights,
    TopologyAScore,
    case_targets,
    score_topology_a_result,
)
from pns.rfmath import complex_to_mag_phase
from pns.topology_a import TopologyAResult, evaluate_topology_a


DEFAULT_TOPOLOGY_A_BOUNDS = {
    "l1_h": (20e-9, 10e-6),
    "c1_f": (5e-12, 3000e-12),
    "c2_f": (5e-12, 3000e-12),
    "l2_h": (20e-9, 10e-6),
}


@dataclass(frozen=True)
class TopologyAComponentValues:
    """Component values for one Topology A candidate."""

    l1_h: float
    c1_f: float
    c2_f: float
    l2_h: float


@dataclass(frozen=True)
class TopologyAOptimizationResult:
    """Optimization output for a Topology A search."""

    success: bool
    message: str
    components: TopologyAComponentValues
    result: TopologyAResult
    score: TopologyAScore


@dataclass(frozen=True)
class TopologyACandidateDiagnostics:
    """Diagnostic values for one scored Topology A candidate."""

    components: TopologyAComponentValues
    v_ratio_magnitude: float
    v_ratio_phase_deg: float
    magnitude_error_db: float
    phase_error_deg: float
    z_input: complex
    input_r_error_ohms: float
    input_x_error_ohms: float
    swr: float
    total_score: float
    component_bound_proximity: dict[str, str | None]
    any_component_near_bound: bool


def optimize_topology_a(
    frequency_hz: float,
    z1: complex,
    z2: complex,
    target_ratio: complex,
    target_input_impedance: complex = 50 + 0j,
    bounds: Mapping[str, tuple[float, float]] | None = None,
    weights: ObjectiveWeights | Mapping[str, float] | None = None,
    maxiter: int = 60,
) -> TopologyAOptimizationResult:
    """Search ideal Topology A component values for target ratio and input match."""
    component_bounds = _coerce_bounds(bounds)
    log_bounds = [_log_bounds(component_bounds[name]) for name in _COMPONENT_ORDER]

    def objective(log_values):
        components = _components_from_log_values(log_values)
        try:
            result = evaluate_topology_a(
                frequency_hz=frequency_hz,
                z1=z1,
                z2=z2,
                l1_h=components.l1_h,
                c1_f=components.c1_f,
                c2_f=components.c2_f,
                l2_h=components.l2_h,
            )
            score = score_topology_a_result(
                result,
                target_ratio,
                target_input_impedance=target_input_impedance,
                weights=weights,
            )
        except (ValueError, ZeroDivisionError, OverflowError):
            return math.inf

        if not math.isfinite(score.total_score):
            return math.inf
        return score.total_score

    optimizer_result = differential_evolution(
        objective,
        bounds=log_bounds,
        maxiter=maxiter,
        polish=True,
        seed=1,
        updating="immediate",
        workers=1,
    )

    best_components = _components_from_log_values(optimizer_result.x)
    best_result = evaluate_topology_a(
        frequency_hz=frequency_hz,
        z1=z1,
        z2=z2,
        l1_h=best_components.l1_h,
        c1_f=best_components.c1_f,
        c2_f=best_components.c2_f,
        l2_h=best_components.l2_h,
    )
    best_score = score_topology_a_result(
        best_result,
        target_ratio,
        target_input_impedance=target_input_impedance,
        weights=weights,
    )

    return TopologyAOptimizationResult(
        success=bool(optimizer_result.success),
        message=str(optimizer_result.message),
        components=best_components,
        result=best_result,
        score=best_score,
    )


def diagnose_topology_a_candidate(
    frequency_hz: float,
    z1: complex,
    z2: complex,
    target_ratio: complex,
    l1_h: float,
    c1_f: float,
    c2_f: float,
    l2_h: float,
    target_input_impedance: complex = 50 + 0j,
    bounds: Mapping[str, tuple[float, float]] | None = None,
    weights: ObjectiveWeights | Mapping[str, float] | None = None,
) -> TopologyACandidateDiagnostics:
    """Evaluate and report score diagnostics for one Topology A candidate."""
    component_bounds = _coerce_bounds(bounds)
    components = TopologyAComponentValues(
        l1_h=l1_h,
        c1_f=c1_f,
        c2_f=c2_f,
        l2_h=l2_h,
    )
    result = evaluate_topology_a(
        frequency_hz=frequency_hz,
        z1=z1,
        z2=z2,
        l1_h=components.l1_h,
        c1_f=components.c1_f,
        c2_f=components.c2_f,
        l2_h=components.l2_h,
    )
    score = score_topology_a_result(
        result,
        target_ratio,
        target_input_impedance=target_input_impedance,
        weights=weights,
    )
    v_ratio_magnitude, v_ratio_phase_deg = complex_to_mag_phase(
        result.v_ratio_v2_over_v1
    )
    component_bound_proximity = _component_bound_proximity(
        components,
        component_bounds,
    )

    return TopologyACandidateDiagnostics(
        components=components,
        v_ratio_magnitude=v_ratio_magnitude,
        v_ratio_phase_deg=v_ratio_phase_deg,
        magnitude_error_db=score.magnitude_error_db,
        phase_error_deg=score.phase_error_deg,
        z_input=result.z_input,
        input_r_error_ohms=score.input_r_error_ohms,
        input_x_error_ohms=score.input_x_error_ohms,
        swr=score.swr,
        total_score=score.total_score,
        component_bound_proximity=component_bound_proximity,
        any_component_near_bound=any(
            bound is not None for bound in component_bound_proximity.values()
        ),
    )


def diagnose_topology_a_optimization(
    optimization_result: TopologyAOptimizationResult,
    frequency_hz: float,
    z1: complex,
    z2: complex,
    target_ratio: complex,
    target_input_impedance: complex = 50 + 0j,
    bounds: Mapping[str, tuple[float, float]] | None = None,
    weights: ObjectiveWeights | Mapping[str, float] | None = None,
) -> TopologyACandidateDiagnostics:
    """Build diagnostics for an optimizer result."""
    components = optimization_result.components
    return diagnose_topology_a_candidate(
        frequency_hz=frequency_hz,
        z1=z1,
        z2=z2,
        target_ratio=target_ratio,
        target_input_impedance=target_input_impedance,
        l1_h=components.l1_h,
        c1_f=components.c1_f,
        c2_f=components.c2_f,
        l2_h=components.l2_h,
        bounds=bounds,
        weights=weights,
    )


def optimize_topology_a_from_case(
    data: dict,
    bounds: Mapping[str, tuple[float, float]] | None = None,
    weights: ObjectiveWeights | Mapping[str, float] | None = None,
    maxiter: int = 60,
) -> TopologyAOptimizationResult:
    """Optimize Topology A from a loaded case dictionary."""
    values = case_to_complex_values(data)
    targets = case_targets(data)

    return optimize_topology_a(
        frequency_hz=values["frequency_hz"],
        z1=values["z1_ohms"],
        z2=values["z2_ohms"],
        target_ratio=targets.target_ratio,
        target_input_impedance=targets.target_input_impedance,
        bounds=bounds,
        weights=weights,
        maxiter=maxiter,
    )


_COMPONENT_ORDER = ("l1_h", "c1_f", "c2_f", "l2_h")


def _coerce_bounds(
    bounds: Mapping[str, tuple[float, float]] | None,
) -> dict[str, tuple[float, float]]:
    component_bounds = dict(DEFAULT_TOPOLOGY_A_BOUNDS)
    if bounds is not None:
        component_bounds.update(bounds)

    for name in _COMPONENT_ORDER:
        lower, upper = component_bounds[name]
        if lower <= 0 or upper <= 0 or lower >= upper:
            raise ValueError(f"{name} bounds must be positive and increasing")

    return component_bounds


def _log_bounds(bounds: tuple[float, float]) -> tuple[float, float]:
    lower, upper = bounds
    return math.log(lower), math.log(upper)


def _components_from_log_values(log_values) -> TopologyAComponentValues:
    values = [math.exp(value) for value in log_values]
    return TopologyAComponentValues(
        l1_h=values[0],
        c1_f=values[1],
        c2_f=values[2],
        l2_h=values[3],
    )


def _component_bound_proximity(
    components: TopologyAComponentValues,
    bounds: Mapping[str, tuple[float, float]],
) -> dict[str, str | None]:
    proximity = {}

    for name in _COMPONENT_ORDER:
        value = getattr(components, name)
        lower, upper = bounds[name]
        if value <= lower * 1.01:
            proximity[name] = "lower"
        elif value >= upper * 0.99:
            proximity[name] = "upper"
        else:
            proximity[name] = None

    return proximity
