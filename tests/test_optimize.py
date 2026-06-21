import math
from pathlib import Path

import pytest

from pns.cases import case_to_complex_values, load_case
from pns.objectives import case_targets, score_topology_a_result
from pns.optimize import DEFAULT_TOPOLOGY_A_BOUNDS, optimize_topology_a_from_case
from pns.topology_a import evaluate_topology_a


CASE_PATH = Path(__file__).resolve().parents[1] / "cases" / "40m_inverted_v_90ft_feedlines.json"


@pytest.fixture(scope="module")
def optimization_result():
    return optimize_topology_a_from_case(load_case(CASE_PATH), maxiter=5)


def test_optimizer_returns_positive_component_values_within_bounds(optimization_result):
    components = optimization_result.components

    for name, (lower, upper) in DEFAULT_TOPOLOGY_A_BOUNDS.items():
        value = getattr(components, name)
        assert lower <= value <= upper
        assert value > 0


def test_optimizer_best_result_has_finite_score(optimization_result):
    assert isinstance(optimization_result.success, bool)
    assert optimization_result.message
    assert math.isfinite(optimization_result.score.total_score)


def test_optimizer_ratio_is_closer_than_deliberately_poor_candidate(optimization_result):
    data = load_case(CASE_PATH)
    values = case_to_complex_values(data)
    targets = case_targets(data)
    poor_result = evaluate_topology_a(
        frequency_hz=values["frequency_hz"],
        z1=values["z1_ohms"],
        z2=values["z2_ohms"],
        l1_h=DEFAULT_TOPOLOGY_A_BOUNDS["l1_h"][0],
        c1_f=DEFAULT_TOPOLOGY_A_BOUNDS["c1_f"][0],
        c2_f=DEFAULT_TOPOLOGY_A_BOUNDS["c2_f"][0],
        l2_h=DEFAULT_TOPOLOGY_A_BOUNDS["l2_h"][0],
    )

    best_score = optimization_result.score
    poor_score = score_topology_a_result(
        poor_result,
        targets.target_ratio,
        targets.target_input_impedance,
    )
    best_ratio_error = best_score.magnitude_error_db**2 + best_score.phase_error_deg**2
    poor_ratio_error = poor_score.magnitude_error_db**2 + poor_score.phase_error_deg**2

    assert best_ratio_error < poor_ratio_error


def test_optimizer_input_impedance_is_finite_and_nonzero(optimization_result):
    z_input = optimization_result.result.z_input

    assert z_input != 0
    assert math.isfinite(z_input.real)
    assert math.isfinite(z_input.imag)
