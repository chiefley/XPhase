"""Shared reporting helpers for feedline sweep results."""

from __future__ import annotations

from dataclasses import dataclass
import math

from pns.feedline_sweep import practical_warnings


@dataclass(frozen=True)
class SweepCandidateSummary:
    """Compact reporting summary for one feedline sweep candidate."""

    mode: str
    common_length: float
    offset: float | None
    port1_length: float
    port2_length: float
    length_unit: str
    port1_box_impedance_ohms: complex
    port2_box_impedance_ohms: complex
    achieved_ratio_magnitude: float
    achieved_ratio_phase_deg: float
    zin_ohms: complex
    swr: float
    score_or_objective: float
    total_estimated_loss_watts: float | None
    estimated_efficiency_percent: float | None
    worst_rms_voltage: float | None
    worst_rms_voltage_component: str | None
    worst_rms_current: float | None
    worst_rms_current_component: str | None
    worst_component_loss_watts: float | None
    worst_component_loss_name: str | None
    warning_count: int
    warnings: tuple[str, ...]


def summarize_equal_length_result(result) -> SweepCandidateSummary:
    """Build a reporting summary for an equal-length sweep result."""
    candidate = result.candidate
    return _summary(
        mode="equal_length",
        common_length=candidate.common_length,
        offset=None,
        port1_length=candidate.common_length,
        port2_length=candidate.common_length,
        length_unit=candidate.length_unit,
        result=result,
    )


def summarize_offset_result(result) -> SweepCandidateSummary:
    """Build a reporting summary for an offset sweep result."""
    candidate = result.candidate
    return _summary(
        mode="offset",
        common_length=candidate.common_length,
        offset=candidate.offset,
        port1_length=candidate.port1_length,
        port2_length=candidate.port2_length,
        length_unit=candidate.length_unit,
        result=result,
    )


def summarize_sweep_result(result) -> SweepCandidateSummary:
    """Dispatch to the correct summary helper for a feedline sweep result."""
    if hasattr(result.candidate, "offset"):
        return summarize_offset_result(result)
    return summarize_equal_length_result(result)


def practical_sort_key(summary: SweepCandidateSummary):
    """Return a display sort key for practical RF screening.

    This does not replace optimizer ranking. It prioritizes finite mathematical
    score, fewer warnings, lower estimated loss, lower current stress, lower
    voltage stress, lower SWR, and then lower optimizer score.
    """
    finite_score_rank = 0 if math.isfinite(summary.score_or_objective) else 1
    return (
        finite_score_rank,
        summary.warning_count,
        _missing_as_infinity(summary.total_estimated_loss_watts),
        _missing_as_infinity(summary.worst_rms_current),
        _missing_as_infinity(summary.worst_rms_voltage),
        summary.swr,
        _missing_as_infinity(summary.score_or_objective),
    )


def format_impedance(value: complex) -> str:
    """Return a compact human-readable complex impedance."""
    return f"{value.real:.3f}{value.imag:+.3f}j"


def format_optional_loss(value: float | None) -> str:
    """Return loss in watts or n/a."""
    if value is None:
        return "n/a"
    return f"{value:.2f}W"


def format_optional_efficiency(value: float | None) -> str:
    """Return efficiency in percent or n/a."""
    if value is None:
        return "n/a"
    return f"{value:.1f}%"


def format_optional_voltage(value: float | None) -> str:
    """Return RMS voltage or n/a."""
    if value is None:
        return "n/a"
    return f"{value:.1f}V"


def format_optional_current(value: float | None) -> str:
    """Return RMS current or n/a."""
    if value is None:
        return "n/a"
    return f"{value:.2f}A"


def _summary(
    mode: str,
    common_length: float,
    offset: float | None,
    port1_length: float,
    port2_length: float,
    length_unit: str,
    result,
) -> SweepCandidateSummary:
    stress_values = _stress_values(result.stress_report)
    warnings = practical_warnings(result)
    return SweepCandidateSummary(
        mode=mode,
        common_length=common_length,
        offset=offset,
        port1_length=port1_length,
        port2_length=port2_length,
        length_unit=length_unit,
        port1_box_impedance_ohms=result.candidate.port1_box_impedance_ohms,
        port2_box_impedance_ohms=result.candidate.port2_box_impedance_ohms,
        achieved_ratio_magnitude=result.achieved_ratio_magnitude,
        achieved_ratio_phase_deg=result.achieved_ratio_phase_deg,
        zin_ohms=result.zin_ohms,
        swr=result.swr,
        score_or_objective=result.score_or_objective,
        total_estimated_loss_watts=stress_values["total_loss"],
        estimated_efficiency_percent=stress_values["efficiency"],
        worst_rms_voltage=stress_values["worst_voltage"],
        worst_rms_voltage_component=stress_values["worst_voltage_component"],
        worst_rms_current=stress_values["worst_current"],
        worst_rms_current_component=stress_values["worst_current_component"],
        worst_component_loss_watts=stress_values["worst_loss"],
        worst_component_loss_name=stress_values["worst_loss_component"],
        warning_count=len(warnings),
        warnings=warnings,
    )


def _stress_values(stress_report) -> dict[str, float | str | None]:
    if stress_report is None:
        return {
            "total_loss": None,
            "efficiency": None,
            "worst_voltage": None,
            "worst_voltage_component": None,
            "worst_current": None,
            "worst_current_component": None,
            "worst_loss": None,
            "worst_loss_component": None,
        }

    worst_voltage = max(
        stress_report.component_stresses,
        key=lambda component: component.rms_voltage,
    )
    worst_current = max(
        stress_report.component_stresses,
        key=lambda component: component.rms_current,
    )
    worst_loss = max(
        stress_report.component_stresses,
        key=lambda component: component.loss_watts,
    )
    return {
        "total_loss": stress_report.total_estimated_loss_watts,
        "efficiency": stress_report.estimated_efficiency_percent,
        "worst_voltage": worst_voltage.rms_voltage,
        "worst_voltage_component": worst_voltage.name,
        "worst_current": worst_current.rms_current,
        "worst_current_component": worst_current.name,
        "worst_loss": worst_loss.loss_watts,
        "worst_loss_component": worst_loss.name,
    }


def _missing_as_infinity(value: float | None) -> float:
    if value is None:
        return math.inf
    return value
