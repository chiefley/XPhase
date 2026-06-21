import math
from pathlib import Path

import pytest

from pns.cases import case_to_complex_values, load_case
from pns.optimize import optimize_topology_b_from_case
from pns.stress import estimate_topology_b_stress, estimate_topology_b_stress_from_case


CASE_PATH = Path(__file__).resolve().parents[1] / "cases" / "40m_inverted_v_90ft_feedlines.json"


@pytest.fixture(scope="module")
def case_data():
    return load_case(CASE_PATH)


@pytest.fixture(scope="module")
def topology_b_result(case_data):
    return optimize_topology_b_from_case(case_data, maxiter=5).result


def test_stress_report_scales_with_requested_power(case_data, topology_b_result):
    values = case_to_complex_values(case_data)
    report_50w = estimate_topology_b_stress(
        topology_b_result,
        values["frequency_hz"],
        values["z1_ohms"],
        values["z2_ohms"],
        input_power_watts=50.0,
    )
    report_100w = estimate_topology_b_stress(
        topology_b_result,
        values["frequency_hz"],
        values["z1_ohms"],
        values["z2_ohms"],
        input_power_watts=100.0,
    )

    assert report_100w.branch1_complex_power_watts.real == pytest.approx(
        2.0 * report_50w.branch1_complex_power_watts.real
    )
    assert report_100w.total_estimated_loss_watts == pytest.approx(
        2.0 * report_50w.total_estimated_loss_watts
    )
    assert report_100w.scale_factor == pytest.approx(
        math.sqrt(2.0) * report_50w.scale_factor
    )


def test_stress_rejects_nonpositive_power_and_q(case_data, topology_b_result):
    values = case_to_complex_values(case_data)

    with pytest.raises(ValueError, match="input_power_watts"):
        estimate_topology_b_stress(
            topology_b_result,
            values["frequency_hz"],
            values["z1_ohms"],
            values["z2_ohms"],
            input_power_watts=0,
        )

    with pytest.raises(ValueError, match="inductor_q"):
        estimate_topology_b_stress(
            topology_b_result,
            values["frequency_hz"],
            values["z1_ohms"],
            values["z2_ohms"],
            input_power_watts=100,
            inductor_q=0,
        )

    with pytest.raises(ValueError, match="capacitor_q"):
        estimate_topology_b_stress(
            topology_b_result,
            values["frequency_hz"],
            values["z1_ohms"],
            values["z2_ohms"],
            input_power_watts=100,
            capacitor_q=-1,
        )


def test_loss_decreases_when_q_increases(case_data, topology_b_result):
    values = case_to_complex_values(case_data)
    low_q_report = estimate_topology_b_stress(
        topology_b_result,
        values["frequency_hz"],
        values["z1_ohms"],
        values["z2_ohms"],
        input_power_watts=100,
        inductor_q=100,
        capacitor_q=200,
    )
    high_q_report = estimate_topology_b_stress(
        topology_b_result,
        values["frequency_hz"],
        values["z1_ohms"],
        values["z2_ohms"],
        input_power_watts=100,
        inductor_q=1000,
        capacitor_q=2000,
    )

    assert high_q_report.total_estimated_loss_watts < low_q_report.total_estimated_loss_watts


def test_optimized_40m_topology_b_result_has_finite_stress_and_loss(
    case_data,
    topology_b_result,
):
    report = estimate_topology_b_stress_from_case(topology_b_result, case_data)

    assert report.input_power_watts == pytest.approx(100.0)
    assert report.delivered_load_power_watts > 0
    assert math.isfinite(report.total_estimated_loss_watts)
    assert report.total_estimated_loss_watts >= 0
    assert 0 < report.estimated_efficiency_percent <= 100
    assert report.component_stresses
    for component in report.component_stresses:
        assert math.isfinite(component.rms_voltage)
        assert math.isfinite(component.rms_current)
        assert math.isfinite(component.loss_watts)
