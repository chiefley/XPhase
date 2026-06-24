"""ngspice batch verification helpers."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

from pns.ltspice import (
    _append_complex_load,
    _append_input_match,
    _append_series_component,
    _append_shunt_component,
    _format_number,
    thevenin_source_voltage_for_matched_power,
)
from pns.topology_b import TopologyBResult


def find_ngspice_executable() -> str | None:
    """Return the ngspice executable path if it is available on PATH."""
    return shutil.which("ngspice")


def export_topology_b_ngspice_netlist(
    topology_b_result: TopologyBResult,
    frequency_hz: float,
    z1: complex,
    z2: complex,
    output_power_watts: float = 100.0,
    z0: float = 50.0,
    include_loss: bool = True,
    inductor_q: float = 250.0,
    capacitor_q: float = 1000.0,
) -> str:
    """Export a Topology B result as a plain ngspice-compatible .cir netlist."""
    _require_positive("frequency_hz", frequency_hz)
    _require_positive("output_power_watts", output_power_watts)
    _require_positive("z0", z0)
    _require_positive("inductor_q", inductor_q)
    _require_positive("capacitor_q", capacitor_q)
    if z1.real <= 0 or z2.real <= 0:
        raise ValueError("load impedances must have positive resistance")

    source_ac_voltage = thevenin_source_voltage_for_matched_power(
        output_power_watts,
        z0,
    )
    input_series_name = _input_series_component_name(topology_b_result)
    lines = [
        "* XPhase Topology B ngspice verification export",
        "* Plain .cir netlist for automated AC verification.",
        f"* Frequency: {_format_number(frequency_hz)} Hz",
        f"* Vsrc is the Thevenin source voltage with Rsrc={_format_number(z0)} ohms.",
        f"Vsrc input_src 0 AC {_format_number(source_ac_voltage)}",
        f"Rsrc input_src input {_format_number(z0)}",
        "",
        "* Input matching section",
        f"* Match label: {topology_b_result.input_match_topology_name}, {topology_b_result.lmatch_solution.match_orientation}",
    ]

    _append_input_match(
        lines,
        topology_b_result,
        frequency_hz,
        include_loss,
        inductor_q,
        capacitor_q,
    )
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
            "* Exact single-frequency AC analysis",
            f".ac lin 1 {_format_number(frequency_hz)} {_format_number(frequency_hz)}",
            "",
            ".control",
            "set noaskquit",
            "set numdgt=15",
            "run",
            "let xphase_vratio = v(port2) / v(port1)",
            "let xphase_vratio_mag = mag(xphase_vratio)",
            "let xphase_vratio_phase_deg = 180.0 / pi * phase(xphase_vratio)",
            "echo XPHASE_BEGIN",
            "print xphase_vratio",
            "print xphase_vratio_mag",
            "print xphase_vratio_phase_deg",
            "print v(input)",
            f"print i({input_series_name})",
            "print i(l1)",
            "print i(c2)",
            "print i(l2)",
            "echo XPHASE_END",
            "quit",
            ".endc",
            ".end",
        ]
    )
    return "\n".join(lines) + "\n"


def write_ngspice_netlist(
    path: str | Path,
    topology_b_result: TopologyBResult,
    frequency_hz: float,
    z1: complex,
    z2: complex,
    output_power_watts: float = 100.0,
    z0: float = 50.0,
    include_loss: bool = True,
    inductor_q: float = 250.0,
    capacitor_q: float = 1000.0,
) -> Path:
    """Write a Topology B ngspice netlist and return the written path."""
    output_path = Path(path)
    if output_path.suffix.lower() != ".cir":
        raise ValueError("ngspice netlist path must use a .cir extension")

    netlist = export_topology_b_ngspice_netlist(
        topology_b_result=topology_b_result,
        frequency_hz=frequency_hz,
        z1=z1,
        z2=z2,
        output_power_watts=output_power_watts,
        z0=z0,
        include_loss=include_loss,
        inductor_q=inductor_q,
        capacitor_q=capacitor_q,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(netlist, encoding="utf-8")
    return output_path


def run_ngspice_batch(
    netlist_path: str | Path,
    ngspice_executable: str | None = None,
) -> str:
    """Run ngspice in batch mode and return combined stdout/stderr text."""
    executable = ngspice_executable or find_ngspice_executable()
    if executable is None:
        raise FileNotFoundError("ngspice executable not found")

    result = subprocess.run(
        [executable, "-b", str(netlist_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout
    if result.stderr:
        output = f"{output}\n{result.stderr}" if output else result.stderr
    if result.returncode != 0:
        raise RuntimeError(f"ngspice failed with exit code {result.returncode}\n{output}")
    return output


def parse_ngspice_measurements(output_text: str) -> dict[str, float | complex]:
    """Parse XPhase control-block print output from ngspice."""
    measurements: dict[str, float | complex] = {}
    in_block = False
    for raw_line in output_text.splitlines():
        line = raw_line.strip()
        if line == "XPHASE_BEGIN":
            in_block = True
            continue
        if line == "XPHASE_END":
            break
        if not in_block:
            continue

        parsed = _parse_assignment(line)
        if parsed is None:
            continue
        name, value = parsed
        measurements[name] = value
    return measurements


def _parse_assignment(line: str) -> tuple[str, float | complex] | None:
    match = re.match(r"^([^=]+?)\s*=\s*(.+)$", line)
    if match is None:
        return None
    name = match.group(1).strip().lower()
    value_text = match.group(2).strip()
    return name, _parse_value(value_text)


def _parse_value(value_text: str) -> float | complex:
    complex_match = re.match(
        rf"^\(?\s*({_FLOAT_RE})\s*,\s*({_FLOAT_RE})\s*\)?$",
        value_text,
        flags=re.IGNORECASE,
    )
    if complex_match is not None:
        return complex(float(complex_match.group(1)), float(complex_match.group(2)))
    return float(value_text)


def _input_series_component_name(result: TopologyBResult) -> str:
    prefix = "lm" if result.lmatch_solution.series_component_type == "L" else "cm"
    return f"{prefix}_series"


def _require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")


_FLOAT_RE = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
