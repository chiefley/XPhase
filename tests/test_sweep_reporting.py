import csv
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from pns.sweep_reporting import (
    CSV_FIELDNAMES,
    SweepCandidateSummary,
    practical_sort_key,
    summary_to_csv_row,
    summarize_equal_length_result,
    summarize_offset_result,
    summarize_sweep_result,
    write_summaries_csv,
)


def test_summary_extraction_works_for_equal_length_result_like_object():
    result = _result(mode="equal_length", stress_report=_stress_report())

    summary = summarize_equal_length_result(result)

    assert summary.mode == "equal_length"
    assert summary.offset is None
    assert summary.port1_length == pytest.approx(70.0)
    assert summary.port2_length == pytest.approx(70.0)
    assert summary.total_estimated_loss_watts == pytest.approx(3.0)
    assert summary.estimated_efficiency_percent == pytest.approx(97.0)
    assert summary.worst_rms_voltage == pytest.approx(300.0)
    assert summary.worst_rms_voltage_component == "C1"
    assert summary.worst_rms_current == pytest.approx(6.0)
    assert summary.worst_rms_current_component == "L1"
    assert summary.worst_component_loss_watts == pytest.approx(2.0)
    assert summary.worst_component_loss_name == "L1"


def test_summary_extraction_works_for_offset_result_like_object():
    result = _result(mode="offset", stress_report=_stress_report())

    summary = summarize_offset_result(result)

    assert summary.mode == "offset"
    assert summary.common_length == pytest.approx(75.0)
    assert summary.offset == pytest.approx(10.0)
    assert summary.port1_length == pytest.approx(75.0)
    assert summary.port2_length == pytest.approx(85.0)


def test_summary_dispatches_based_on_candidate_attributes():
    equal_summary = summarize_sweep_result(_result(mode="equal_length"))
    offset_summary = summarize_sweep_result(_result(mode="offset"))

    assert equal_summary.mode == "equal_length"
    assert offset_summary.mode == "offset"


def test_summary_handles_missing_stress_report():
    summary = summarize_equal_length_result(_result(mode="equal_length", stress_report=None))

    assert summary.total_estimated_loss_watts is None
    assert summary.estimated_efficiency_percent is None
    assert summary.worst_rms_voltage is None
    assert summary.worst_rms_current is None
    assert summary.worst_component_loss_watts is None


def test_practical_sort_key_prefers_fewer_warnings_then_lower_loss_and_stress():
    fewer_warnings = _summary(
        warning_count=0,
        total_estimated_loss_watts=10.0,
        worst_rms_current=10.0,
        worst_rms_voltage=1000.0,
    )
    more_warnings = _summary(
        warning_count=1,
        total_estimated_loss_watts=1.0,
        worst_rms_current=1.0,
        worst_rms_voltage=100.0,
    )
    lower_loss = _summary(
        warning_count=0,
        total_estimated_loss_watts=5.0,
        worst_rms_current=10.0,
        worst_rms_voltage=1000.0,
    )
    lower_current = _summary(
        warning_count=0,
        total_estimated_loss_watts=5.0,
        worst_rms_current=5.0,
        worst_rms_voltage=1000.0,
    )

    assert practical_sort_key(fewer_warnings) < practical_sort_key(more_warnings)
    assert practical_sort_key(lower_loss) < practical_sort_key(fewer_warnings)
    assert practical_sort_key(lower_current) < practical_sort_key(lower_loss)


def test_comparison_example_limit_parser_accepts_positive_limit():
    module = _load_compare_example_module()

    args = module._parse_args(["--limit", "3"])

    assert args.limit == 3
    assert args.show_all is False


def test_comparison_example_limit_parser_rejects_nonpositive_limit():
    module = _load_compare_example_module()

    with pytest.raises(SystemExit):
        module._parse_args(["--limit", "0"])


def test_summary_to_csv_row_serializes_representative_summary():
    summary = _candidate_summary()

    row = summary_to_csv_row(
        summary,
        rank_math_within_mode=2,
        rank_practical_combined=7,
    )

    assert row["rank_math_within_mode"] == 2
    assert row["rank_practical_combined"] == 7
    assert row["mode"] == "offset"
    assert row["offset"] == 10.0
    assert row["port1_box_r_ohms"] == pytest.approx(50.0)
    assert row["port2_box_x_ohms"] == pytest.approx(-2.0)
    assert row["warnings"] == "C2 high current; L1 high loss"


def test_summary_to_csv_row_serializes_missing_optional_values_as_empty_strings():
    summary = _candidate_summary(
        offset=None,
        total_estimated_loss_watts=None,
        estimated_efficiency_percent=None,
        worst_rms_voltage=None,
        worst_rms_voltage_component=None,
        worst_rms_current=None,
        worst_rms_current_component=None,
        worst_component_loss_watts=None,
        worst_component_loss_name=None,
    )

    row = summary_to_csv_row(summary)

    assert row["offset"] == ""
    assert row["total_estimated_loss_watts"] == ""
    assert row["estimated_efficiency_percent"] == ""
    assert row["worst_rms_voltage"] == ""
    assert row["worst_rms_voltage_component"] == ""
    assert row["worst_rms_current"] == ""
    assert row["worst_rms_current_component"] == ""
    assert row["worst_component_loss_watts"] == ""
    assert row["worst_component_loss_name"] == ""


def test_write_summaries_csv_creates_file_with_header_and_row(tmp_path):
    summary = _candidate_summary()
    output_path = tmp_path / "reports" / "comparison.csv"

    written_path = write_summaries_csv(
        output_path,
        (summary,),
        practical_ordered_summaries=(summary,),
        math_rank_by_mode={summary: 1},
    )

    assert written_path == output_path
    with output_path.open(newline="") as input_file:
        reader = csv.DictReader(input_file)
        rows = list(reader)

    assert reader.fieldnames == list(CSV_FIELDNAMES)
    assert len(rows) == 1
    assert rows[0]["rank_math_within_mode"] == "1"
    assert rows[0]["rank_practical_combined"] == "1"
    assert rows[0]["mode"] == "offset"
    assert rows[0]["warnings"] == "C2 high current; L1 high loss"


def test_comparison_example_parser_accepts_write_csv_and_custom_csv_path():
    module = _load_compare_example_module()

    args = module._parse_args(
        ["--limit", "3", "--write-csv", "--csv-path", "reports/custom.csv"]
    )

    assert args.limit == 3
    assert args.write_csv is True
    assert args.csv_path == Path("reports/custom.csv")


def _result(mode: str, stress_report=None):
    candidate = (
        SimpleNamespace(
            common_length=70.0,
            length_unit="ft",
            port1_box_impedance_ohms=50 + 1j,
            port2_box_impedance_ohms=60 - 2j,
        )
        if mode == "equal_length"
        else SimpleNamespace(
            common_length=75.0,
            offset=10.0,
            length_unit="ft",
            port1_length=75.0,
            port2_length=85.0,
            port1_box_impedance_ohms=50 + 1j,
            port2_box_impedance_ohms=60 - 2j,
        )
    )
    return SimpleNamespace(
        candidate=candidate,
        optimization_result=SimpleNamespace(
            components=SimpleNamespace(
                l1_h=1e-6,
                c1_f=100e-12,
                c2_f=100e-12,
                l2_h=1e-6,
            ),
            input_match_solution=SimpleNamespace(
                series_component_type="L",
                series_value_si=1e-6,
                shunt_component_type="C",
                shunt_value_si=100e-12,
            ),
        ),
        achieved_ratio_magnitude=1.2,
        achieved_ratio_phase_deg=-30.0,
        zin_ohms=50 + 0j,
        swr=1.0,
        score_or_objective=0.1,
        stress_report=stress_report,
    )


def _stress_report():
    return SimpleNamespace(
        total_estimated_loss_watts=3.0,
        estimated_efficiency_percent=97.0,
        component_stresses=(
            SimpleNamespace(
                name="L1",
                rms_voltage=100.0,
                rms_current=6.0,
                loss_watts=2.0,
            ),
            SimpleNamespace(
                name="C1",
                rms_voltage=300.0,
                rms_current=1.0,
                loss_watts=0.5,
            ),
        ),
    )


def _summary(
    warning_count: int,
    total_estimated_loss_watts: float,
    worst_rms_current: float,
    worst_rms_voltage: float,
):
    return SimpleNamespace(
        score_or_objective=0.1,
        warning_count=warning_count,
        total_estimated_loss_watts=total_estimated_loss_watts,
        worst_rms_current=worst_rms_current,
        worst_rms_voltage=worst_rms_voltage,
        swr=1.0,
    )


def _candidate_summary(**overrides):
    values = {
        "mode": "offset",
        "common_length": 75.0,
        "offset": 10.0,
        "port1_length": 75.0,
        "port2_length": 85.0,
        "length_unit": "ft",
        "port1_box_impedance_ohms": 50 + 1j,
        "port2_box_impedance_ohms": 60 - 2j,
        "achieved_ratio_magnitude": 1.34942,
        "achieved_ratio_phase_deg": -30.744,
        "zin_ohms": 50 + 0.5j,
        "swr": 1.02,
        "score_or_objective": 0.01,
        "total_estimated_loss_watts": 8.5,
        "estimated_efficiency_percent": 92.0,
        "worst_rms_voltage": 250.0,
        "worst_rms_voltage_component": "C2",
        "worst_rms_current": 4.5,
        "worst_rms_current_component": "L1",
        "worst_component_loss_watts": 3.0,
        "worst_component_loss_name": "L1",
        "warning_count": 2,
        "warnings": ("C2 high current", "L1 high loss"),
    }
    values.update(overrides)
    return SweepCandidateSummary(**values)


def _load_compare_example_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "compare_40m_feedline_sweeps.py"
    )
    spec = importlib.util.spec_from_file_location("compare_40m_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
