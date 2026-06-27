import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pns.cases import load_case  # noqa: E402
from pns.feedline_sweep import (  # noqa: E402
    optimize_equal_length_feedline_sweep,
    optimize_offset_feedline_sweep,
)
from pns.static_bandwidth import (  # noqa: E402
    evaluate_static_bandwidth_for_result,
    frequency_grid_hz,
    write_static_bandwidth_csv,
)
from pns.sweep_reporting import (  # noqa: E402
    format_impedance,
    format_optional_efficiency,
    format_optional_loss,
    practical_sort_key,
    summarize_sweep_result,
)


DEFAULT_CSV_PATH = REPO_ROOT / "reports" / "40m_static_bandwidth.csv"


def main() -> None:
    args = _parse_args()
    frequencies_hz = frequency_grid_hz(
        args.start_mhz * 1e6,
        args.stop_mhz * 1e6,
        args.step_khz * 1e3,
    )
    case_path = REPO_ROOT / "cases" / "40m_inverted_v_feedpoints_plus_y_7020khz.json"
    case_data = load_case(case_path)
    center_frequency_hz = case_data["frequency_hz"]
    z1_feedpoint = _port_impedance(case_data, "port1")
    z2_feedpoint = _port_impedance(case_data, "port2")
    target = case_data["target"]["voltage_ratio_v2_over_v1"]
    target_input = complex(
        case_data["target"]["input_impedance_ohms"]["r"],
        case_data["target"]["input_impedance_ohms"]["x"],
    )
    assumptions = case_data["component_assumptions"]

    equal_results, offset_results = _run_candidate_search(
        case_data,
        z1_feedpoint,
        z2_feedpoint,
        target_input,
    )
    selected_results = _select_results(equal_results, offset_results, args.limit)
    summaries = tuple(
        evaluate_static_bandwidth_for_result(
            result,
            z1_feedpoint_ohms=z1_feedpoint,
            z2_feedpoint_ohms=z2_feedpoint,
            center_frequency_hz=center_frequency_hz,
            frequencies_hz=frequencies_hz,
            target_voltage_ratio_magnitude=target["magnitude"],
            target_voltage_ratio_phase_deg=target["phase_deg"],
            target_input_impedance_ohms=target_input,
            characteristic_impedance_ohms=50.0,
            velocity_factor=0.66,
            input_power_watts=case_data["power_watts"],
            inductor_q=assumptions["inductor_q"],
            capacitor_q=assumptions["capacitor_q"],
        )
        for result in selected_results
    )

    print("Level 1 static/frozen network bandwidth evaluation.")
    print("Feedpoint impedances are held fixed at the center-frequency NEC case values.")
    print("Feedline electrical lengths vary with frequency.")
    print("Network components are frozen; no reoptimization is performed.")
    print("This is not NEC frequency-sweep bandwidth.")
    print(f"case: {case_data['name']}")
    print(f"center frequency: {center_frequency_hz / 1e6:.6f} MHz")
    print(
        f"evaluation grid: {frequencies_hz[0] / 1e6:.6f} to "
        f"{frequencies_hz[-1] / 1e6:.6f} MHz, {len(frequencies_hz)} points"
    )
    print("")

    for index, (source_result, summary) in enumerate(
        zip(selected_results, summaries),
        start=1,
    ):
        _print_summary(index, source_result, summary)

    if args.write_csv:
        csv_path = write_static_bandwidth_csv(args.csv_path, summaries)
        print(f"CSV written: {csv_path.resolve()}")


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate selected frozen 40 m networks over a frequency grid."
    )
    parser.add_argument(
        "--start-mhz",
        type=_positive_float,
        default=7.000,
        help="evaluation start frequency in MHz; default: 7.000",
    )
    parser.add_argument(
        "--stop-mhz",
        type=_positive_float,
        default=7.060,
        help="evaluation stop frequency in MHz; default: 7.060",
    )
    parser.add_argument(
        "--step-khz",
        type=_positive_float,
        default=10.0,
        help="frequency step in kHz; default: 10",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=3,
        help="maximum number of center-frequency candidates to evaluate; default: 3",
    )
    parser.add_argument(
        "--write-csv",
        action="store_true",
        help="write point-level static bandwidth results to CSV",
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"CSV output path when --write-csv is used; default: {DEFAULT_CSV_PATH}",
    )
    return parser.parse_args(argv)


def _run_candidate_search(case_data, z1_feedpoint, z2_feedpoint, target_input):
    target = case_data["target"]["voltage_ratio_v2_over_v1"]
    assumptions = case_data["component_assumptions"]
    common_kwargs = {
        "z1_feedpoint_ohms": z1_feedpoint,
        "z2_feedpoint_ohms": z2_feedpoint,
        "frequency_hz": case_data["frequency_hz"],
        "target_voltage_ratio_magnitude": target["magnitude"],
        "target_voltage_ratio_phase_deg": target["phase_deg"],
        "target_input_impedance_ohms": target_input,
        "characteristic_impedance_ohms": 50.0,
        "velocity_factor": 0.66,
        "length_unit": "ft",
        "maxiter": 30,
        "input_power_watts": case_data["power_watts"],
        "inductor_q": assumptions["inductor_q"],
        "capacitor_q": assumptions["capacitor_q"],
        "polarities": ("normal", "invert_port1", "invert_port2"),
    }
    equal_results = optimize_equal_length_feedline_sweep(
        **common_kwargs,
        start_length=60.0,
        stop_length=90.0,
        step=5.0,
    )
    offset_results = optimize_offset_feedline_sweep(
        **common_kwargs,
        start_common_length=75.0,
        stop_common_length=95.0,
        common_step=5.0,
        start_offset=-25.0,
        stop_offset=25.0,
        offset_step=5.0,
    )
    return equal_results, offset_results


def _select_results(equal_results, offset_results, limit: int):
    combined = (*equal_results, *offset_results)
    practical = tuple(
        sorted(combined, key=lambda result: practical_sort_key(summarize_sweep_result(result)))
    )
    preferred = (
        practical[0],
        next((result for result in equal_results if result.polarity != "normal"), None),
        next((result for result in practical if result.polarity == "normal"), None),
        *practical,
    )
    selected = []
    for result in preferred:
        if result is not None and result not in selected:
            selected.append(result)
        if len(selected) >= limit:
            break
    return tuple(selected)


def _print_summary(index, source_result, summary) -> None:
    center = summarize_sweep_result(source_result)
    print(
        f"Candidate {index}: {summary.candidate_label}  "
        f"mode={summary.mode}, polarity={summary.polarity}"
    )
    print(
        f"  feedlines: port1={summary.port1_length:g} {summary.length_unit}, "
        f"port2={summary.port2_length:g} {summary.length_unit}"
    )
    print(
        "  center stress: "
        f"loss={format_optional_loss(center.total_estimated_loss_watts)}, "
        f"efficiency={format_optional_efficiency(center.estimated_efficiency_percent)}"
    )
    print(
        f"  band summary: max SWR={summary.max_swr:.4f}, "
        f"max |magnitude error|={summary.max_magnitude_error:.5f}, "
        f"max |phase error|={summary.max_abs_phase_error_deg:.3f} deg, "
        f"max loss={format_optional_loss(summary.max_total_estimated_loss_watts)}, "
        f"min efficiency={format_optional_efficiency(summary.min_estimated_efficiency_percent)}"
    )
    print("  maximum per-component stress across band:")
    for component in summary.max_component_stresses:
        print(
            f"    {component.name:<13} "
            f"V={component.rms_voltage:>8.2f} Vrms  "
            f"I={component.rms_current:>7.3f} Arms  "
            f"loss={component.loss_watts:>7.3f} W"
        )
    print(
        "  frequency  |V2/V1|  phase(deg)  mag_error  phase_error  "
        "Zin(ohms)             SWR     loss    eff"
    )
    for point in summary.points:
        print(
            f"  {point.frequency_hz / 1e6:>8.3f}  "
            f"{point.achieved_ratio_magnitude:>7.4f}  "
            f"{point.achieved_ratio_phase_deg:>10.3f}  "
            f"{point.magnitude_error:>9.5f}  "
            f"{point.phase_error_deg:>11.3f}  "
            f"{format_impedance(point.zin_ohms):>20}  "
            f"{point.swr:>6.3f}  "
            f"{format_optional_loss(point.total_estimated_loss_watts):>7}  "
            f"{format_optional_efficiency(point.estimated_efficiency_percent):>6}"
        )
    print("")


def _port_impedance(case_data: dict, port_name: str) -> complex:
    parts = case_data["ports"][port_name]["z_ohms"]
    return complex(parts["r"], parts["x"])


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("limit must be greater than 0")
    return parsed


if __name__ == "__main__":
    main()
