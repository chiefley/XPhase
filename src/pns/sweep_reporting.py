"""Shared reporting helpers for feedline sweep results."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import math
from pathlib import Path

from pns.feedline_sweep import practical_warnings


KNOWN_COMPONENT_STRESS_NAMES = (
    "L1",
    "C1",
    "C2",
    "L2",
    "input_series",
    "input_shunt",
)


def _component_stress_csv_fieldnames() -> tuple[str, ...]:
    return tuple(
        field_name
        for component_name in KNOWN_COMPONENT_STRESS_NAMES
        for field_name in (
            f"{component_name}_rms_voltage",
            f"{component_name}_rms_current",
            f"{component_name}_loss_watts",
        )
    )


CSV_FIELDNAMES = (
    "rank_math_within_mode",
    "rank_practical_combined",
    "mode",
    "polarity",
    "target_ratio_was_inverted",
    "common_length",
    "offset",
    "port1_length",
    "port2_length",
    "length_unit",
    "port1_box_r_ohms",
    "port1_box_x_ohms",
    "port2_box_r_ohms",
    "port2_box_x_ohms",
    "achieved_v2_over_v1_magnitude",
    "achieved_v2_over_v1_phase_deg",
    "zin_r_ohms",
    "zin_x_ohms",
    "swr",
    "score_or_objective",
    "total_estimated_loss_watts",
    "estimated_efficiency_percent",
    *_component_stress_csv_fieldnames(),
    "worst_rms_voltage",
    "worst_rms_voltage_component",
    "worst_rms_current",
    "worst_rms_current_component",
    "worst_component_loss_watts",
    "worst_component_loss_name",
    "warning_count",
    "warnings",
)


@dataclass(frozen=True)
class ComponentStressSummary:
    """RMS stress and estimated loss for one synthesized component."""

    name: str
    rms_voltage: float
    rms_current: float
    loss_watts: float


@dataclass(frozen=True)
class SweepCandidateSummary:
    """Compact reporting summary for one feedline sweep candidate."""

    mode: str
    polarity: str
    target_ratio_was_inverted: bool
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
    component_stresses: tuple[ComponentStressSummary, ...] = ()


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


def summary_to_csv_row(
    summary: SweepCandidateSummary,
    *,
    rank_math_within_mode: int | None = None,
    rank_practical_combined: int | None = None,
) -> dict[str, object]:
    """Convert a sweep summary to one CSV row.

    Optional numeric/string fields that are unavailable are serialized as empty
    strings. Warnings are serialized as a semicolon-separated string.
    """
    row = {
        "rank_math_within_mode": _csv_optional(rank_math_within_mode),
        "rank_practical_combined": _csv_optional(rank_practical_combined),
        "mode": summary.mode,
        "polarity": summary.polarity,
        "target_ratio_was_inverted": summary.target_ratio_was_inverted,
        "common_length": summary.common_length,
        "offset": _csv_optional(summary.offset),
        "port1_length": summary.port1_length,
        "port2_length": summary.port2_length,
        "length_unit": summary.length_unit,
        "port1_box_r_ohms": summary.port1_box_impedance_ohms.real,
        "port1_box_x_ohms": summary.port1_box_impedance_ohms.imag,
        "port2_box_r_ohms": summary.port2_box_impedance_ohms.real,
        "port2_box_x_ohms": summary.port2_box_impedance_ohms.imag,
        "achieved_v2_over_v1_magnitude": summary.achieved_ratio_magnitude,
        "achieved_v2_over_v1_phase_deg": summary.achieved_ratio_phase_deg,
        "zin_r_ohms": summary.zin_ohms.real,
        "zin_x_ohms": summary.zin_ohms.imag,
        "swr": summary.swr,
        "score_or_objective": summary.score_or_objective,
        "total_estimated_loss_watts": _csv_optional(
            summary.total_estimated_loss_watts
        ),
        "estimated_efficiency_percent": _csv_optional(
            summary.estimated_efficiency_percent
        ),
        "worst_rms_voltage": _csv_optional(summary.worst_rms_voltage),
        "worst_rms_voltage_component": _csv_optional(
            summary.worst_rms_voltage_component
        ),
        "worst_rms_current": _csv_optional(summary.worst_rms_current),
        "worst_rms_current_component": _csv_optional(
            summary.worst_rms_current_component
        ),
        "worst_component_loss_watts": _csv_optional(
            summary.worst_component_loss_watts
        ),
        "worst_component_loss_name": _csv_optional(summary.worst_component_loss_name),
        "warning_count": summary.warning_count,
        "warnings": "; ".join(summary.warnings),
    }
    component_stress_by_name = {
        component.name: component for component in summary.component_stresses
    }
    for component_name in KNOWN_COMPONENT_STRESS_NAMES:
        component = component_stress_by_name.get(component_name)
        row[f"{component_name}_rms_voltage"] = _csv_component_value(
            component,
            "rms_voltage",
        )
        row[f"{component_name}_rms_current"] = _csv_component_value(
            component,
            "rms_current",
        )
        row[f"{component_name}_loss_watts"] = _csv_component_value(
            component,
            "loss_watts",
        )
    return row


def write_summaries_csv(
    path,
    summaries,
    *,
    practical_ordered_summaries=None,
    math_rank_by_mode=None,
) -> Path:
    """Write combined sweep summaries to CSV and return the written path.

    Optional stress/loss fields are written as empty cells when unavailable.
    ``practical_ordered_summaries`` and ``math_rank_by_mode`` may be supplied to
    annotate each row with practical and within-mode mathematical ranks.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    practical_rank = _rank_map(practical_ordered_summaries)
    math_rank_by_mode = math_rank_by_mode or {}

    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for summary in summaries:
            writer.writerow(
                summary_to_csv_row(
                    summary,
                    rank_math_within_mode=math_rank_by_mode.get(summary),
                    rank_practical_combined=practical_rank.get(summary),
                )
            )
    return path


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
        polarity=getattr(result, "polarity", "normal"),
        target_ratio_was_inverted=getattr(
            result,
            "target_ratio_was_inverted",
            False,
        ),
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
        component_stresses=stress_values["component_stresses"],
    )


def _stress_values(stress_report) -> dict[str, object]:
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
            "component_stresses": (),
        }

    component_stresses = tuple(
        ComponentStressSummary(
            name=component.name,
            rms_voltage=component.rms_voltage,
            rms_current=component.rms_current,
            loss_watts=component.loss_watts,
        )
        for component in stress_report.component_stresses
    )
    if not component_stresses:
        return {
            "total_loss": stress_report.total_estimated_loss_watts,
            "efficiency": stress_report.estimated_efficiency_percent,
            "worst_voltage": None,
            "worst_voltage_component": None,
            "worst_current": None,
            "worst_current_component": None,
            "worst_loss": None,
            "worst_loss_component": None,
            "component_stresses": (),
        }

    worst_voltage = max(
        component_stresses,
        key=lambda component: component.rms_voltage,
    )
    worst_current = max(
        component_stresses,
        key=lambda component: component.rms_current,
    )
    worst_loss = max(
        component_stresses,
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
        "component_stresses": component_stresses,
    }


def _missing_as_infinity(value: float | None) -> float:
    if value is None:
        return math.inf
    return value


def _csv_optional(value):
    if value is None:
        return ""
    return value


def _csv_component_value(component, attribute: str):
    if component is None:
        return ""
    return getattr(component, attribute)


def _rank_map(summaries) -> dict[SweepCandidateSummary, int]:
    if summaries is None:
        return {}
    return {summary: rank for rank, summary in enumerate(summaries, start=1)}
