import pytest

from pns.lmatch import (
    evaluate_l_match_solution,
    find_l_matches,
    reactance_to_capacitance,
    reactance_to_inductance,
)


def test_reactance_to_inductance_and_capacitance_require_positive_frequency():
    with pytest.raises(ValueError, match="frequency_hz"):
        reactance_to_inductance(10.0, 0)

    with pytest.raises(ValueError, match="frequency_hz"):
        reactance_to_capacitance(-10.0, 0)


def test_find_l_matches_requires_positive_frequency_and_target_resistance():
    with pytest.raises(ValueError, match="frequency_hz"):
        find_l_matches(0, 25 + 0j)

    with pytest.raises(ValueError, match="target_resistance"):
        find_l_matches(7_015_000, 25 + 0j, target_resistance=0)


def test_find_l_matches_rejects_zero_or_negative_resistance_load():
    with pytest.raises(ValueError, match="load_impedance"):
        find_l_matches(7_015_000, 0j)

    with pytest.raises(ValueError, match="positive resistance"):
        find_l_matches(7_015_000, -25 + 10j)


def test_purely_resistive_load_below_50_ohms_has_valid_matches():
    solutions = find_l_matches(7_015_000, 25 + 0j)

    assert solutions
    assert {solution.topology_name for solution in solutions} == {"B-LP", "B-HP"}
    assert all(solution.series_value_si > 0 for solution in solutions)
    assert all(solution.shunt_value_si > 0 for solution in solutions)


def test_40m_phasing_priority_split_impedance_has_valid_match():
    solutions = find_l_matches(7_015_000, 19.30 - 26.35j)

    assert len(solutions) >= 1
    assert any(solution.topology_name == "B-HP" for solution in solutions)


def test_returned_solutions_evaluate_to_target_input_impedance():
    load_impedance = 19.30 - 26.35j
    solutions = find_l_matches(7_015_000, load_impedance)

    for solution in solutions:
        input_impedance = evaluate_l_match_solution(solution, load_impedance)
        assert input_impedance.real == pytest.approx(50.0, abs=1e-9)
        assert input_impedance.imag == pytest.approx(0.0, abs=1e-9)
        assert solution.input_impedance == pytest.approx(input_impedance)


def test_returned_solutions_have_unity_swr():
    solutions = find_l_matches(7_015_000, 19.30 - 26.35j)

    assert solutions
    for solution in solutions:
        assert solution.swr == pytest.approx(1.0)
