import csv
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from pns.cases import load_case
from pns.feedline_sweep import optimize_equal_length_feedline_sweep
from pns.rfmath import phase_error_deg
from pns.static_bandwidth import (
    STATIC_BANDWIDTH_CSV_FIELDNAMES,
    evaluate_static_bandwidth_for_result,
    extract_candidate_feedline_lengths,
    frequency_grid_hz,
    static_bandwidth_point_to_csv_row,
    write_static_bandwidth_csv,
)


CASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "cases"
    / "40m_inverted_v_feedpoints_plus_y_7020khz.json"
)


@pytest.fixture(scope="module")
def case_data():
    return load_case(CASE_PATH)


@pytest.fixture(scope="module")
def solved_equal_result(case_data):
    target = case_data["target"]["voltage_ratio_v2_over_v1"]
    target_input = case_data["target"]["input_impedance_ohms"]
    return optimize_equal_length_feedline_sweep(
        z1_feedpoint_ohms=_port_impedance(case_data, "port1"),
        z2_feedpoint_ohms=_port_impedance(case_data, "port2"),
        frequency_hz=case_data["frequency_hz"],
        target_voltage_ratio_magnitude=target["magnitude"],
        target_voltage_ratio_phase_deg=target["phase_deg"],
        target_input_impedance_ohms=complex(target_input["r"], target_input["x"]),
        characteristic_impedance_ohms=50.0,
        velocity_factor=0.66,
        start_length=70.0,
        stop_length=70.0,
        step=5.0,
        length_unit="ft",
        maxiter=3,
    )[0]


def test_frequency_grid_includes_both_endpoints():
    assert frequency_grid_hz(7_000_000.0, 7_060_000.0, 20_000.0) == (
        7_000_000.0,
        7_020_000.0,
        7_040_000.0,
        7_060_000.0,
    )
    assert frequency_grid_hz(7_000_000.0, 7_055_000.0, 20_000.0)[-1] == pytest.approx(
        7_055_000.0
    )


def test_frequency_grid_handles_single_frequency():
    assert frequency_grid_hz(7_020_000.0, 7_020_000.0, 10_000.0) == (
        7_020_000.0,
    )


@pytest.mark.parametrize(
    "start_hz, stop_hz, step_hz",
    (
        (0.0, 7_060_000.0, 10_000.0),
        (7_000_000.0, 0.0, 10_000.0),
        (7_000_000.0, 7_060_000.0, 0.0),
        (7_060_000.0, 7_000_000.0, 10_000.0),
    ),
)
def test_frequency_grid_rejects_invalid_inputs(start_hz, stop_hz, step_hz):
    with pytest.raises(ValueError):
        frequency_grid_hz(start_hz, stop_hz, step_hz)


def test_extracts_equal_length_candidate_lengths(solved_equal_result):
    lengths = extract_candidate_feedline_lengths(solved_equal_result)

    assert lengths.mode == "equal_length"
    assert lengths.offset is None
    assert lengths.port1_length == pytest.approx(70.0)
    assert lengths.port2_length == pytest.approx(70.0)
    assert lengths.length_unit == "ft"


def test_extracts_offset_candidate_lengths():
    result = SimpleNamespace(
        candidate=SimpleNamespace(
            common_length=75.0,
            offset=10.0,
            port1_length=75.0,
            port2_length=85.0,
            length_unit="ft",
        )
    )

    lengths = extract_candidate_feedline_lengths(result)

    assert lengths.mode == "offset"
    assert lengths.common_length == pytest.approx(75.0)
    assert lengths.offset == pytest.approx(10.0)
    assert lengths.port1_length == pytest.approx(75.0)
    assert lengths.port2_length == pytest.approx(85.0)


def test_center_frequency_matches_original_solved_candidate(
    case_data,
    solved_equal_result,
):
    center_hz = case_data["frequency_hz"]
    summary = _evaluate(
        solved_equal_result,
        case_data,
        frequencies_hz=(center_hz,),
    )
    point = summary.points[0]

    assert point.achieved_ratio_magnitude == pytest.approx(
        solved_equal_result.achieved_ratio_magnitude,
        rel=1e-10,
    )
    assert phase_error_deg(
        point.achieved_ratio_phase_deg,
        solved_equal_result.achieved_ratio_phase_deg,
    ) == pytest.approx(0.0, abs=1e-10)
    assert point.zin_ohms == pytest.approx(solved_equal_result.zin_ohms, rel=1e-10)
    assert point.swr == pytest.approx(solved_equal_result.swr, rel=1e-10)


def test_off_center_evaluation_returns_one_point_per_frequency(
    case_data,
    solved_equal_result,
):
    frequencies = (7_000_000.0, 7_020_000.0, 7_040_000.0)

    summary = _evaluate(
        solved_equal_result,
        case_data,
        frequencies_hz=frequencies,
    )

    assert tuple(point.frequency_hz for point in summary.points) == frequencies


def test_static_evaluator_does_not_call_optimizer(
    monkeypatch,
    case_data,
    solved_equal_result,
):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("optimize_topology_b must not be called")

    monkeypatch.setattr("pns.optimize.optimize_topology_b", fail_if_called)

    _evaluate(
        solved_equal_result,
        case_data,
        frequencies_hz=(case_data["frequency_hz"],),
    )


def test_summary_extrema_match_point_values(case_data, solved_equal_result):
    summary = _evaluate(
        solved_equal_result,
        case_data,
        frequencies_hz=(7_000_000.0, 7_020_000.0, 7_040_000.0),
        include_stress=True,
    )

    assert summary.max_swr == max(point.swr for point in summary.points)
    assert summary.max_magnitude_error == max(
        abs(point.magnitude_error) for point in summary.points
    )
    assert summary.max_abs_phase_error_deg == max(
        abs(point.phase_error_deg) for point in summary.points
    )
    assert summary.max_total_estimated_loss_watts == max(
        point.total_estimated_loss_watts for point in summary.points
    )
    assert summary.min_estimated_efficiency_percent == min(
        point.estimated_efficiency_percent for point in summary.points
    )
    l1_maximum = next(
        component for component in summary.max_component_stresses if component.name == "L1"
    )
    assert l1_maximum.rms_voltage == max(
        next(
            component.rms_voltage
            for component in point.component_stresses
            if component.name == "L1"
        )
        for point in summary.points
    )


def test_csv_row_contains_point_rf_and_component_stress_fields(
    case_data,
    solved_equal_result,
):
    summary = _evaluate(
        solved_equal_result,
        case_data,
        frequencies_hz=(case_data["frequency_hz"],),
        include_stress=True,
    )

    row = static_bandwidth_point_to_csv_row(
        summary,
        summary.points[0],
        candidate_index=1,
    )

    assert row["frequency_hz"] == pytest.approx(case_data["frequency_hz"])
    assert row["achieved_v2_over_v1_magnitude"] > 0
    assert row["zin_r_ohms"] == pytest.approx(summary.points[0].zin_ohms.real)
    assert row["L1_rms_voltage"] > 0
    assert row["input_shunt_loss_watts"] >= 0


def test_csv_row_uses_empty_component_fields_without_stress(
    case_data,
    solved_equal_result,
):
    summary = _evaluate(
        solved_equal_result,
        case_data,
        frequencies_hz=(case_data["frequency_hz"],),
    )

    row = static_bandwidth_point_to_csv_row(
        summary,
        summary.points[0],
        candidate_index=1,
    )

    assert row["total_estimated_loss_watts"] == ""
    assert row["L1_rms_voltage"] == ""
    assert row["input_shunt_loss_watts"] == ""


def test_write_static_bandwidth_csv_creates_point_rows(
    tmp_path,
    case_data,
    solved_equal_result,
):
    summary = _evaluate(
        solved_equal_result,
        case_data,
        frequencies_hz=(7_010_000.0, 7_020_000.0),
    )
    path = tmp_path / "reports" / "bandwidth.csv"

    written = write_static_bandwidth_csv(path, (summary,))

    assert written == path
    with path.open(newline="") as input_file:
        reader = csv.DictReader(input_file)
        rows = list(reader)
    assert reader.fieldnames == list(STATIC_BANDWIDTH_CSV_FIELDNAMES)
    assert len(rows) == 2
    assert rows[0]["candidate_index"] == "1"


def test_example_parser_accepts_band_and_csv_options():
    module = _load_example_module()

    args = module._parse_args(
        [
            "--start-mhz",
            "7.01",
            "--stop-mhz",
            "7.05",
            "--step-khz",
            "5",
            "--limit",
            "2",
            "--write-csv",
            "--csv-path",
            "reports/custom_bandwidth.csv",
        ]
    )

    assert args.start_mhz == pytest.approx(7.01)
    assert args.stop_mhz == pytest.approx(7.05)
    assert args.step_khz == pytest.approx(5.0)
    assert args.limit == 2
    assert args.write_csv is True
    assert args.csv_path == Path("reports/custom_bandwidth.csv")


def _evaluate(result, case_data, *, frequencies_hz, include_stress=False):
    target = case_data["target"]["voltage_ratio_v2_over_v1"]
    target_input = case_data["target"]["input_impedance_ohms"]
    assumptions = case_data["component_assumptions"]
    return evaluate_static_bandwidth_for_result(
        result,
        z1_feedpoint_ohms=_port_impedance(case_data, "port1"),
        z2_feedpoint_ohms=_port_impedance(case_data, "port2"),
        center_frequency_hz=case_data["frequency_hz"],
        frequencies_hz=frequencies_hz,
        target_voltage_ratio_magnitude=target["magnitude"],
        target_voltage_ratio_phase_deg=target["phase_deg"],
        target_input_impedance_ohms=complex(target_input["r"], target_input["x"]),
        characteristic_impedance_ohms=50.0,
        velocity_factor=0.66,
        input_power_watts=case_data["power_watts"] if include_stress else None,
        inductor_q=assumptions["inductor_q"],
        capacitor_q=assumptions["capacitor_q"],
    )


def _port_impedance(case_data, port_name):
    value = case_data["ports"][port_name]["z_ohms"]
    return complex(value["r"], value["x"])


def _load_example_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "evaluate_40m_static_bandwidth.py"
    )
    spec = importlib.util.spec_from_file_location("static_bandwidth_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
