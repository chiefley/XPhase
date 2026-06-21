"""LTspice netlist export helpers."""

from __future__ import annotations

from pathlib import Path
import math

from pns.topology_b import TopologyBResult


def export_topology_b_ltspice_netlist(
    topology_b_result: TopologyBResult,
    frequency_hz: float,
    z1: complex,
    z2: complex,
    output_power_watts: float = 100.0,
    include_loss: bool = True,
    inductor_q: float = 250.0,
    capacitor_q: float = 1000.0,
) -> str:
    """Export a Topology B result as a plain LTspice-compatible .cir netlist."""
    _require_positive("frequency_hz", frequency_hz)
    _require_positive("output_power_watts", output_power_watts)
    _require_positive("inductor_q", inductor_q)
    _require_positive("capacitor_q", capacitor_q)
    if z1.real <= 0 or z2.real <= 0:
        raise ValueError("load impedances must have positive resistance")

    source_ac_voltage = math.sqrt(output_power_watts * 50.0)
    start_hz = frequency_hz * 0.8
    stop_hz = frequency_hz * 1.2
    lines = [
        "* XPhase Topology B export",
        "* Plain .cir netlist for independent AC verification.",
        f"* Frequency: {_format_number(frequency_hz)} Hz",
        "* AC source magnitude uses sqrt(Pout * 50 ohms) as an RMS-style convention.",
        "* Inspect V(port2)/V(port1) for the phasing target.",
        "* Inspect V(input)/I(Vsrc) with source resistance de-embedded for input impedance.",
        f"Vsrc input_src 0 AC {_format_number(source_ac_voltage)}",
        "Rsrc input_src input 50",
        "",
        "* Input matching section",
    ]

    _append_input_match(lines, topology_b_result, frequency_hz, include_loss, inductor_q, capacitor_q)
    lines.extend(
        [
            "",
            "* Topology A branch networks",
        ]
    )
    _append_series_component(
        lines,
        name="L1",
        component_type="L",
        value_si=topology_b_result.l1_h,
        node_a="split",
        node_b="port1",
        frequency_hz=frequency_hz,
        include_loss=include_loss,
        q=inductor_q,
    )
    _append_shunt_component(
        lines,
        name="C1",
        component_type="C",
        value_si=topology_b_result.c1_f,
        node="port1",
        frequency_hz=frequency_hz,
        include_loss=include_loss,
        q=capacitor_q,
    )
    _append_series_component(
        lines,
        name="C2",
        component_type="C",
        value_si=topology_b_result.c2_f,
        node_a="split",
        node_b="port2",
        frequency_hz=frequency_hz,
        include_loss=include_loss,
        q=capacitor_q,
    )
    _append_shunt_component(
        lines,
        name="L2",
        component_type="L",
        value_si=topology_b_result.l2_h,
        node="port2",
        frequency_hz=frequency_hz,
        include_loss=include_loss,
        q=inductor_q,
    )

    lines.extend(
        [
            "",
            "* Complex antenna/feedline port loads",
        ]
    )
    _append_complex_load(lines, "1", "port1", z1, frequency_hz)
    _append_complex_load(lines, "2", "port2", z2, frequency_hz)

    lines.extend(
        [
            "",
            "* AC analysis around the operating frequency",
            f".ac dec 101 {_format_number(start_hz)} {_format_number(stop_hz)}",
            "",
            "* Measurement/inspection helpers",
            ".meas ac Vratio_mag PARAM mag(V(port2)/V(port1))",
            ".meas ac Vport1_mag PARAM mag(V(port1))",
            ".meas ac Vport2_mag PARAM mag(V(port2))",
            ".meas ac Ibranch1_mag PARAM mag(I(L1))",
            ".meas ac Ibranch2_mag PARAM mag(I(C2))",
            "* Capacitor voltage checks: V(port1), V(split,port2), and input-match capacitor node pair.",
            "* Inductor current checks: I(L1), I(L2), and input-match inductor current.",
            "* SWR check: compute Zin from input-node voltage/current after accounting for Rsrc.",
            ".end",
        ]
    )
    return "\n".join(lines) + "\n"


def write_topology_b_ltspice_netlist(
    path: str | Path,
    topology_b_result: TopologyBResult,
    frequency_hz: float,
    z1: complex,
    z2: complex,
    output_power_watts: float = 100.0,
    include_loss: bool = True,
    inductor_q: float = 250.0,
    capacitor_q: float = 1000.0,
) -> Path:
    """Write a Topology B LTspice netlist and return the written path."""
    netlist = export_topology_b_ltspice_netlist(
        topology_b_result=topology_b_result,
        frequency_hz=frequency_hz,
        z1=z1,
        z2=z2,
        output_power_watts=output_power_watts,
        include_loss=include_loss,
        inductor_q=inductor_q,
        capacitor_q=capacitor_q,
    )
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(netlist, encoding="utf-8")
    return output_path


def _append_input_match(
    lines: list[str],
    result: TopologyBResult,
    frequency_hz: float,
    include_loss: bool,
    inductor_q: float,
    capacitor_q: float,
) -> None:
    solution = result.lmatch_solution
    series_name = _input_component_name("series", solution.series_component_type)
    shunt_name = _input_component_name("shunt", solution.shunt_component_type)

    if solution.match_orientation == "series-then-shunt":
        _append_series_component(
            lines,
            name=series_name,
            component_type=solution.series_component_type,
            value_si=solution.series_value_si,
            node_a="input",
            node_b="split",
            frequency_hz=frequency_hz,
            include_loss=include_loss,
            q=inductor_q if solution.series_component_type == "L" else capacitor_q,
        )
        _append_shunt_component(
            lines,
            name=shunt_name,
            component_type=solution.shunt_component_type,
            value_si=solution.shunt_value_si,
            node="split",
            frequency_hz=frequency_hz,
            include_loss=include_loss,
            q=inductor_q if solution.shunt_component_type == "L" else capacitor_q,
        )
        return

    if solution.match_orientation == "shunt-then-series":
        _append_shunt_component(
            lines,
            name=shunt_name,
            component_type=solution.shunt_component_type,
            value_si=solution.shunt_value_si,
            node="input",
            frequency_hz=frequency_hz,
            include_loss=include_loss,
            q=inductor_q if solution.shunt_component_type == "L" else capacitor_q,
        )
        _append_series_component(
            lines,
            name=series_name,
            component_type=solution.series_component_type,
            value_si=solution.series_value_si,
            node_a="input",
            node_b="split",
            frequency_hz=frequency_hz,
            include_loss=include_loss,
            q=inductor_q if solution.series_component_type == "L" else capacitor_q,
        )
        return

    raise ValueError(f"unknown match orientation: {solution.match_orientation}")


def _append_series_component(
    lines: list[str],
    name: str,
    component_type: str,
    value_si: float,
    node_a: str,
    node_b: str,
    frequency_hz: float,
    include_loss: bool,
    q: float,
) -> None:
    _require_supported_component(component_type)
    if include_loss:
        esr_node = f"{name.lower()}_esr"
        lines.append(f"R{name}_ESR {node_a} {esr_node} {_format_number(_component_esr(component_type, value_si, frequency_hz, q))}")
        lines.append(f"{name} {esr_node} {node_b} {_format_number(value_si)}")
    else:
        lines.append(f"{name} {node_a} {node_b} {_format_number(value_si)}")


def _append_shunt_component(
    lines: list[str],
    name: str,
    component_type: str,
    value_si: float,
    node: str,
    frequency_hz: float,
    include_loss: bool,
    q: float,
) -> None:
    _require_supported_component(component_type)
    if include_loss:
        esr_node = f"{name.lower()}_esr"
        lines.append(f"R{name}_ESR {node} {esr_node} {_format_number(_component_esr(component_type, value_si, frequency_hz, q))}")
        lines.append(f"{name} {esr_node} 0 {_format_number(value_si)}")
    else:
        lines.append(f"{name} {node} 0 {_format_number(value_si)}")


def _append_complex_load(
    lines: list[str],
    suffix: str,
    port_node: str,
    impedance: complex,
    frequency_hz: float,
) -> None:
    reactance_node = f"load{suffix}_x"
    lines.append(f"Rload{suffix} {port_node} {reactance_node} {_format_number(impedance.real)}")

    if impedance.imag > 0:
        value = impedance.imag / _omega(frequency_hz)
        lines.append(f"Lload{suffix} {reactance_node} 0 {_format_number(value)}")
    elif impedance.imag < 0:
        value = 1.0 / (_omega(frequency_hz) * abs(impedance.imag))
        lines.append(f"Cload{suffix} {reactance_node} 0 {_format_number(value)}")
    else:
        lines.append(f"Rload{suffix}_x_short {reactance_node} 0 1u")


def _input_component_name(position: str, component_type: str) -> str:
    prefix = "Lm" if component_type == "L" else "Cm"
    return f"{prefix}_{position}"


def _component_esr(
    component_type: str,
    value_si: float,
    frequency_hz: float,
    q: float,
) -> float:
    _require_positive("q", q)
    if component_type == "L":
        reactance = _omega(frequency_hz) * value_si
    elif component_type == "C":
        reactance = 1.0 / (_omega(frequency_hz) * value_si)
    else:
        raise ValueError(f"unknown component type: {component_type}")
    return abs(reactance) / q


def _require_supported_component(component_type: str) -> None:
    if component_type not in {"L", "C"}:
        raise ValueError(f"unknown component type: {component_type}")


def _require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")


def _omega(frequency_hz: float) -> float:
    return 2.0 * math.pi * frequency_hz


def _format_number(value: float) -> str:
    return f"{value:.12g}"
