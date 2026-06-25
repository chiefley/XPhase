from copy import deepcopy
from pathlib import Path

import pytest

from pns.cases import CaseValidationError, case_to_complex_values, load_case, validate_case


CASE_PATH = Path(__file__).resolve().parents[1] / "cases" / "40m_inverted_v_90ft_feedlines.json"
PLUS_Y_FEEDPOINT_CASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "cases"
    / "40m_inverted_v_feedpoints_plus_y_7020khz.json"
)


def test_existing_40m_case_loads_successfully():
    data = load_case(CASE_PATH)

    assert data["name"] == "40m_inverted_v_90ft_feedlines_preliminary"


def test_existing_40m_case_loads_complex_impedances():
    values = case_to_complex_values(load_case(CASE_PATH))

    assert values["z1_ohms"] == complex(74.3166, -37.5440)
    assert values["z2_ohms"] == complex(17.7330, 4.6350)


def test_existing_40m_case_loads_target_ratio_fields():
    values = case_to_complex_values(load_case(CASE_PATH))

    assert values["target_voltage_ratio_magnitude"] == pytest.approx(0.356)
    assert values["target_voltage_ratio_phase_deg"] == pytest.approx(86.6)


def test_plus_y_feedpoint_case_loads_nec_feedpoint_impedances():
    data = load_case(PLUS_Y_FEEDPOINT_CASE_PATH)
    values = case_to_complex_values(data)

    assert data["reference_plane"] == "nec_feedpoint"
    assert data["pattern"]["desired_forward_direction"] == "+Y"
    assert data["ports"]["port1"]["role"] == "rear_element_minus_y"
    assert data["ports"]["port2"]["role"] == "forward_element_plus_y"
    assert values["frequency_hz"] == pytest.approx(7_020_000)
    assert values["z1_ohms"] == complex(25.6111, -34.7429)
    assert values["z2_ohms"] == complex(47.5898, 36.0728)


def test_plus_y_feedpoint_case_preserves_voltage_and_future_current_targets():
    data = load_case(PLUS_Y_FEEDPOINT_CASE_PATH)
    values = case_to_complex_values(data)
    future_current_target = data["target"]["future_current_ratio_i2_over_i1"]

    assert values["target_voltage_ratio_magnitude"] == pytest.approx(1.34942)
    assert values["target_voltage_ratio_phase_deg"] == pytest.approx(-30.744)
    assert future_current_target["magnitude"] == pytest.approx(0.97468)
    assert future_current_target["phase_deg"] == pytest.approx(-121.499)
    assert future_current_target["status"] == "documentation_only"


def test_validation_fails_on_missing_required_field():
    data = load_case(CASE_PATH)
    invalid_data = deepcopy(data)
    del invalid_data["target"]["input_impedance_ohms"]["r"]

    with pytest.raises(CaseValidationError, match="missing required field"):
        validate_case(invalid_data)


def test_validation_fails_on_invalid_numeric_field():
    data = load_case(CASE_PATH)
    invalid_data = deepcopy(data)
    invalid_data["frequency_hz"] = 0

    with pytest.raises(CaseValidationError, match="frequency_hz"):
        validate_case(invalid_data)
