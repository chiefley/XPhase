from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pns.cases import load_case  # noqa: E402
from pns.optimize import optimize_topology_a_from_case  # noqa: E402
from pns.rfmath import complex_to_mag_phase  # noqa: E402


def main() -> None:
    case_path = REPO_ROOT / "cases" / "40m_inverted_v_90ft_feedlines.json"
    result = optimize_topology_a_from_case(load_case(case_path))
    magnitude, phase_deg = complex_to_mag_phase(result.result.v_ratio_v2_over_v1)

    print(f"success: {result.success}")
    print(f"message: {result.message}")
    print(f"L1: {result.components.l1_h:.6g} H")
    print(f"C1: {result.components.c1_f:.6g} F")
    print(f"C2: {result.components.c2_f:.6g} F")
    print(f"L2: {result.components.l2_h:.6g} H")
    print(f"V2/V1: {magnitude:.6g} angle {phase_deg:.6g} deg")
    print(
        "Zin: "
        f"{result.result.z_input.real:.6g} "
        f"{result.result.z_input.imag:+.6g}j ohms"
    )
    print(f"SWR: {result.result.swr:.6g}")
    print(f"score: {result.score.total_score:.6g}")


if __name__ == "__main__":
    main()
