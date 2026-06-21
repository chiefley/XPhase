"""Ideal two-component L-network matching helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math

from pns.rfmath import parallel_impedance, swr_from_impedance


@dataclass(frozen=True)
class LMatchSolution:
    """One ideal input L-network match solution."""

    topology_name: str
    match_orientation: str
    series_reactance_ohms: float
    shunt_reactance_ohms: float
    series_component_type: str
    shunt_component_type: str
    series_value_si: float
    shunt_value_si: float
    input_impedance: complex
    swr: float
    notes: tuple[str, ...] = ()


def reactance_to_inductance(xl_ohms: float, frequency_hz: float) -> float:
    """Convert positive inductive reactance to inductance in henries."""
    _require_positive("frequency_hz", frequency_hz)
    _require_positive("xl_ohms", xl_ohms)
    return xl_ohms / _omega(frequency_hz)


def reactance_to_capacitance(xc_ohms: float, frequency_hz: float) -> float:
    """Convert capacitive reactance magnitude or signed value to farads."""
    _require_positive("frequency_hz", frequency_hz)
    if xc_ohms == 0:
        raise ValueError("xc_ohms must not be zero")
    return 1.0 / (_omega(frequency_hz) * abs(xc_ohms))


def find_l_matches(
    frequency_hz: float,
    load_impedance: complex,
    target_resistance: float = 50.0,
) -> list[LMatchSolution]:
    """Find ideal L-network matches from load impedance to a real source resistance."""
    _validate_match_inputs(frequency_hz, load_impedance, target_resistance)

    solutions = []
    solutions.extend(
        _series_then_shunt_solutions(
            frequency_hz,
            load_impedance,
            target_resistance,
        )
    )
    solutions.extend(
        _shunt_then_series_solutions(
            frequency_hz,
            load_impedance,
            target_resistance,
        )
    )
    return _deduplicate_solutions(solutions)


def evaluate_l_match_solution(
    solution: LMatchSolution,
    load_impedance: complex,
) -> complex:
    """Evaluate input impedance for a returned L-match solution."""
    series = 1j * solution.series_reactance_ohms
    shunt = 1j * solution.shunt_reactance_ohms

    if solution.match_orientation == "series-then-shunt":
        return series + parallel_impedance(load_impedance, shunt)
    if solution.match_orientation == "shunt-then-series":
        return parallel_impedance(shunt, series + load_impedance)

    raise ValueError(f"unknown match orientation: {solution.match_orientation}")


def _series_then_shunt_solutions(
    frequency_hz: float,
    load_impedance: complex,
    target_resistance: float,
) -> list[LMatchSolution]:
    load_admittance = 1.0 / load_impedance
    conductance = load_admittance.real
    load_susceptance = load_admittance.imag
    discriminant = conductance / target_resistance - conductance**2

    if discriminant < -_TOLERANCE:
        return []

    total_susceptance_options = _signed_square_roots(max(discriminant, 0.0))
    solutions = []
    for total_susceptance in total_susceptance_options:
        shunt_susceptance = total_susceptance - load_susceptance
        if abs(shunt_susceptance) <= _TOLERANCE:
            continue

        shunt_reactance = -1.0 / shunt_susceptance
        parallel_section = 1.0 / complex(conductance, total_susceptance)
        series_reactance = -parallel_section.imag
        solutions.extend(
            _build_solution(
                frequency_hz=frequency_hz,
                load_impedance=load_impedance,
                target_resistance=target_resistance,
                series_reactance=series_reactance,
                shunt_reactance=shunt_reactance,
                match_orientation="series-then-shunt",
                notes=("documented Topology B source-to-Split order",),
            )
        )

    return solutions


def _shunt_then_series_solutions(
    frequency_hz: float,
    load_impedance: complex,
    target_resistance: float,
) -> list[LMatchSolution]:
    load_resistance = load_impedance.real
    load_reactance = load_impedance.imag
    discriminant = load_resistance * target_resistance - load_resistance**2

    if discriminant < -_TOLERANCE:
        return []

    series_total_reactance_options = _signed_square_roots(max(discriminant, 0.0))
    solutions = []
    for series_total_reactance in series_total_reactance_options:
        series_reactance = series_total_reactance - load_reactance
        denominator = load_resistance**2 + series_total_reactance**2
        series_branch_susceptance = -series_total_reactance / denominator
        if abs(series_branch_susceptance) <= _TOLERANCE:
            continue

        shunt_reactance = 1.0 / series_branch_susceptance
        solutions.extend(
            _build_solution(
                frequency_hz=frequency_hz,
                load_impedance=load_impedance,
                target_resistance=target_resistance,
                series_reactance=series_reactance,
                shunt_reactance=shunt_reactance,
                match_orientation="shunt-then-series",
                notes=("alternate mathematical L-network orientation",),
            )
        )

    return solutions


def _build_solution(
    frequency_hz: float,
    load_impedance: complex,
    target_resistance: float,
    series_reactance: float,
    shunt_reactance: float,
    match_orientation: str,
    notes: tuple[str, ...],
) -> list[LMatchSolution]:
    series_component_type = _component_type(series_reactance)
    shunt_component_type = _component_type(shunt_reactance)

    if series_component_type is None or shunt_component_type is None:
        return []

    topology_name = _topology_name(series_component_type, shunt_component_type)
    if topology_name is None:
        return []

    solution = LMatchSolution(
        topology_name=topology_name,
        match_orientation=match_orientation,
        series_reactance_ohms=series_reactance,
        shunt_reactance_ohms=shunt_reactance,
        series_component_type=series_component_type,
        shunt_component_type=shunt_component_type,
        series_value_si=_component_value(series_reactance, frequency_hz),
        shunt_value_si=_component_value(shunt_reactance, frequency_hz),
        input_impedance=0j,
        swr=math.inf,
        notes=notes,
    )
    input_impedance = evaluate_l_match_solution(solution, load_impedance)
    swr = swr_from_impedance(input_impedance, target_resistance)

    return [
        LMatchSolution(
            topology_name=solution.topology_name,
            match_orientation=solution.match_orientation,
            series_reactance_ohms=solution.series_reactance_ohms,
            shunt_reactance_ohms=solution.shunt_reactance_ohms,
            series_component_type=solution.series_component_type,
            shunt_component_type=solution.shunt_component_type,
            series_value_si=solution.series_value_si,
            shunt_value_si=solution.shunt_value_si,
            input_impedance=input_impedance,
            swr=swr,
            notes=solution.notes,
        )
    ]


def _component_type(reactance_ohms: float) -> str | None:
    if reactance_ohms > _TOLERANCE:
        return "L"
    if reactance_ohms < -_TOLERANCE:
        return "C"
    return None


def _component_value(reactance_ohms: float, frequency_hz: float) -> float:
    if reactance_ohms > 0:
        return reactance_to_inductance(reactance_ohms, frequency_hz)
    return reactance_to_capacitance(reactance_ohms, frequency_hz)


def _topology_name(series_component_type: str, shunt_component_type: str) -> str | None:
    if series_component_type == "L" and shunt_component_type == "C":
        return "B-LP"
    if series_component_type == "C" and shunt_component_type == "L":
        return "B-HP"
    return None


def _signed_square_roots(value: float) -> tuple[float, ...]:
    root = math.sqrt(value)
    if root <= _TOLERANCE:
        return (0.0,)
    return root, -root


def _deduplicate_solutions(solutions: list[LMatchSolution]) -> list[LMatchSolution]:
    unique = []
    seen = set()
    for solution in solutions:
        key = (
            solution.topology_name,
            solution.match_orientation,
            round(solution.series_reactance_ohms, 12),
            round(solution.shunt_reactance_ohms, 12),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(solution)
    return unique


def _validate_match_inputs(
    frequency_hz: float,
    load_impedance: complex,
    target_resistance: float,
) -> None:
    _require_positive("frequency_hz", frequency_hz)
    _require_positive("target_resistance", target_resistance)

    if load_impedance == 0:
        raise ValueError("load_impedance must not be zero")
    if load_impedance.real <= 0:
        raise ValueError("load_impedance must have positive resistance")


def _require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")


def _omega(frequency_hz: float) -> float:
    return 2.0 * math.pi * frequency_hz


_TOLERANCE = 1e-12
