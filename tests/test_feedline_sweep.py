import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from pns.feedline import (
    LosslessCoaxLine,
    feet_to_meters,
    transform_two_feedpoints_to_box_end,
)
from pns.feedline_sweep import (
    equal_length_grid,
    format_component_value,
    generate_equal_length_feedline_candidates,
    generate_offset_feedline_candidates,
    offset_grid,
    optimize_equal_length_feedline_sweep,
    optimize_offset_feedline_sweep,
    practical_warnings,
)


FREQUENCY_HZ = 7_020_000
Z1_FEEDPOINT = 25.6111 - 34.7429j
Z2_FEEDPOINT = 47.5898 + 36.0728j
Z0 = 50.0
VELOCITY_FACTOR = 0.66


def test_equal_length_grid_includes_start():
    assert equal_length_grid(60.0, 70.0, 5.0)[0] == pytest.approx(60.0)


def test_equal_length_grid_includes_stop_when_step_lands_exactly():
    assert equal_length_grid(60.0, 70.0, 5.0) == pytest.approx(
        (60.0, 65.0, 70.0)
    )


def test_equal_length_grid_start_equal_stop_returns_one_value():
    assert equal_length_grid(70.0, 70.0, 5.0) == pytest.approx((70.0,))


@pytest.mark.parametrize(
    ("start", "stop", "step", "message"),
    (
        (-1.0, 10.0, 1.0, "start"),
        (0.0, -1.0, 1.0, "stop"),
        (0.0, 10.0, 0.0, "step"),
        (10.0, 0.0, 1.0, "stop"),
    ),
)
def test_equal_length_grid_invalid_ranges_raise_clear_errors(
    start,
    stop,
    step,
    message,
):
    with pytest.raises(ValueError, match=message):
        equal_length_grid(start, stop, step)


def test_offset_grid_includes_negative_zero_and_positive_offsets():
    assert offset_grid(-5.0, 5.0, 5.0) == pytest.approx((-5.0, 0.0, 5.0))


@pytest.mark.parametrize(
    ("start", "stop", "step", "message"),
    (
        (0.0, 10.0, 0.0, "step"),
        (10.0, 0.0, 1.0, "stop"),
    ),
)
def test_offset_grid_invalid_ranges_raise_clear_errors(
    start,
    stop,
    step,
    message,
):
    with pytest.raises(ValueError, match=message):
        offset_grid(start, stop, step)


def test_equal_length_candidate_generation_count_matches_grid():
    candidates = generate_equal_length_feedline_candidates(
        z1_feedpoint_ohms=Z1_FEEDPOINT,
        z2_feedpoint_ohms=Z2_FEEDPOINT,
        frequency_hz=FREQUENCY_HZ,
        characteristic_impedance_ohms=Z0,
        velocity_factor=VELOCITY_FACTOR,
        start_length=60.0,
        stop_length=70.0,
        step=5.0,
        length_unit="ft",
    )

    assert len(candidates) == 3
    assert [candidate.common_length for candidate in candidates] == pytest.approx(
        [60.0, 65.0, 70.0]
    )


def test_offset_candidate_generation_count_matches_small_grid():
    candidates = generate_offset_feedline_candidates(
        z1_feedpoint_ohms=Z1_FEEDPOINT,
        z2_feedpoint_ohms=Z2_FEEDPOINT,
        frequency_hz=FREQUENCY_HZ,
        characteristic_impedance_ohms=Z0,
        velocity_factor=VELOCITY_FACTOR,
        start_common_length=70.0,
        stop_common_length=75.0,
        common_step=5.0,
        start_offset=-5.0,
        stop_offset=5.0,
        offset_step=5.0,
        length_unit="ft",
    )

    assert len(candidates) == 6


def test_offset_candidate_generation_skips_negative_physical_lengths():
    candidates = generate_offset_feedline_candidates(
        z1_feedpoint_ohms=Z1_FEEDPOINT,
        z2_feedpoint_ohms=Z2_FEEDPOINT,
        frequency_hz=FREQUENCY_HZ,
        characteristic_impedance_ohms=Z0,
        velocity_factor=VELOCITY_FACTOR,
        start_common_length=10.0,
        stop_common_length=10.0,
        common_step=5.0,
        start_offset=-15.0,
        stop_offset=5.0,
        offset_step=10.0,
        length_unit="ft",
    )

    assert len(candidates) == 2
    assert [candidate.offset for candidate in candidates] == pytest.approx([-5.0, 5.0])
    assert all(candidate.port2_length >= 0 for candidate in candidates)


def test_equal_length_candidate_impedances_match_direct_transform():
    candidate = generate_equal_length_feedline_candidates(
        z1_feedpoint_ohms=Z1_FEEDPOINT,
        z2_feedpoint_ohms=Z2_FEEDPOINT,
        frequency_hz=FREQUENCY_HZ,
        characteristic_impedance_ohms=Z0,
        velocity_factor=VELOCITY_FACTOR,
        start_length=70.0,
        stop_length=70.0,
        step=5.0,
        length_unit="ft",
    )[0]
    feedline = LosslessCoaxLine(
        characteristic_impedance_ohms=Z0,
        velocity_factor=VELOCITY_FACTOR,
        length_m=feet_to_meters(70.0),
    )
    expected_z1, expected_z2 = transform_two_feedpoints_to_box_end(
        Z1_FEEDPOINT,
        Z2_FEEDPOINT,
        FREQUENCY_HZ,
        feedline,
        feedline,
    )

    assert candidate.port1_box_impedance_ohms == pytest.approx(expected_z1)
    assert candidate.port2_box_impedance_ohms == pytest.approx(expected_z2)
    assert candidate.port1_electrical_length_deg == pytest.approx(
        candidate.port2_electrical_length_deg
    )


def test_offset_candidate_impedances_match_direct_independent_transform():
    candidate = generate_offset_feedline_candidates(
        z1_feedpoint_ohms=Z1_FEEDPOINT,
        z2_feedpoint_ohms=Z2_FEEDPOINT,
        frequency_hz=FREQUENCY_HZ,
        characteristic_impedance_ohms=Z0,
        velocity_factor=VELOCITY_FACTOR,
        start_common_length=70.0,
        stop_common_length=70.0,
        common_step=5.0,
        start_offset=10.0,
        stop_offset=10.0,
        offset_step=5.0,
        length_unit="ft",
    )[0]
    feedline1 = LosslessCoaxLine(
        characteristic_impedance_ohms=Z0,
        velocity_factor=VELOCITY_FACTOR,
        length_m=feet_to_meters(70.0),
    )
    feedline2 = LosslessCoaxLine(
        characteristic_impedance_ohms=Z0,
        velocity_factor=VELOCITY_FACTOR,
        length_m=feet_to_meters(80.0),
    )
    expected_z1, expected_z2 = transform_two_feedpoints_to_box_end(
        Z1_FEEDPOINT,
        Z2_FEEDPOINT,
        FREQUENCY_HZ,
        feedline1,
        feedline2,
    )

    assert candidate.port1_length == pytest.approx(70.0)
    assert candidate.port2_length == pytest.approx(80.0)
    assert candidate.port1_box_impedance_ohms == pytest.approx(expected_z1)
    assert candidate.port2_box_impedance_ohms == pytest.approx(expected_z2)


def test_one_candidate_optimization_sweep_runs_and_returns_one_ranked_result():
    results = optimize_equal_length_feedline_sweep(
        z1_feedpoint_ohms=Z1_FEEDPOINT,
        z2_feedpoint_ohms=Z2_FEEDPOINT,
        frequency_hz=FREQUENCY_HZ,
        target_voltage_ratio_magnitude=1.34942,
        target_voltage_ratio_phase_deg=-30.744,
        target_input_impedance_ohms=50 + 0j,
        characteristic_impedance_ohms=Z0,
        velocity_factor=VELOCITY_FACTOR,
        start_length=70.0,
        stop_length=70.0,
        step=5.0,
        length_unit="ft",
        maxiter=2,
    )

    assert len(results) == 1
    assert results[0].candidate.common_length == pytest.approx(70.0)
    assert results[0].optimization_result.components.l1_h > 0
    assert results[0].achieved_ratio_magnitude > 0
    assert results[0].swr >= 1.0
    assert results[0].score_or_objective >= 0


def test_one_candidate_offset_optimization_sweep_runs_and_returns_one_result():
    results = optimize_offset_feedline_sweep(
        z1_feedpoint_ohms=Z1_FEEDPOINT,
        z2_feedpoint_ohms=Z2_FEEDPOINT,
        frequency_hz=FREQUENCY_HZ,
        target_voltage_ratio_magnitude=1.34942,
        target_voltage_ratio_phase_deg=-30.744,
        target_input_impedance_ohms=50 + 0j,
        characteristic_impedance_ohms=Z0,
        velocity_factor=VELOCITY_FACTOR,
        start_common_length=70.0,
        stop_common_length=70.0,
        common_step=5.0,
        start_offset=0.0,
        stop_offset=0.0,
        offset_step=5.0,
        length_unit="ft",
        maxiter=2,
    )

    assert len(results) == 1
    assert results[0].candidate.common_length == pytest.approx(70.0)
    assert results[0].candidate.offset == pytest.approx(0.0)
    assert results[0].optimization_result.components.l1_h > 0
    assert results[0].achieved_ratio_magnitude > 0
    assert results[0].swr >= 1.0
    assert results[0].score_or_objective >= 0


def test_component_value_formatting_uses_human_readable_units():
    assert format_component_value("L", 2.5e-6) == "2.5 uH"
    assert format_component_value("C", 470e-12) == "470 pF"


def test_practical_warnings_include_very_small_capacitor():
    result = _sweep_result_for_warnings(c1_f=5e-12)

    assert "C1 < 10 pF" in practical_warnings(result)


def test_practical_warnings_include_very_large_inductor():
    result = _sweep_result_for_warnings(l1_h=12e-6)

    assert "L1 > 10 uH" in practical_warnings(result)


def test_sweep_example_limit_parser_accepts_positive_limit():
    module = _load_sweep_example_module()

    args = module._parse_args(["--limit", "3"])

    assert args.limit == 3
    assert args.show_all is False


def test_sweep_example_limit_parser_rejects_nonpositive_limit():
    module = _load_sweep_example_module()

    with pytest.raises(SystemExit):
        module._parse_args(["--limit", "0"])


def test_offset_sweep_example_limit_parser_accepts_positive_limit():
    module = _load_offset_sweep_example_module()

    args = module._parse_args(["--limit", "3"])

    assert args.limit == 3
    assert args.show_all is False


def test_offset_sweep_example_limit_parser_rejects_nonpositive_limit():
    module = _load_offset_sweep_example_module()

    with pytest.raises(SystemExit):
        module._parse_args(["--limit", "0"])


def _sweep_result_for_warnings(
    l1_h: float = 1e-6,
    c1_f: float = 100e-12,
    c2_f: float = 100e-12,
    l2_h: float = 1e-6,
):
    return SimpleNamespace(
        optimization_result=SimpleNamespace(
            components=SimpleNamespace(
                l1_h=l1_h,
                c1_f=c1_f,
                c2_f=c2_f,
                l2_h=l2_h,
            ),
            input_match_solution=SimpleNamespace(
                series_component_type="L",
                series_value_si=1e-6,
                shunt_component_type="C",
                shunt_value_si=100e-12,
            ),
        ),
        stress_report=None,
    )


def _load_sweep_example_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "sweep_40m_equal_feedline_lengths.py"
    )
    spec = importlib.util.spec_from_file_location("sweep_40m_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_offset_sweep_example_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "sweep_40m_offset_feedline_lengths.py"
    )
    spec = importlib.util.spec_from_file_location("offset_sweep_40m_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
