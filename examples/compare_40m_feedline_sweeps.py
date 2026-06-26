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
from pns.sweep_reporting import (  # noqa: E402
    format_impedance,
    format_optional_current,
    format_optional_efficiency,
    format_optional_loss,
    format_optional_voltage,
    practical_sort_key,
    summarize_sweep_result,
    write_summaries_csv,
)


DEFAULT_CSV_PATH = REPO_ROOT / "reports" / "40m_feedline_sweep_comparison.csv"


def main() -> None:
    args = _parse_args()
    polarities = _selected_polarities(args.include_polarity_variants)
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
    common_kwargs = {
        "z1_feedpoint_ohms": z1_feedpoint,
        "z2_feedpoint_ohms": z2_feedpoint,
        "frequency_hz": frequency_hz,
        "target_voltage_ratio_magnitude": target["magnitude"],
        "target_voltage_ratio_phase_deg": target["phase_deg"],
        "target_input_impedance_ohms": target_input,
        "characteristic_impedance_ohms": 50.0,
        "velocity_factor": 0.66,
        "length_unit": "ft",
        "maxiter": 30,
        "input_power_watts": case_data["power_watts"],
        "inductor_q": case_data["component_assumptions"]["inductor_q"],
        "capacitor_q": case_data["component_assumptions"]["capacitor_q"],
        "polarities": polarities,
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
    equal_summaries = tuple(summarize_sweep_result(result) for result in equal_results)
    offset_summaries = tuple(summarize_sweep_result(result) for result in offset_results)
    practical_summaries = tuple(
        sorted((*equal_summaries, *offset_summaries), key=practical_sort_key)
    )
    combined_summaries = (*equal_summaries, *offset_summaries)

    print("Center-frequency feedline sweep comparison only.")
    print("This is not bandwidth evaluation, current-ratio optimization, or NEC pattern verification.")
    print(f"case: {case_data['name']}")
    print(f"frequency: {frequency_hz:.6g} Hz")
    print(f"target V2/V1: {target['magnitude']:.6g} angle {target['phase_deg']:.6g} deg")
    print("coax: Z0=50 ohms, VF=0.66")
    print("equal sweep: port1_length = port2_length = 60 ft to 90 ft by 5 ft")
    print("offset sweep: common 75 ft to 95 ft by 5 ft, offset -25 ft to +25 ft by 5 ft")
    print("offset convention: positive offset adds coax to port 2, the forward +Y reference source")
    if args.include_polarity_variants:
        print("polarity variants: normal, invert_port1, invert_port2")
        print("inverting either port shifts the optimizer V2/V1 target by 180 degrees")
    else:
        print("polarity variants: normal only")
    print("")

    _print_section("A: top mathematical equal-length candidates", equal_summaries, args)
    _print_section("B: top mathematical offset candidates", offset_summaries, args)
    _print_section("C: top practical-screen candidates from combined set", practical_summaries, args)

    if args.write_csv:
        csv_path = write_summaries_csv(
            args.csv_path,
            combined_summaries,
            practical_ordered_summaries=practical_summaries,
            math_rank_by_mode=_math_rank_by_mode(equal_summaries, offset_summaries),
        )
        print(f"CSV written: {csv_path.resolve()}")


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare equal-length and offset center-frequency feedline sweeps."
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=5,
        help="number of ranked candidates per section unless --show-all is used",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="show every result in each section",
    )
    parser.add_argument(
        "--write-csv",
        action="store_true",
        help="write the combined candidate set to CSV",
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"CSV output path when --write-csv is used; default: {DEFAULT_CSV_PATH}",
    )
    parser.add_argument(
        "--include-polarity-variants",
        action="store_true",
        help="also evaluate invert_port1 and invert_port2 target conventions",
    )
    return parser.parse_args(argv)


def _print_section(title: str, summaries, args: argparse.Namespace) -> None:
    displayed = summaries if args.show_all else summaries[: args.limit]
    print(title)
    print(
        "rank  mode          polarity       common  offset  p1_len  p2_len  "
        "SWR      score      loss    eff    worstV       worstI       "
        "worstLoss    warn"
    )
    for rank, summary in enumerate(displayed, start=1):
        print(
            f"{rank:>4}  "
            f"{summary.mode:<12}  "
            f"{summary.polarity:<13}  "
            f"{summary.common_length:>6.1f}  "
            f"{_format_offset(summary.offset):>6}  "
            f"{summary.port1_length:>6.1f}  "
            f"{summary.port2_length:>6.1f}  "
            f"{summary.swr:>7.4f}  "
            f"{summary.score_or_objective:>9.3g}  "
            f"{format_optional_loss(summary.total_estimated_loss_watts):>7}  "
            f"{format_optional_efficiency(summary.estimated_efficiency_percent):>5}  "
            f"{_format_component_metric(summary.worst_rms_voltage_component, format_optional_voltage(summary.worst_rms_voltage)):>12}  "
            f"{_format_component_metric(summary.worst_rms_current_component, format_optional_current(summary.worst_rms_current)):>12}  "
            f"{_format_component_metric(summary.worst_component_loss_name, format_optional_loss(summary.worst_component_loss_watts)):>12}  "
            f"{summary.warning_count:>4}"
        )
        print(
            "      "
            f"Z1box={format_impedance(summary.port1_box_impedance_ohms)}, "
            f"Z2box={format_impedance(summary.port2_box_impedance_ohms)}, "
            f"V2/V1={summary.achieved_ratio_magnitude:.4f} "
            f"angle {summary.achieved_ratio_phase_deg:.2f} deg, "
            f"Zin={format_impedance(summary.zin_ohms)}"
        )
        if summary.warnings:
            print(f"      warnings: {', '.join(summary.warnings)}")
        else:
            print("      warnings: none")
    if not args.show_all and len(summaries) > len(displayed):
        print(f"      showing top {len(displayed)} of {len(summaries)}; use --show-all for all")
    print("")


def _port_impedance(case_data: dict, port_name: str) -> complex:
    parts = case_data["ports"][port_name]["z_ohms"]
    return complex(parts["r"], parts["x"])


def _format_offset(offset: float | None) -> str:
    if offset is None:
        return "n/a"
    return f"{offset:.1f}"


def _format_component_metric(component_name: str | None, value: str) -> str:
    if component_name is None:
        return "n/a"
    return f"{component_name}={value}"


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("limit must be greater than 0")
    return parsed


def _math_rank_by_mode(equal_summaries, offset_summaries) -> dict:
    ranked = {}
    for summaries in (equal_summaries, offset_summaries):
        for rank, summary in enumerate(summaries, start=1):
            ranked[summary] = rank
    return ranked


def _selected_polarities(include_variants: bool) -> tuple[str, ...]:
    if include_variants:
        return ("normal", "invert_port1", "invert_port2")
    return ("normal",)


if __name__ == "__main__":
    main()
