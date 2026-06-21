"""Evaluator for Topology A branch networks."""

from __future__ import annotations

from dataclasses import dataclass
import math

from pns.rfmath import parallel_impedance, swr_from_impedance


@dataclass(frozen=True)
class TopologyAResult:
    """Computed values for one ideal Topology A network."""

    z_branch1_input: complex
    z_branch2_input: complex
    z_input: complex
    y_input: complex
    v_port1: complex
    v_port2: complex
    v_ratio_v2_over_v1: complex
    i_branch1: complex
    i_branch2: complex
    swr: float
    branch1_complex_power_for_split_voltage: complex
    branch2_complex_power_for_split_voltage: complex


def evaluate_topology_a(
    frequency_hz: float,
    z1: complex,
    z2: complex,
    l1_h: float,
    c1_f: float,
    c2_f: float,
    l2_h: float,
    split_voltage: complex = 1 + 0j,
    z0: complex = 50,
) -> TopologyAResult:
    """Evaluate ideal Topology A branch networks for one component set."""
    _validate_inputs(frequency_hz, z1, z2, l1_h, c1_f, c2_f, l2_h)

    omega = 2.0 * math.pi * frequency_hz

    z_l1 = 1j * omega * l1_h
    z_c1 = 1.0 / (1j * omega * c1_f)
    z_c2 = 1.0 / (1j * omega * c2_f)
    z_l2 = 1j * omega * l2_h

    z_port1_parallel = parallel_impedance(z1, z_c1)
    z_port2_parallel = parallel_impedance(z2, z_l2)

    z_branch1_input = z_l1 + z_port1_parallel
    z_branch2_input = z_c2 + z_port2_parallel
    z_input = parallel_impedance(z_branch1_input, z_branch2_input)
    y_input = 1.0 / z_input

    i_branch1 = split_voltage / z_branch1_input
    i_branch2 = split_voltage / z_branch2_input

    v_port1 = split_voltage * z_port1_parallel / z_branch1_input
    v_port2 = split_voltage * z_port2_parallel / z_branch2_input
    v_ratio_v2_over_v1 = v_port2 / v_port1

    return TopologyAResult(
        z_branch1_input=z_branch1_input,
        z_branch2_input=z_branch2_input,
        z_input=z_input,
        y_input=y_input,
        v_port1=v_port1,
        v_port2=v_port2,
        v_ratio_v2_over_v1=v_ratio_v2_over_v1,
        i_branch1=i_branch1,
        i_branch2=i_branch2,
        swr=swr_from_impedance(z_input, z0),
        branch1_complex_power_for_split_voltage=split_voltage * i_branch1.conjugate(),
        branch2_complex_power_for_split_voltage=split_voltage * i_branch2.conjugate(),
    )


def _validate_inputs(
    frequency_hz: float,
    z1: complex,
    z2: complex,
    l1_h: float,
    c1_f: float,
    c2_f: float,
    l2_h: float,
) -> None:
    _require_positive("frequency_hz", frequency_hz)
    _require_positive("l1_h", l1_h)
    _require_positive("c1_f", c1_f)
    _require_positive("c2_f", c2_f)
    _require_positive("l2_h", l2_h)

    if z1 == 0:
        raise ValueError("z1 must not be zero")
    if z2 == 0:
        raise ValueError("z2 must not be zero")


def _require_positive(name: str, value: float) -> None:
    if value is None:
        raise ValueError(f"{name} must be greater than 0")
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")
