import math

import pytest

from pns.feedline import (
    FEET_TO_METERS,
    SPEED_OF_LIGHT_M_PER_S,
    LosslessCoaxLine,
    feet_to_meters,
    meters,
    transform_feedpoint_to_box_end,
    transform_lossless_feedline_impedance,
    transform_two_feedpoints_to_box_end,
)


FREQUENCY_HZ = 7_000_000
Z0 = 50.0
VELOCITY_FACTOR = 0.66


def test_zero_length_line_returns_load_impedance():
    load = 73 - 12j

    transformed = transform_lossless_feedline_impedance(
        load,
        FREQUENCY_HZ,
        Z0,
        VELOCITY_FACTOR,
        0.0,
    )

    assert transformed == load


def test_half_wave_line_returns_load_impedance():
    load = 73 - 12j
    half_wave_m = _wavelength_on_line_m() / 2.0

    transformed = transform_lossless_feedline_impedance(
        load,
        FREQUENCY_HZ,
        Z0,
        VELOCITY_FACTOR,
        half_wave_m,
    )

    assert transformed == pytest.approx(load, abs=1e-10)


def test_quarter_wave_line_transforms_resistive_load():
    load = 25 + 0j
    quarter_wave_m = _wavelength_on_line_m() / 4.0

    transformed = transform_lossless_feedline_impedance(
        load,
        FREQUENCY_HZ,
        Z0,
        VELOCITY_FACTOR,
        quarter_wave_m,
    )

    assert transformed == pytest.approx((Z0**2 / load.real) + 0j, abs=1e-9)


def test_arbitrary_complex_load_matches_known_calculated_result():
    transformed = transform_lossless_feedline_impedance(
        75 - 25j,
        FREQUENCY_HZ,
        Z0,
        VELOCITY_FACTOR,
        12.3,
    )

    assert transformed == pytest.approx(
        86.0365299236464 + 11.63231174170658j,
    )


def test_feet_to_meters_conversion_works():
    assert feet_to_meters(100.0) == pytest.approx(30.48)
    assert feet_to_meters(1.0) == pytest.approx(FEET_TO_METERS)
    assert meters(12.5) == pytest.approx(12.5)


def test_transform_feedpoint_to_box_end_uses_line_description():
    line = LosslessCoaxLine(
        characteristic_impedance_ohms=Z0,
        velocity_factor=VELOCITY_FACTOR,
        length_m=12.3,
    )

    transformed = transform_feedpoint_to_box_end(
        75 - 25j,
        FREQUENCY_HZ,
        line,
    )

    assert transformed == pytest.approx(86.0365299236464 + 11.63231174170658j)


def test_transform_two_feedpoints_to_box_end_returns_both_impedances():
    line1 = LosslessCoaxLine(Z0, VELOCITY_FACTOR, 0.0)
    line2 = LosslessCoaxLine(Z0, VELOCITY_FACTOR, _wavelength_on_line_m() / 4.0)

    z1, z2 = transform_two_feedpoints_to_box_end(
        73 - 12j,
        25 + 0j,
        FREQUENCY_HZ,
        line1,
        line2,
    )

    assert z1 == 73 - 12j
    assert z2 == pytest.approx(100 + 0j, abs=1e-9)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"frequency_hz": 0}, "frequency_hz"),
        ({"velocity_factor": 0}, "velocity_factor"),
        ({"velocity_factor": 1.1}, "velocity_factor"),
        ({"load_impedance": 0j}, "load_impedance"),
        ({"length_m": -1.0}, "length_m"),
    ),
)
def test_invalid_transform_values_fail_clearly(kwargs, message):
    values = {
        "load_impedance": 50 + 0j,
        "frequency_hz": FREQUENCY_HZ,
        "characteristic_impedance_ohms": Z0,
        "velocity_factor": VELOCITY_FACTOR,
        "length_m": 1.0,
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=message):
        transform_lossless_feedline_impedance(**values)


def test_invalid_line_values_fail_clearly():
    with pytest.raises(ValueError, match="characteristic_impedance_ohms"):
        LosslessCoaxLine(0, VELOCITY_FACTOR, 1.0)

    with pytest.raises(ValueError, match="velocity_factor"):
        LosslessCoaxLine(Z0, 1.1, 1.0)

    with pytest.raises(ValueError, match="length_m"):
        LosslessCoaxLine(Z0, VELOCITY_FACTOR, -1.0)


def test_negative_length_unit_helpers_fail_clearly():
    with pytest.raises(ValueError, match="length"):
        feet_to_meters(-1.0)

    with pytest.raises(ValueError, match="length"):
        meters(-1.0)


def _wavelength_on_line_m():
    return SPEED_OF_LIGHT_M_PER_S * VELOCITY_FACTOR / FREQUENCY_HZ
