import math
from pathlib import Path

import pytest

from pns.cases import load_case
from pns.optimize import DEFAULT_TOPOLOGY_A_BOUNDS, optimize_topology_b_from_case


CASE_PATH = Path(__file__).resolve().parents[1] / "cases" / "40m_inverted_v_90ft_feedlines.json"


@pytest.fixture(scope="module")
def topology_b_optimization_result():
    return optimize_topology_b_from_case(load_case(CASE_PATH), maxiter=5)


def test_topology_b_optimizer_returns_positive_branch_components_within_bounds(
    topology_b_optimization_result,
):
    components = topology_b_optimization_result.components

    for name, (lower, upper) in DEFAULT_TOPOLOGY_A_BOUNDS.items():
        value = getattr(components, name)
        assert lower <= value <= upper
        assert value > 0


def test_topology_b_optimizer_selects_input_match(topology_b_optimization_result):
    solution = topology_b_optimization_result.input_match_solution

    assert solution is not None
    assert solution.series_value_si > 0
    assert solution.shunt_value_si > 0
    assert solution.topology_name in {"B-LP", "B-HP"}


def test_topology_b_optimizer_final_swr_is_close_to_unity(topology_b_optimization_result):
    assert topology_b_optimization_result.swr == pytest.approx(1.0)
    assert topology_b_optimization_result.z_input.real == pytest.approx(50.0, abs=1e-8)
    assert topology_b_optimization_result.z_input.imag == pytest.approx(0.0, abs=1e-8)


def test_topology_b_optimizer_v_ratio_is_close_to_40m_target(
    topology_b_optimization_result,
):
    assert topology_b_optimization_result.v_ratio_magnitude == pytest.approx(
        0.356,
        abs=0.02,
    )
    assert topology_b_optimization_result.v_ratio_phase_deg == pytest.approx(
        86.6,
        abs=2.0,
    )
    assert math.isfinite(topology_b_optimization_result.score.total_score)
