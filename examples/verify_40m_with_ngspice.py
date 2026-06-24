from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pns.cases import load_case  # noqa: E402
from pns.ngspice import (  # noqa: E402
    find_ngspice_executable,
    parse_ngspice_measurements,
    run_ngspice_batch,
    write_ngspice_netlist,
)
from pns.optimize import optimize_topology_b_from_case  # noqa: E402
from pns.rfmath import complex_to_mag_phase, phase_error_deg  # noqa: E402


def main() -> int:
    case_path = REPO_ROOT / "cases" / "40m_inverted_v_90ft_feedlines.json"
    case_data = load_case(case_path)
    result = optimize_topology_b_from_case(case_data)

    output_path = REPO_ROOT / "ngspice" / "xphase_40m_topology_b.cir"
    written_path = write_ngspice_netlist(
        path=output_path,
        topology_b_result=result.result,
        frequency_hz=case_data["frequency_hz"],
        z1=complex(
            case_data["ports"]["port1"]["z_ohms"]["r"],
            case_data["ports"]["port1"]["z_ohms"]["x"],
        ),
        z2=complex(
            case_data["ports"]["port2"]["z_ohms"]["r"],
            case_data["ports"]["port2"]["z_ohms"]["x"],
        ),
        output_power_watts=case_data["power_watts"],
        include_loss=False,
        inductor_q=case_data["component_assumptions"]["inductor_q"],
        capacitor_q=case_data["component_assumptions"]["capacitor_q"],
    )
    print(f"ngspice netlist: {written_path.resolve()}")

    ngspice_executable = find_ngspice_executable()
    if ngspice_executable is None:
        print("ngspice not found. Install with: sudo apt install ngspice")
        return 0

    try:
        output_text = run_ngspice_batch(written_path, ngspice_executable)
        measurements = parse_ngspice_measurements(output_text)
        measured_ratio = measurements["xphase_vratio"]
    except (KeyError, RuntimeError, ValueError) as exc:
        print("ngspice verification: FAIL")
        print(f"reason: {exc}")
        return 1

    measured_mag, measured_phase_deg = complex_to_mag_phase(measured_ratio)
    expected_mag = result.v_ratio_magnitude
    expected_phase_deg = result.v_ratio_phase_deg
    mag_error = abs(measured_mag - expected_mag)
    phase_error = phase_error_deg(measured_phase_deg, expected_phase_deg)

    mag_pass = mag_error <= 1e-6
    phase_pass = abs(phase_error) <= 1e-4
    status = "PASS" if mag_pass and phase_pass else "FAIL"

    print(f"ngspice executable: {ngspice_executable}")
    print(f"XPhase |V2/V1|: {expected_mag:.12g}")
    print(f"ngspice |V2/V1|: {measured_mag:.12g}")
    print(f"magnitude error: {mag_error:.3g}")
    print(f"XPhase phase: {expected_phase_deg:.12g} deg")
    print(f"ngspice phase: {measured_phase_deg:.12g} deg")
    print(f"phase error: {phase_error:.3g} deg")
    print(f"ngspice verification: {status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
