from pathlib import Path
from types import SimpleNamespace

import pytest

from pns.cases import load_case
from pns.objectives import (
    ObjectiveWeights,
    case_target_ratio,
    load_case_targets,
    score_topology_a_result,
)
from pns.rfmath import complex_to_mag_phase, polar_to_complex


CASE_PATH = Path(__file__).resolve().parents[1] / "cases" / "40m_inverted_v_90ft_feedlines.json"


def _result(v_ratio, z_input=50 + 0j, swr=1.0):
    return SimpleNamespace(
        v_ratio_v2_over_v1=v_ratio,
        z_input=z_input,
        swr=swr,
    )


def test_exact_target_ratio_and_input_impedance_gives_near_zero_score():
    target_ratio = polar_to_complex(0.356, 86.6)
    result = _result(target_ratio, 50 + 0j, swr=1.0)

    score = score_topology_a_result(result, target_ratio, 50 + 0j)

    assert score.magnitude_error_db == pytest.approx(0.0)
    assert score.phase_error_deg == pytest.approx(0.0)
    assert score.input_r_error_ohms == pytest.approx(0.0)
    assert score.input_x_error_ohms == pytest.approx(0.0)
    assert score.swr == pytest.approx(1.0)
    assert score.total_score == pytest.approx(0.0)


def test_phase_wrap_uses_actual_minus_target_convention():
    target_ratio = polar_to_complex(1.0, -179.0)
    result = _result(polar_to_complex(1.0, 179.0))

    score = score_topology_a_result(result, target_ratio)

    assert score.phase_error_deg == pytest.approx(-2.0)
    assert score.total_score == pytest.approx(4.0)


def test_wrong_phase_increases_score():
    target_ratio = polar_to_complex(1.0, 0.0)
    exact_score = score_topology_a_result(_result(target_ratio), target_ratio)
    wrong_score = score_topology_a_result(
        _result(polar_to_complex(1.0, 10.0)),
        target_ratio,
    )

    assert wrong_score.total_score > exact_score.total_score
    assert wrong_score.phase_error_deg == pytest.approx(10.0)


def test_wrong_magnitude_increases_score():
    target_ratio = polar_to_complex(1.0, 0.0)
    exact_score = score_topology_a_result(_result(target_ratio), target_ratio)
    wrong_score = score_topology_a_result(
        _result(polar_to_complex(2.0, 0.0)),
        target_ratio,
    )

    assert wrong_score.total_score > exact_score.total_score
    assert wrong_score.magnitude_error_db == pytest.approx(6.0206, abs=1e-4)


def test_wrong_input_impedance_increases_score():
    target_ratio = polar_to_complex(1.0, 0.0)
    exact_score = score_topology_a_result(_result(target_ratio, 50 + 0j), target_ratio)
    wrong_score = score_topology_a_result(
        _result(target_ratio, 55 - 3j),
        target_ratio,
    )

    assert wrong_score.total_score > exact_score.total_score
    assert wrong_score.input_r_error_ohms == pytest.approx(5.0)
    assert wrong_score.input_x_error_ohms == pytest.approx(-3.0)


def test_custom_weights_change_total_score():
    target_ratio = polar_to_complex(1.0, 0.0)
    result = _result(polar_to_complex(1.0, 10.0), 55 + 0j)

    default_score = score_topology_a_result(result, target_ratio)
    weighted_score = score_topology_a_result(
        result,
        target_ratio,
        weights=ObjectiveWeights(phase_error_deg=2.0, input_r_error_ohms=0.5),
    )

    assert weighted_score.total_score != pytest.approx(default_score.total_score)
    assert weighted_score.total_score == pytest.approx(2.0 * 10.0**2 + 0.5 * 5.0**2)


def test_shipped_40m_case_target_ratio_converts_to_expected_polar_value():
    targets = load_case_targets(CASE_PATH)
    target_ratio = case_target_ratio(load_case(CASE_PATH))
    magnitude, phase_deg = complex_to_mag_phase(target_ratio)

    assert magnitude == pytest.approx(0.356)
    assert phase_deg == pytest.approx(86.6)
    assert targets.target_ratio == pytest.approx(target_ratio)
    assert targets.target_input_impedance == pytest.approx(50 + 0j)
