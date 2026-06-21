"""Evaluator for Topology B networks."""

from __future__ import annotations

from dataclasses import dataclass
import math

from pns.lmatch import LMatchSolution, evaluate_l_match_solution, find_l_matches
from pns.rfmath import swr_from_impedance
from pns.topology_a import TopologyAResult, evaluate_topology_a


@dataclass(frozen=True)
class TopologyBResult:
    """Computed values for one ideal Topology B network."""

    topology_a_result: TopologyAResult
    lmatch_solution: LMatchSolution
    z_split: complex
    z_input: complex
    swr: float
    v_port1: complex
    v_port2: complex
    v_ratio_v2_over_v1: complex
    input_match_topology_name: str
    l1_h: float
    c1_f: float
    c2_f: float
    l2_h: float
    input_series_component_type: str
    input_shunt_component_type: str
    input_series_value_si: float
    input_shunt_value_si: float


def evaluate_topology_b_from_components(
    frequency_hz: float,
    z1: complex,
    z2: complex,
    l1_h: float,
    c1_f: float,
    c2_f: float,
    l2_h: float,
    input_match_solution: LMatchSolution | None = None,
    target_resistance: float = 50.0,
    z0: float = 50.0,
) -> TopologyBResult:
    """Evaluate Topology A branches followed by one ideal input L-match."""
    _require_positive("target_resistance", target_resistance)

    topology_a_result = evaluate_topology_a(
        frequency_hz=frequency_hz,
        z1=z1,
        z2=z2,
        l1_h=l1_h,
        c1_f=c1_f,
        c2_f=c2_f,
        l2_h=l2_h,
        z0=z0,
    )
    z_split = topology_a_result.z_input

    if input_match_solution is None:
        input_match_solution = _choose_l_match(
            frequency_hz,
            z_split,
            target_resistance,
        )

    z_input = evaluate_l_match_solution(input_match_solution, z_split)
    swr = swr_from_impedance(z_input, z0)
    if not math.isfinite(z_input.real) or not math.isfinite(z_input.imag):
        raise ValueError("input match produced non-finite input impedance")

    return TopologyBResult(
        topology_a_result=topology_a_result,
        lmatch_solution=input_match_solution,
        z_split=z_split,
        z_input=z_input,
        swr=swr,
        v_port1=topology_a_result.v_port1,
        v_port2=topology_a_result.v_port2,
        v_ratio_v2_over_v1=topology_a_result.v_ratio_v2_over_v1,
        input_match_topology_name=input_match_solution.topology_name,
        l1_h=l1_h,
        c1_f=c1_f,
        c2_f=c2_f,
        l2_h=l2_h,
        input_series_component_type=input_match_solution.series_component_type,
        input_shunt_component_type=input_match_solution.shunt_component_type,
        input_series_value_si=input_match_solution.series_value_si,
        input_shunt_value_si=input_match_solution.shunt_value_si,
    )


def _choose_l_match(
    frequency_hz: float,
    z_split: complex,
    target_resistance: float,
) -> LMatchSolution:
    matches = find_l_matches(
        frequency_hz=frequency_hz,
        load_impedance=z_split,
        target_resistance=target_resistance,
    )
    if not matches:
        raise ValueError("no valid input L-match found for split impedance")
    return matches[0]


def _require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")
