from copy import deepcopy
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pns.cases import load_case  # noqa: E402
from pns.feedline import (  # noqa: E402
    LosslessCoaxLine,
    feet_to_meters,
    transform_two_feedpoints_to_box_end,
)
from pns.optimize import optimize_topology_b_from_case  # noqa: E402
from pns.stress import estimate_topology_b_stress_from_case  # noqa: E402


def main() -> None:
    case_path = REPO_ROOT / "cases" / "40m_inverted_v_feedpoints_plus_y_7020khz.json"
    case_data = load_case(case_path)
    frequency_hz = case_data["frequency_hz"]

    feedpoint1 = _port_impedance(case_data, "port1")
    feedpoint2 = _port_impedance(case_data, "port2")
    line1 = _feedline(case_data, "port1")
    line2 = _feedline(case_data, "port2")

    box_end1, box_end2 = transform_two_feedpoints_to_box_end(
        feedpoint1,
        feedpoint2,
        frequency_hz,
        line1,
        line2,
    )
    optimizer_case = _case_with_box_end_impedances(case_data, box_end1, box_end2)
    result = optimize_topology_b_from_case(optimizer_case)
    match = result.input_match_solution
    stress = estimate_topology_b_stress_from_case(result.result, optimizer_case)
    worst_capacitor = _worst_component(stress.component_stresses, "C", "rms_voltage")
    worst_inductor = _worst_component(stress.component_stresses, "L", "rms_current")
    highest_loss = max(stress.component_stresses, key=lambda item: item.loss_watts)

    target = case_data["target"]["voltage_ratio_v2_over_v1"]
    future_current_target = case_data["target"]["future_current_ratio_i2_over_i1"]

    print(f"case: {case_data['name']}")
    print(f"frequency: {frequency_hz:.6g} Hz")
    print(f"forward direction: {case_data['pattern']['desired_forward_direction']}")
    print("feedpoint impedances from NEC:")
    print(f"  port1 rear -Y: {_format_impedance(feedpoint1)} ohms")
    print(f"  port2 forward +Y: {_format_impedance(feedpoint2)} ohms")
    print("fixed lossless feedlines:")
    print(_format_line("  port1", line1))
    print(_format_line("  port2", line2))
    print("box-end impedances for optimizer:")
    print(f"  port1: {_format_impedance(box_end1)} ohms")
    print(f"  port2: {_format_impedance(box_end2)} ohms")
    print(
        "voltage target V2/V1: "
        f"{target['magnitude']:.6g} angle {target['phase_deg']:.6g} deg"
    )
    print(
        "future current target I2/I1: "
        f"{future_current_target['magnitude']:.6g} "
        f"angle {future_current_target['phase_deg']:.6g} deg "
        f"({future_current_target['status']})"
    )
    print("")
    print(f"success: {result.success}")
    print(f"message: {result.message}")
    print(f"L1: {result.components.l1_h:.6g} H")
    print(f"C1: {result.components.c1_f:.6g} F")
    print(f"C2: {result.components.c2_f:.6g} F")
    print(f"L2: {result.components.l2_h:.6g} H")
    print(f"input match: {match.topology_name} ({match.match_orientation})")
    print(
        "input series: "
        f"{match.series_component_type} = "
        f"{_format_value(match.series_component_type, match.series_value_si)}"
    )
    print(
        "input shunt: "
        f"{match.shunt_component_type} = "
        f"{_format_value(match.shunt_component_type, match.shunt_value_si)}"
    )
    print(
        f"V2/V1: {result.v_ratio_magnitude:.6g} "
        f"angle {result.v_ratio_phase_deg:.6g} deg"
    )
    print(
        "Zin: "
        f"{result.z_input.real:.6g} "
        f"{result.z_input.imag:+.6g}j ohms"
    )
    print(f"SWR: {result.swr:.6g}")
    print(f"score: {result.score.total_score:.6g}")
    print("stress at 100 W:")
    print(
        "  branch powers: "
        f"P1={stress.branch1_complex_power_watts.real:.3f} W, "
        f"P2={stress.branch2_complex_power_watts.real:.3f} W"
    )
    print(f"  total loss: {stress.total_estimated_loss_watts:.3f} W")
    print(f"  efficiency: {stress.estimated_efficiency_percent:.2f}%")
    print(
        "  worst capacitor voltage: "
        f"{worst_capacitor.name}={worst_capacitor.rms_voltage:.1f} Vrms"
    )
    print(
        "  worst inductor current: "
        f"{worst_inductor.name}={worst_inductor.rms_current:.2f} Arms"
    )
    print(
        "  highest-loss component: "
        f"{highest_loss.name}={highest_loss.loss_watts:.3f} W"
    )


def _port_impedance(case_data: dict, port_name: str) -> complex:
    parts = case_data["ports"][port_name]["z_ohms"]
    return complex(parts["r"], parts["x"])


def _feedline(case_data: dict, port_name: str) -> LosslessCoaxLine:
    values = case_data["fixed_feedlines"][port_name]
    return LosslessCoaxLine(
        characteristic_impedance_ohms=values["characteristic_impedance_ohms"],
        velocity_factor=values["velocity_factor"],
        length_m=feet_to_meters(values["length_ft"]),
    )


def _case_with_box_end_impedances(
    case_data: dict,
    box_end1: complex,
    box_end2: complex,
) -> dict:
    transformed = deepcopy(case_data)
    transformed["reference_plane"] = "phasing_box_end"
    transformed["ports"]["port1"]["reference_plane"] = "phasing_box_end"
    transformed["ports"]["port1"]["z_ohms"] = {
        "r": box_end1.real,
        "x": box_end1.imag,
    }
    transformed["ports"]["port2"]["reference_plane"] = "phasing_box_end"
    transformed["ports"]["port2"]["z_ohms"] = {
        "r": box_end2.real,
        "x": box_end2.imag,
    }
    return transformed


def _format_line(label: str, line: LosslessCoaxLine) -> str:
    length_ft = line.length_m / 0.3048
    return (
        f"{label}: Z0={line.characteristic_impedance_ohms:.6g} ohms, "
        f"VF={line.velocity_factor:.6g}, length={length_ft:.3f} ft"
    )


def _format_impedance(value: complex) -> str:
    return f"{value.real:.6g} {value.imag:+.6g}j"


def _format_value(component_type: str, value: float) -> str:
    unit = "H" if component_type == "L" else "F"
    return f"{value:.6g} {unit}"


def _worst_component(components, component_type: str, field_name: str):
    return max(
        (component for component in components if component.component_type == component_type),
        key=lambda component: getattr(component, field_name),
    )


if __name__ == "__main__":
    main()
