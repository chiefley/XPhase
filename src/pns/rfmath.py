"""Basic RF math helpers."""

from __future__ import annotations

import cmath
import math


def polar_to_complex(magnitude: float, phase_deg: float) -> complex:
    """Convert magnitude and phase in degrees to a complex value."""
    return cmath.rect(magnitude, math.radians(phase_deg))


def complex_to_mag_phase(z: complex) -> tuple[float, float]:
    """Convert a complex value to magnitude and phase in degrees."""
    return abs(z), math.degrees(cmath.phase(z))


def db20(magnitude: float) -> float:
    """Convert a positive voltage/current magnitude ratio to dB."""
    if magnitude <= 0:
        raise ValueError("magnitude must be greater than 0")

    return 20.0 * math.log10(magnitude)


def undb20(db: float) -> float:
    """Convert a dB voltage/current ratio to linear magnitude."""
    return 10.0 ** (db / 20.0)


def impedance_to_admittance(z: complex) -> complex:
    """Convert impedance to admittance."""
    return 1.0 / z


def admittance_to_impedance(y: complex) -> complex:
    """Convert admittance to impedance."""
    return 1.0 / y


def series_impedance(*z_values: complex) -> complex:
    """Combine impedances in series."""
    return sum(z_values, 0j)


def parallel_impedance(*z_values: complex) -> complex:
    """Combine impedances in parallel."""
    if not z_values:
        raise ValueError("at least one impedance is required")

    if any(z == 0 for z in z_values):
        return 0j

    return admittance_to_impedance(sum(impedance_to_admittance(z) for z in z_values))


def reflection_coefficient(z: complex, z0: complex = 50) -> complex:
    """Return load reflection coefficient relative to reference impedance."""
    return (z - z0) / (z + z0)


def swr_from_impedance(z: complex, z0: complex = 50) -> float:
    """Return standing wave ratio for an impedance and reference impedance."""
    gamma_magnitude = abs(reflection_coefficient(z, z0))
    if gamma_magnitude >= 1.0:
        return math.inf

    return (1.0 + gamma_magnitude) / (1.0 - gamma_magnitude)


def phase_error_deg(actual_deg: float, target_deg: float) -> float:
    """Return actual minus target phase error, wrapped to [-180, +180]."""
    return ((actual_deg - target_deg + 180.0) % 360.0) - 180.0
