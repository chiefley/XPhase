"""Stress and ideal Q-loss estimates for topology results."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from pns.lmatch import LMatchSolution
from pns.rfmath import parallel_impedance
from pns.topology_b import TopologyBResult


@dataclass(frozen=True)
class ComponentStress:
    """Voltage, current, and approximate loss for one component."""

    name: str
    component_type: str
    value_si: float
    reactance_ohms: float
    esr_ohms: float
    rms_voltage: float
    rms_current: float
    loss_watts: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class TopologyBStressReport:
    """Stress and loss report for a Topology B result."""

    input_power_watts: float
    scale_factor: float
    branch1_complex_power_watts: complex
    branch2_complex_power_watts: complex
    delivered_load_power_watts: float
    total_estimated_loss_watts: float
    estimated_efficiency_percent: float
    component_stresses: tuple[ComponentStress, ...]
    warnings: tuple[str, ...] = ()


def estimate_topology_b_stress(
    result: TopologyBResult,
    frequency_hz: float,
    z1: complex,
    z2: complex,
    input_power_watts: float,
    inductor_q: float = 250.0,
    capacitor_q: float = 1000.0,
    high_voltage_threshold_vrms: float = 1000.0,
    high_current_threshold_arms: float = 5.0,
    high_loss_threshold_watts: float = 5.0,
) -> TopologyBStressReport:
    """Estimate RMS component stress and Q loss for a Topology B result."""
    _require_positive("frequency_hz", frequency_hz)
    _require_positive("input_power_watts", input_power_watts)
    _require_positive("inductor_q", inductor_q)
    _require_positive("capacitor_q", capacitor_q)
    if z1 == 0 or z2 == 0:
        raise ValueError("z1 and z2 must be nonzero")

    input_voltage, input_current = _input_voltage_current_for_split_voltage(result)
    unscaled_input_power = (input_voltage * input_current.conjugate()).real
    if unscaled_input_power <= 0:
        raise ValueError("result must have positive input power for split_voltage=1")

    scale_factor = math.sqrt(input_power_watts / unscaled_input_power)
    scale2 = scale_factor**2
    topology_a = result.topology_a_result

    component_stresses = (
        _component_stress(
            name="L1",
            component_type="L",
            value_si=result.l1_h,
            frequency_hz=frequency_hz,
            rms_voltage=abs(topology_a.i_branch1 * _inductor_reactance(result.l1_h, frequency_hz) * scale_factor),
            rms_current=abs(topology_a.i_branch1 * scale_factor),
            q=inductor_q,
            high_voltage_threshold_vrms=high_voltage_threshold_vrms,
            high_current_threshold_arms=high_current_threshold_arms,
            high_loss_threshold_watts=high_loss_threshold_watts,
        ),
        _component_stress(
            name="C1",
            component_type="C",
            value_si=result.c1_f,
            frequency_hz=frequency_hz,
            rms_voltage=abs(topology_a.v_port1 * scale_factor),
            rms_current=abs((topology_a.v_port1 / _capacitor_impedance(result.c1_f, frequency_hz)) * scale_factor),
            q=capacitor_q,
            high_voltage_threshold_vrms=high_voltage_threshold_vrms,
            high_current_threshold_arms=high_current_threshold_arms,
            high_loss_threshold_watts=high_loss_threshold_watts,
        ),
        _component_stress(
            name="C2",
            component_type="C",
            value_si=result.c2_f,
            frequency_hz=frequency_hz,
            rms_voltage=abs(topology_a.i_branch2 * _capacitor_impedance(result.c2_f, frequency_hz) * scale_factor),
            rms_current=abs(topology_a.i_branch2 * scale_factor),
            q=capacitor_q,
            high_voltage_threshold_vrms=high_voltage_threshold_vrms,
            high_current_threshold_arms=high_current_threshold_arms,
            high_loss_threshold_watts=high_loss_threshold_watts,
        ),
        _component_stress(
            name="L2",
            component_type="L",
            value_si=result.l2_h,
            frequency_hz=frequency_hz,
            rms_voltage=abs(topology_a.v_port2 * scale_factor),
            rms_current=abs((topology_a.v_port2 / _inductor_impedance(result.l2_h, frequency_hz)) * scale_factor),
            q=inductor_q,
            high_voltage_threshold_vrms=high_voltage_threshold_vrms,
            high_current_threshold_arms=high_current_threshold_arms,
            high_loss_threshold_watts=high_loss_threshold_watts,
        ),
        *_input_match_component_stresses(
            result=result,
            frequency_hz=frequency_hz,
            scale_factor=scale_factor,
            inductor_q=inductor_q,
            capacitor_q=capacitor_q,
            high_voltage_threshold_vrms=high_voltage_threshold_vrms,
            high_current_threshold_arms=high_current_threshold_arms,
            high_loss_threshold_watts=high_loss_threshold_watts,
        ),
    )

    branch1_power = (
        topology_a.v_port1 * (topology_a.v_port1 / z1).conjugate() * scale2
    )
    branch2_power = (
        topology_a.v_port2 * (topology_a.v_port2 / z2).conjugate() * scale2
    )
    delivered_load_power = branch1_power.real + branch2_power.real
    total_loss = sum(stress.loss_watts for stress in component_stresses)
    efficiency = (
        delivered_load_power / (delivered_load_power + total_loss) * 100.0
        if delivered_load_power + total_loss > 0
        else 0.0
    )
    warnings = tuple(
        f"{stress.name}:{warning}"
        for stress in component_stresses
        for warning in stress.warnings
    )

    return TopologyBStressReport(
        input_power_watts=input_power_watts,
        scale_factor=scale_factor,
        branch1_complex_power_watts=branch1_power,
        branch2_complex_power_watts=branch2_power,
        delivered_load_power_watts=delivered_load_power,
        total_estimated_loss_watts=total_loss,
        estimated_efficiency_percent=efficiency,
        component_stresses=component_stresses,
        warnings=warnings,
    )


def estimate_topology_b_stress_from_case(
    result: TopologyBResult,
    case_data: dict[str, Any],
) -> TopologyBStressReport:
    """Estimate stress using frequency, loads, power, and Q values from case data."""
    assumptions = case_data.get("component_assumptions", {})
    return estimate_topology_b_stress(
        result=result,
        frequency_hz=case_data["frequency_hz"],
        z1=complex(
            case_data["ports"]["port1"]["z_ohms"]["r"],
            case_data["ports"]["port1"]["z_ohms"]["x"],
        ),
        z2=complex(
            case_data["ports"]["port2"]["z_ohms"]["r"],
            case_data["ports"]["port2"]["z_ohms"]["x"],
        ),
        input_power_watts=case_data["power_watts"],
        inductor_q=assumptions.get("inductor_q", 250.0),
        capacitor_q=assumptions.get("capacitor_q", 1000.0),
    )


def _input_match_component_stresses(
    result: TopologyBResult,
    frequency_hz: float,
    scale_factor: float,
    inductor_q: float,
    capacitor_q: float,
    high_voltage_threshold_vrms: float,
    high_current_threshold_arms: float,
    high_loss_threshold_watts: float,
) -> tuple[ComponentStress, ComponentStress]:
    solution = result.lmatch_solution
    split_voltage = 1 + 0j
    series_z = 1j * solution.series_reactance_ohms
    shunt_z = 1j * solution.shunt_reactance_ohms

    if solution.match_orientation == "series-then-shunt":
        parallel_section = parallel_impedance(result.z_split, shunt_z)
        series_current = split_voltage / parallel_section
        series_voltage = series_current * series_z
        shunt_voltage = split_voltage
        shunt_current = split_voltage / shunt_z
    elif solution.match_orientation == "shunt-then-series":
        series_current = split_voltage / result.z_split
        series_voltage = series_current * series_z
        input_voltage = split_voltage + series_voltage
        shunt_voltage = input_voltage
        shunt_current = input_voltage / shunt_z
    else:
        raise ValueError(f"unknown match orientation: {solution.match_orientation}")

    return (
        _component_stress(
            name="input_series",
            component_type=solution.series_component_type,
            value_si=solution.series_value_si,
            frequency_hz=frequency_hz,
            rms_voltage=abs(series_voltage * scale_factor),
            rms_current=abs(series_current * scale_factor),
            q=inductor_q if solution.series_component_type == "L" else capacitor_q,
            high_voltage_threshold_vrms=high_voltage_threshold_vrms,
            high_current_threshold_arms=high_current_threshold_arms,
            high_loss_threshold_watts=high_loss_threshold_watts,
        ),
        _component_stress(
            name="input_shunt",
            component_type=solution.shunt_component_type,
            value_si=solution.shunt_value_si,
            frequency_hz=frequency_hz,
            rms_voltage=abs(shunt_voltage * scale_factor),
            rms_current=abs(shunt_current * scale_factor),
            q=inductor_q if solution.shunt_component_type == "L" else capacitor_q,
            high_voltage_threshold_vrms=high_voltage_threshold_vrms,
            high_current_threshold_arms=high_current_threshold_arms,
            high_loss_threshold_watts=high_loss_threshold_watts,
        ),
    )


def _input_voltage_current_for_split_voltage(
    result: TopologyBResult,
) -> tuple[complex, complex]:
    solution = result.lmatch_solution
    split_voltage = 1 + 0j
    series_z = 1j * solution.series_reactance_ohms
    shunt_z = 1j * solution.shunt_reactance_ohms

    if solution.match_orientation == "series-then-shunt":
        parallel_section = parallel_impedance(result.z_split, shunt_z)
        series_current = split_voltage / parallel_section
        input_voltage = split_voltage + series_current * series_z
        return input_voltage, series_current

    if solution.match_orientation == "shunt-then-series":
        series_current = split_voltage / result.z_split
        input_voltage = split_voltage + series_current * series_z
        input_current = series_current + input_voltage / shunt_z
        return input_voltage, input_current

    raise ValueError(f"unknown match orientation: {solution.match_orientation}")


def _component_stress(
    name: str,
    component_type: str,
    value_si: float,
    frequency_hz: float,
    rms_voltage: float,
    rms_current: float,
    q: float,
    high_voltage_threshold_vrms: float,
    high_current_threshold_arms: float,
    high_loss_threshold_watts: float,
) -> ComponentStress:
    reactance = _component_reactance(component_type, value_si, frequency_hz)
    esr = abs(reactance) / q
    loss = rms_current**2 * esr
    warnings = []
    if rms_voltage >= high_voltage_threshold_vrms:
        warnings.append("high_voltage")
    if rms_current >= high_current_threshold_arms:
        warnings.append("high_current")
    if loss >= high_loss_threshold_watts:
        warnings.append("high_loss")

    return ComponentStress(
        name=name,
        component_type=component_type,
        value_si=value_si,
        reactance_ohms=reactance,
        esr_ohms=esr,
        rms_voltage=rms_voltage,
        rms_current=rms_current,
        loss_watts=loss,
        warnings=tuple(warnings),
    )


def _component_reactance(
    component_type: str,
    value_si: float,
    frequency_hz: float,
) -> float:
    if component_type == "L":
        return _inductor_reactance(value_si, frequency_hz)
    if component_type == "C":
        return abs(_capacitor_reactance(value_si, frequency_hz))
    raise ValueError(f"unknown component type: {component_type}")


def _inductor_impedance(value_h: float, frequency_hz: float) -> complex:
    return 1j * _inductor_reactance(value_h, frequency_hz)


def _capacitor_impedance(value_f: float, frequency_hz: float) -> complex:
    return -1j * _capacitor_reactance(value_f, frequency_hz)


def _inductor_reactance(value_h: float, frequency_hz: float) -> float:
    return _omega(frequency_hz) * value_h


def _capacitor_reactance(value_f: float, frequency_hz: float) -> float:
    return 1.0 / (_omega(frequency_hz) * value_f)


def _require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")


def _omega(frequency_hz: float) -> float:
    return 2.0 * math.pi * frequency_hz
