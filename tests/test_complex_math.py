import math

import pytest

from pns.rfmath import (
    admittance_to_impedance,
    complex_to_mag_phase,
    db20,
    impedance_to_admittance,
    parallel_impedance,
    phase_error_deg,
    polar_to_complex,
    reflection_coefficient,
    series_impedance,
    swr_from_impedance,
    undb20,
)


def test_polar_to_complex_preserves_target_magnitude_and_phase():
    z = polar_to_complex(0.356, 86.6)
    magnitude, phase_deg = complex_to_mag_phase(z)

    assert magnitude == pytest.approx(0.356)
    assert phase_deg == pytest.approx(86.6)


def test_complex_to_mag_phase_returns_degrees():
    magnitude, phase_deg = complex_to_mag_phase(1 + 1j)

    assert magnitude == pytest.approx(math.sqrt(2.0))
    assert phase_deg == pytest.approx(45.0)


def test_db20_and_undb20_round_trip_positive_magnitude():
    db = db20(0.356)

    assert db == pytest.approx(-8.97, abs=0.01)
    assert undb20(db) == pytest.approx(0.356)


def test_db20_rejects_nonpositive_magnitude():
    with pytest.raises(ValueError, match="magnitude"):
        db20(0)


def test_impedance_admittance_round_trip():
    z = 74.3166 - 37.5440j

    assert admittance_to_impedance(impedance_to_admittance(z)) == pytest.approx(z)


def test_series_impedance_sums_complex_values():
    assert series_impedance(10 + 2j, 5 - 1j, -3j) == pytest.approx(15 - 2j)


def test_parallel_impedance_combines_complex_impedances():
    z1 = 100 + 50j
    z2 = 75 - 25j
    expected = 1 / (1 / z1 + 1 / z2)

    assert parallel_impedance(z1, z2) == pytest.approx(expected)


def test_parallel_impedance_zero_branch_is_short_circuit():
    assert parallel_impedance(50 + 0j, 0j) == 0j


def test_parallel_impedance_requires_at_least_one_value():
    with pytest.raises(ValueError, match="at least one"):
        parallel_impedance()


def test_reflection_coefficient_for_matched_load_is_zero():
    assert reflection_coefficient(50 + 0j, 50) == pytest.approx(0j)


def test_swr_from_impedance_for_matched_load_is_one():
    assert swr_from_impedance(50 + 0j, 50) == pytest.approx(1.0)


def test_swr_from_impedance_for_open_or_short_is_infinite():
    assert swr_from_impedance(0j, 50) == math.inf


def test_phase_error_wraps_actual_minus_target_to_signed_range():
    assert phase_error_deg(179, -179) == pytest.approx(-2.0)
    assert phase_error_deg(-179, 179) == pytest.approx(2.0)
    assert phase_error_deg(10, 350) == pytest.approx(20.0)
