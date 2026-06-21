import pytest

from pns.lmatch import find_l_matches
from pns.topology_a import evaluate_topology_a
from pns.topology_b import TopologyBResult, evaluate_topology_b_from_components


FREQUENCY_HZ = 7_015_000
Z1 = 74.3166 - 37.5440j
Z2 = 17.7330 + 4.6350j
L1_H = 20e-9
C1_F = 5e-12
C2_F = 445.21e-12
L2_H = 10e-6


def test_phasing_priority_split_impedance_can_be_matched_to_50_ohms():
    result = evaluate_topology_b_from_components(
        FREQUENCY_HZ,
        Z1,
        Z2,
        L1_H,
        C1_F,
        C2_F,
        L2_H,
    )

    assert isinstance(result, TopologyBResult)
    assert result.z_split.real == pytest.approx(19.30, abs=0.02)
    assert result.z_split.imag == pytest.approx(-26.35, abs=0.02)
    assert result.z_input.real == pytest.approx(50.0, abs=1e-9)
    assert result.z_input.imag == pytest.approx(0.0, abs=1e-9)


def test_topology_b_preserves_underlying_topology_a_voltage_ratio():
    topology_a_result = evaluate_topology_a(
        FREQUENCY_HZ,
        Z1,
        Z2,
        L1_H,
        C1_F,
        C2_F,
        L2_H,
    )
    topology_b_result = evaluate_topology_b_from_components(
        FREQUENCY_HZ,
        Z1,
        Z2,
        L1_H,
        C1_F,
        C2_F,
        L2_H,
    )

    assert topology_b_result.topology_a_result == topology_a_result
    assert topology_b_result.v_port1 == pytest.approx(topology_a_result.v_port1)
    assert topology_b_result.v_port2 == pytest.approx(topology_a_result.v_port2)
    assert topology_b_result.v_ratio_v2_over_v1 == pytest.approx(
        topology_a_result.v_ratio_v2_over_v1
    )


def test_topology_b_final_swr_is_unity_for_valid_match():
    result = evaluate_topology_b_from_components(
        FREQUENCY_HZ,
        Z1,
        Z2,
        L1_H,
        C1_F,
        C2_F,
        L2_H,
    )

    assert result.swr == pytest.approx(1.0)


def test_topology_b_default_match_selection_is_stable():
    first = evaluate_topology_b_from_components(
        FREQUENCY_HZ,
        Z1,
        Z2,
        L1_H,
        C1_F,
        C2_F,
        L2_H,
    )
    second = evaluate_topology_b_from_components(
        FREQUENCY_HZ,
        Z1,
        Z2,
        L1_H,
        C1_F,
        C2_F,
        L2_H,
    )

    assert first.input_match_topology_name == "B-HP"
    assert first.lmatch_solution.match_orientation == "series-then-shunt"
    assert second.lmatch_solution == first.lmatch_solution


def test_topology_b_accepts_explicit_lmatch_solution():
    topology_a_result = evaluate_topology_a(
        FREQUENCY_HZ,
        Z1,
        Z2,
        L1_H,
        C1_F,
        C2_F,
        L2_H,
    )
    solutions = find_l_matches(FREQUENCY_HZ, topology_a_result.z_input)
    explicit_solution = solutions[-1]

    result = evaluate_topology_b_from_components(
        FREQUENCY_HZ,
        Z1,
        Z2,
        L1_H,
        C1_F,
        C2_F,
        L2_H,
        input_match_solution=explicit_solution,
    )

    assert result.lmatch_solution == explicit_solution
    assert result.z_input.real == pytest.approx(50.0, abs=1e-9)
    assert result.z_input.imag == pytest.approx(0.0, abs=1e-9)


def test_topology_b_rejects_invalid_inputs_clearly():
    with pytest.raises(ValueError, match="target_resistance"):
        evaluate_topology_b_from_components(
            FREQUENCY_HZ,
            Z1,
            Z2,
            L1_H,
            C1_F,
            C2_F,
            L2_H,
            target_resistance=0,
        )

    with pytest.raises(ValueError, match="frequency_hz"):
        evaluate_topology_b_from_components(
            0,
            Z1,
            Z2,
            L1_H,
            C1_F,
            C2_F,
            L2_H,
        )
