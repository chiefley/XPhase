import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pns.cases import load_case  # noqa: E402
from pns.ltspice import write_topology_b_ltspice_netlist  # noqa: E402
from pns.optimize import optimize_topology_b_from_case  # noqa: E402
from pns.stress import estimate_topology_b_stress_from_case  # noqa: E402


def main() -> None:
    args = _parse_args()
    case_path = REPO_ROOT / "cases" / "40m_inverted_v_90ft_feedlines.json"
    case_data = load_case(case_path)
    result = optimize_topology_b_from_case(case_data)
    match = result.input_match_solution
    stress = estimate_topology_b_stress_from_case(result.result, case_data)
    worst_capacitor = _worst_component(stress.component_stresses, "C", "rms_voltage")
    worst_inductor = _worst_component(stress.component_stresses, "L", "rms_current")
    highest_loss = max(stress.component_stresses, key=lambda item: item.loss_watts)

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

    if args.write_ltspice:
        output_path = REPO_ROOT / "ltspice" / "xphase_40m_topology_b.cir"
        written_path = write_topology_b_ltspice_netlist(
            path=output_path,
            topology_b_result=result.result,
            frequency_hz=case_data["frequency_hz"],
            z1=complex(
                case_data["ports"]["port1"]["z_ohms"]["r"],
                case_data["ports"]["port1"]["z_ohms"]["x"],
            ),
            z2=complex(
                case_data["ports"]["port2"]["z_ohms"]["r"],
                case_data["ports"]["port2"]["z_ohms"]["x"],
            ),
            output_power_watts=case_data["power_watts"],
            inductor_q=case_data["component_assumptions"]["inductor_q"],
            capacitor_q=case_data["component_assumptions"]["capacitor_q"],
        )
        print(f"LTspice netlist: {written_path.relative_to(REPO_ROOT)}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optimize the shipped 40m Topology B case."
    )
    parser.add_argument(
        "--write-ltspice",
        action="store_true",
        help="write ltspice/xphase_40m_topology_b.cir",
    )
    return parser.parse_args()


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
