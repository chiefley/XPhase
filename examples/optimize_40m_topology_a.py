from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pns.cases import load_case  # noqa: E402
from pns.cases import case_to_complex_values  # noqa: E402
from pns.objectives import ObjectiveWeights, case_targets  # noqa: E402
from pns.optimize import (  # noqa: E402
    diagnose_topology_a_optimization,
    optimize_topology_a_from_case,
)


WEIGHT_SETS = [
    ("balanced", None),
    (
        "phasing",
        ObjectiveWeights(
            magnitude_error_db=10.0,
            phase_error_deg=10.0,
            input_r_error_ohms=0.05,
            input_x_error_ohms=0.05,
        ),
    ),
    (
        "matching",
        ObjectiveWeights(
            magnitude_error_db=0.1,
            phase_error_deg=0.1,
            input_r_error_ohms=10.0,
            input_x_error_ohms=10.0,
        ),
    ),
]


def main() -> None:
    case_path = REPO_ROOT / "cases" / "40m_inverted_v_90ft_feedlines.json"
    data = load_case(case_path)
    values = case_to_complex_values(data)
    targets = case_targets(data)

    rows = []
    for label, weights in WEIGHT_SETS:
        result = optimize_topology_a_from_case(data, weights=weights)
        diagnostics = diagnose_topology_a_optimization(
            result,
            frequency_hz=values["frequency_hz"],
            z1=values["z1_ohms"],
            z2=values["z2_ohms"],
            target_ratio=targets.target_ratio,
            target_input_impedance=targets.target_input_impedance,
            weights=weights,
        )
        rows.append((label, result, diagnostics))

    print(
        "case       "
        "L1_uH   C1_pF   C2_pF   L2_uH   "
        "|V2/V1| phase  magErr phaseErr  Zin_R  Zin_X  SWR   score    bounds"
    )
    for label, _result, diagnostics in rows:
        components = diagnostics.components
        bounds = _format_bound_hits(diagnostics.component_bound_proximity)
        print(
            f"{label:<10} "
            f"{components.l1_h * 1e6:6.3f} "
            f"{components.c1_f * 1e12:7.2f} "
            f"{components.c2_f * 1e12:7.2f} "
            f"{components.l2_h * 1e6:7.3f} "
            f"{diagnostics.v_ratio_magnitude:7.3f} "
            f"{diagnostics.v_ratio_phase_deg:6.2f} "
            f"{diagnostics.magnitude_error_db:7.2f} "
            f"{diagnostics.phase_error_deg:8.2f} "
            f"{diagnostics.z_input.real:6.2f} "
            f"{diagnostics.z_input.imag:6.2f} "
            f"{diagnostics.swr:5.2f} "
            f"{diagnostics.total_score:8.2f} "
            f"{bounds}"
        )


def _format_bound_hits(bound_proximity: dict[str, str | None]) -> str:
    hits = [
        f"{name}:{bound}"
        for name, bound in bound_proximity.items()
        if bound is not None
    ]
    return ",".join(hits) if hits else "-"


if __name__ == "__main__":
    main()
