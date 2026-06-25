"""Lossless feedline reference-plane transformations."""

from __future__ import annotations

from dataclasses import dataclass
import math


SPEED_OF_LIGHT_M_PER_S = 299_792_458.0
FEET_TO_METERS = 0.3048


@dataclass(frozen=True)
class LosslessCoaxLine:
    """Physical lossless coax description for impedance transformation."""

    characteristic_impedance_ohms: float
    velocity_factor: float
    length_m: float

    def __post_init__(self) -> None:
        _validate_line_values(
            self.characteristic_impedance_ohms,
            self.velocity_factor,
            self.length_m,
        )


def feet_to_meters(feet: float) -> float:
    """Convert feet to meters."""
    if feet < 0:
        raise ValueError("length must be nonnegative")
    return feet * FEET_TO_METERS


def meters(length_m: float) -> float:
    """Return a meter value after validating it as a physical length."""
    if length_m < 0:
        raise ValueError("length must be nonnegative")
    return length_m


def transform_lossless_feedline_impedance(
    load_impedance: complex,
    frequency_hz: float,
    characteristic_impedance_ohms: float,
    velocity_factor: float,
    length_m: float,
) -> complex:
    """Transform a load impedance through a physical lossless coax line."""
    _validate_transform_inputs(
        load_impedance,
        frequency_hz,
        characteristic_impedance_ohms,
        velocity_factor,
        length_m,
    )

    if length_m == 0:
        return load_impedance

    z0 = characteristic_impedance_ohms
    beta = _phase_constant_rad_per_m(frequency_hz, velocity_factor)
    tangent = math.tan(beta * length_m)
    return z0 * (load_impedance + 1j * z0 * tangent) / (
        z0 + 1j * load_impedance * tangent
    )


def transform_feedpoint_to_box_end(
    feedpoint_impedance: complex,
    frequency_hz: float,
    feedline: LosslessCoaxLine,
) -> complex:
    """Return the phasing-box-end impedance for one feedpoint and feedline."""
    return transform_lossless_feedline_impedance(
        load_impedance=feedpoint_impedance,
        frequency_hz=frequency_hz,
        characteristic_impedance_ohms=feedline.characteristic_impedance_ohms,
        velocity_factor=feedline.velocity_factor,
        length_m=feedline.length_m,
    )


def transform_two_feedpoints_to_box_end(
    feedpoint1_impedance: complex,
    feedpoint2_impedance: complex,
    frequency_hz: float,
    feedline1: LosslessCoaxLine,
    feedline2: LosslessCoaxLine,
) -> tuple[complex, complex]:
    """Return box-end impedances for two feedpoints and their feedlines."""
    return (
        transform_feedpoint_to_box_end(
            feedpoint1_impedance,
            frequency_hz,
            feedline1,
        ),
        transform_feedpoint_to_box_end(
            feedpoint2_impedance,
            frequency_hz,
            feedline2,
        ),
    )


def _phase_constant_rad_per_m(frequency_hz: float, velocity_factor: float) -> float:
    wavelength_on_line_m = SPEED_OF_LIGHT_M_PER_S * velocity_factor / frequency_hz
    return 2.0 * math.pi / wavelength_on_line_m


def _validate_transform_inputs(
    load_impedance: complex,
    frequency_hz: float,
    characteristic_impedance_ohms: float,
    velocity_factor: float,
    length_m: float,
) -> None:
    if load_impedance == 0:
        raise ValueError("load_impedance must not be zero")
    _require_positive("frequency_hz", frequency_hz)
    _validate_line_values(characteristic_impedance_ohms, velocity_factor, length_m)


def _validate_line_values(
    characteristic_impedance_ohms: float,
    velocity_factor: float,
    length_m: float,
) -> None:
    _require_positive("characteristic_impedance_ohms", characteristic_impedance_ohms)
    _require_positive("velocity_factor", velocity_factor)
    if velocity_factor > 1:
        raise ValueError("velocity_factor must be less than or equal to 1")
    if length_m < 0:
        raise ValueError("length_m must be nonnegative")


def _require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")
