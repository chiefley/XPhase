from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pns.cases import load_case  # noqa: E402
from pns.feedline import (  # noqa: E402
    LosslessCoaxLine,
    feet_to_meters,
    transform_two_feedpoints_to_box_end,
)


def main() -> None:
    case_path = REPO_ROOT / "cases" / "40m_inverted_v_90ft_feedlines.json"
    case_data = load_case(case_path)
    frequency_hz = case_data["frequency_hz"]

    feedpoint1 = complex(
        case_data["ports"]["port1"]["z_ohms"]["r"],
        case_data["ports"]["port1"]["z_ohms"]["x"],
    )
    feedpoint2 = complex(
        case_data["ports"]["port2"]["z_ohms"]["r"],
        case_data["ports"]["port2"]["z_ohms"]["x"],
    )

    line1 = LosslessCoaxLine(
        characteristic_impedance_ohms=50.0,
        velocity_factor=0.66,
        length_m=feet_to_meters(90.0),
    )
    line2 = LosslessCoaxLine(
        characteristic_impedance_ohms=50.0,
        velocity_factor=0.66,
        length_m=feet_to_meters(95.0),
    )

    box_end1, box_end2 = transform_two_feedpoints_to_box_end(
        feedpoint1,
        feedpoint2,
        frequency_hz,
        line1,
        line2,
    )

    print(f"case: {case_data['name']}")
    print(f"frequency: {frequency_hz:.6g} Hz")
    print("sample feedlines:")
    print(_format_line("  port1", line1))
    print(_format_line("  port2", line2))
    print("feedpoint impedances:")
    print(f"  port1: {_format_impedance(feedpoint1)} ohms")
    print(f"  port2: {_format_impedance(feedpoint2)} ohms")
    print("box-end impedances after lossless feedline transform:")
    print(f"  port1: {_format_impedance(box_end1)} ohms")
    print(f"  port2: {_format_impedance(box_end2)} ohms")


def _format_line(label: str, line: LosslessCoaxLine) -> str:
    length_ft = line.length_m / 0.3048
    return (
        f"{label}: Z0={line.characteristic_impedance_ohms:.6g} ohms, "
        f"VF={line.velocity_factor:.6g}, length={length_ft:.3f} ft"
    )


def _format_impedance(value: complex) -> str:
    return f"{value.real:.6g} {value.imag:+.6g}j"


if __name__ == "__main__":
    main()
