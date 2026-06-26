import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pns.cases import load_case  # noqa: E402
from pns.feedline_sweep import (  # noqa: E402
    format_component_value,
    optimize_equal_length_feedline_sweep,
    practical_warnings,
)


def main() -> None:
    args = _parse_args()
    case_path = REPO_ROOT / "cases" / "40m_inverted_v_feedpoints_plus_y_7020khz.json"
    case_data = load_case(case_path)
    frequency_hz = case_data["frequency_hz"]
    z1_feedpoint = _port_impedance(case_data, "port1")
    z2_feedpoint = _port_impedance(case_data, "port2")
    target = case_data["target"]["voltage_ratio_v2_over_v1"]
    target_input = complex(
        case_data["target"]["input_impedance_ohms"]["r"],
        case_data["target"]["input_impedance_ohms"]["x"],
    )

    print("Equal-length center-frequency feedline sweep only.")
    print("This is not bandwidth evaluation, current-ratio optimization, or NEC pattern verification.")
    print(f"case: {case_data['name']}")
    print(f"frequency: {frequency_hz:.6g} Hz")
    print(f"target V2/V1: {target['magnitude']:.6g} angle {target['phase_deg']:.6g} deg")
    print("coax: Z0=50 ohms, VF=0.66")
    print("sweep: port1_length = port2_length = 60 ft to 90 ft by 5 ft")
    print("")

    results = optimize_equal_length_feedline_sweep(
        z1_feedpoint_ohms=z1_feedpoint,
        z2_feedpoint_ohms=z2_feedpoint,
        frequency_hz=frequency_hz,
        target_voltage_ratio_magnitude=target["magnitude"],
        target_voltage_ratio_phase_deg=target["phase_deg"],
        target_input_impedance_ohms=target_input,
        characteristic_impedance_ohms=50.0,
        velocity_factor=0.66,
        start_length=60.0,
        stop_length=90.0,
        step=5.0,
        length_unit="ft",
        input_power_watts=case_data["power_watts"],
        inductor_q=case_data["component_assumptions"]["inductor_q"],
        capacitor_q=case_data["component_assumptions"]["capacitor_q"],
    )
    displayed_results = results if args.show_all else results[: args.limit]

    print(
        "rank  len(ft)  Z1box(ohms)          Z2box(ohms)          "
        "|V2/V1|  phase     Zin(ohms)          SWR      score      loss  eff"
    )
    for rank, result in enumerate(displayed_results, start=1):
        print(
            f"{rank:>4}  "
            f"{result.candidate.common_length:>7.1f}  "
            f"{_format_impedance(result.candidate.port1_box_impedance_ohms):>19}  "
            f"{_format_impedance(result.candidate.port2_box_impedance_ohms):>19}  "
            f"{result.achieved_ratio_magnitude:>7.4f}  "
            f"{result.achieved_ratio_phase_deg:>7.2f}  "
            f"{_format_impedance(result.zin_ohms):>18}  "
            f"{result.swr:>7.4f}  "
            f"{result.score_or_objective:>9.3g}  "
            f"{_format_loss(result):>5}  "
            f"{_format_efficiency(result):>5}"
        )
        print(f"      network: {_format_branch_components(result)}")
        print(f"      input match: {_format_input_match(result)}")
        print(f"      stress: {_format_stress_summary(result)}")
        warnings = practical_warnings(result)
        if warnings:
            print(f"      warnings: {', '.join(warnings)}")
        else:
            print("      warnings: none")

    if not args.show_all and len(results) > len(displayed_results):
        print("")
        print(
            f"showing top {len(displayed_results)} of {len(results)} candidates; "
            "use --show-all to print every result"
        )


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an equal-length center-frequency feedline sweep."
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=5,
        help="number of ranked candidates to show unless --show-all is used",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="show every sweep result",
    )
    return parser.parse_args(argv)


def _port_impedance(case_data: dict, port_name: str) -> complex:
    parts = case_data["ports"][port_name]["z_ohms"]
    return complex(parts["r"], parts["x"])


def _format_impedance(value: complex) -> str:
    return f"{value.real:.3f}{value.imag:+.3f}j"


def _format_branch_components(result) -> str:
    comp = result.optimization_result.components
    return (
        f"L1={format_component_value('L', comp.l1_h)}, "
        f"C1={format_component_value('C', comp.c1_f)}, "
        f"C2={format_component_value('C', comp.c2_f)}, "
        f"L2={format_component_value('L', comp.l2_h)}"
    )


def _format_input_match(result) -> str:
    match = result.optimization_result.input_match_solution
    return (
        f"{match.topology_name} ({match.match_orientation}), "
        f"series {match.series_component_type}="
        f"{format_component_value(match.series_component_type, match.series_value_si)}, "
        f"shunt {match.shunt_component_type}="
        f"{format_component_value(match.shunt_component_type, match.shunt_value_si)}"
    )


def _format_loss(result) -> str:
    if result.stress_report is None:
        return "n/a"
    return f"{result.stress_report.total_estimated_loss_watts:.2f}W"


def _format_efficiency(result) -> str:
    if result.stress_report is None:
        return "n/a"
    return f"{result.stress_report.estimated_efficiency_percent:.1f}%"


def _format_stress_summary(result) -> str:
    if result.stress_report is None:
        return "n/a"
    worst_voltage = max(
        result.stress_report.component_stresses,
        key=lambda component: component.rms_voltage,
    )
    worst_current = max(
        result.stress_report.component_stresses,
        key=lambda component: component.rms_current,
    )
    highest_loss = max(
        result.stress_report.component_stresses,
        key=lambda component: component.loss_watts,
    )
    return (
        f"Vmax {worst_voltage.name}={worst_voltage.rms_voltage:.1f} Vrms, "
        f"Imax {worst_current.name}={worst_current.rms_current:.2f} Arms, "
        f"Ploss max {highest_loss.name}={highest_loss.loss_watts:.2f} W"
    )


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("limit must be greater than 0")
    return parsed


if __name__ == "__main__":
    main()
