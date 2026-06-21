import math

import pytest

from pns.rfmath import parallel_impedance, swr_from_impedance
from pns.topology_a import TopologyAResult, evaluate_topology_a


def test_topology_a_rejects_open_or_omitted_required_components():
    with pytest.raises(ValueError, match="c1_f"):
        evaluate_topology_a(
            frequency_hz=7_015_000,
            z1=50 + 0j,
            z2=50 + 0j,
            l1_h=1e-6,
            c1_f=None,
            c2_f=100e-12,
            l2_h=1e-6,
        )

    with pytest.raises(ValueError, match="l2_h"):
        evaluate_topology_a(
            frequency_hz=7_015_000,
            z1=50 + 0j,
            z2=50 + 0j,
            l1_h=1e-6,
            c1_f=100e-12,
            c2_f=100e-12,
            l2_h=0,
        )


def test_topology_a_rejects_invalid_frequency_and_zero_loads():
    with pytest.raises(ValueError, match="frequency_hz"):
        evaluate_topology_a(0, 50 + 0j, 50 + 0j, 1e-6, 100e-12, 100e-12, 1e-6)

    with pytest.raises(ValueError, match="z1"):
        evaluate_topology_a(7_015_000, 0j, 50 + 0j, 1e-6, 100e-12, 100e-12, 1e-6)

    with pytest.raises(ValueError, match="z2"):
        evaluate_topology_a(7_015_000, 50 + 0j, 0j, 1e-6, 100e-12, 100e-12, 1e-6)


def test_known_simple_case_gives_sane_results():
    result = evaluate_topology_a(
        frequency_hz=1_000_000,
        z1=100 + 0j,
        z2=100 + 0j,
        l1_h=10e-6,
        c1_f=1e-9,
        c2_f=1e-9,
        l2_h=10e-6,
        split_voltage=1 + 0j,
    )

    assert isinstance(result, TopologyAResult)
    assert result.z_input.real > 0
    assert abs(result.v_port1) > 0
    assert abs(result.v_port2) > 0
    assert result.i_branch1 == pytest.approx(1 / result.z_branch1_input)
    assert result.i_branch2 == pytest.approx(1 / result.z_branch2_input)
    assert result.y_input == pytest.approx(1 / result.z_input)
    assert result.branch1_complex_power_for_split_voltage == pytest.approx(
        result.i_branch1.conjugate()
    )


def test_topology_a_matches_independent_branch_equations():
    frequency_hz = 7_015_000
    z1 = 74.3166 - 37.5440j
    z2 = 17.7330 + 4.6350j
    l1_h = 1.2e-6
    c1_f = 180e-12
    c2_f = 220e-12
    l2_h = 1.8e-6
    split_voltage = 2.5 - 0.75j
    omega = 2.0 * math.pi * frequency_hz

    z_l1 = 1j * omega * l1_h
    z_c1 = 1 / (1j * omega * c1_f)
    z_c2 = 1 / (1j * omega * c2_f)
    z_l2 = 1j * omega * l2_h
    z_port1_parallel = parallel_impedance(z1, z_c1)
    z_port2_parallel = parallel_impedance(z2, z_l2)
    expected_z_branch1 = z_l1 + z_port1_parallel
    expected_z_branch2 = z_c2 + z_port2_parallel
    expected_v_port1 = split_voltage * z_port1_parallel / expected_z_branch1
    expected_v_port2 = split_voltage * z_port2_parallel / expected_z_branch2

    result = evaluate_topology_a(
        frequency_hz=frequency_hz,
        z1=z1,
        z2=z2,
        l1_h=l1_h,
        c1_f=c1_f,
        c2_f=c2_f,
        l2_h=l2_h,
        split_voltage=split_voltage,
    )

    assert result.z_branch1_input == pytest.approx(expected_z_branch1)
    assert result.z_branch2_input == pytest.approx(expected_z_branch2)
    assert result.v_port1 == pytest.approx(expected_v_port1)
    assert result.v_port2 == pytest.approx(expected_v_port2)
    assert result.v_ratio_v2_over_v1 == pytest.approx(expected_v_port2 / expected_v_port1)


def test_z_input_is_parallel_combination_of_branch_inputs():
    result = evaluate_topology_a(
        frequency_hz=7_015_000,
        z1=74.3166 - 37.5440j,
        z2=17.7330 + 4.6350j,
        l1_h=1.2e-6,
        c1_f=180e-12,
        c2_f=220e-12,
        l2_h=1.8e-6,
    )

    assert result.z_input == pytest.approx(
        parallel_impedance(result.z_branch1_input, result.z_branch2_input)
    )


def test_swr_uses_supplied_reference_impedance_defaulting_to_50_ohms():
    result_default = evaluate_topology_a(
        frequency_hz=7_015_000,
        z1=74.3166 - 37.5440j,
        z2=17.7330 + 4.6350j,
        l1_h=1.2e-6,
        c1_f=180e-12,
        c2_f=220e-12,
        l2_h=1.8e-6,
    )
    result_75 = evaluate_topology_a(
        frequency_hz=7_015_000,
        z1=74.3166 - 37.5440j,
        z2=17.7330 + 4.6350j,
        l1_h=1.2e-6,
        c1_f=180e-12,
        c2_f=220e-12,
        l2_h=1.8e-6,
        z0=75,
    )

    assert result_default.swr == pytest.approx(swr_from_impedance(result_default.z_input, 50))
    assert result_75.swr == pytest.approx(swr_from_impedance(result_75.z_input, 75))
    assert result_default.swr != pytest.approx(result_75.swr)
