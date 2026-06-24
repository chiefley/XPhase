from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pns.ngspice import (
    export_topology_b_ngspice_netlist,
    find_ngspice_executable,
    parse_ngspice_measurements,
    run_ngspice_batch,
    write_ngspice_netlist,
)
from pns.topology_b import evaluate_topology_b_from_components


FREQUENCY_HZ = 7_015_000
Z1 = 74.3166 - 37.5440j
Z2 = 17.7330 + 4.6350j
L1_H = 20e-9
C1_F = 5e-12
C2_F = 445.21e-12
L2_H = 10e-6


@pytest.fixture
def topology_b_result():
    return evaluate_topology_b_from_components(
        FREQUENCY_HZ,
        Z1,
        Z2,
        L1_H,
        C1_F,
        C2_F,
        L2_H,
    )


def test_exported_ngspice_netlist_contains_key_nodes_and_components(
    topology_b_result,
):
    netlist = export_topology_b_ngspice_netlist(
        topology_b_result,
        FREQUENCY_HZ,
        Z1,
        Z2,
    )

    for text in (
        "Vsrc input_src 0 AC",
        "Rsrc input_src input",
        " split",
        " port1",
        " port2",
        "L1",
        "C1",
        "C2",
        "L2",
        "Rload1",
        "Rload2",
    ):
        assert text in netlist


def test_exported_ngspice_netlist_uses_single_frequency_ac(topology_b_result):
    netlist = export_topology_b_ngspice_netlist(
        topology_b_result,
        FREQUENCY_HZ,
        Z1,
        Z2,
    )

    assert f".ac lin 1 {FREQUENCY_HZ} {FREQUENCY_HZ}" in netlist
    assert ".control" in netlist
    assert "print xphase_vratio" in netlist
    assert "print i(l1)" in netlist
    assert "print i(c2)" in netlist
    assert "print i(l2)" in netlist


def test_exported_ngspice_netlist_can_omit_esr(topology_b_result):
    netlist = export_topology_b_ngspice_netlist(
        topology_b_result,
        FREQUENCY_HZ,
        Z1,
        Z2,
        include_loss=False,
    )

    assert "RL1_ESR" not in netlist
    assert "L1 split port1" in netlist


def test_write_ngspice_netlist_creates_expected_cir_filename(
    tmp_path,
    topology_b_result,
):
    output_path = tmp_path / "ngspice" / "xphase_40m_topology_b.cir"

    written_path = write_ngspice_netlist(
        output_path,
        topology_b_result,
        FREQUENCY_HZ,
        Z1,
        Z2,
    )

    assert written_path == output_path
    assert output_path.exists()
    assert output_path.name == "xphase_40m_topology_b.cir"
    assert output_path.suffix == ".cir"


def test_write_ngspice_netlist_rejects_non_cir_filename(
    tmp_path,
    topology_b_result,
):
    output_path = tmp_path / "ngspice" / "xphase_40m_topology_b.net"

    with pytest.raises(ValueError, match=r"\.cir"):
        write_ngspice_netlist(
            output_path,
            topology_b_result,
            FREQUENCY_HZ,
            Z1,
            Z2,
        )


def test_parse_ngspice_measurements_parses_complex_and_scalar_values():
    output = """
Noise before the control output.
XPHASE_BEGIN
xphase_vratio = 2.000000000000000e-01,3.000000000000000e-01
xphase_vratio_mag = 3.605551275463989e-01
xphase_vratio_phase_deg = 5.630102354155978e+01
v(input) = (1.000000000000000e+00,-2.000000000000000e+00)
i(l1) = -1.250000000000000e-02,4.000000000000000e-03
XPHASE_END
More ngspice text.
"""

    measurements = parse_ngspice_measurements(output)

    assert measurements["xphase_vratio"] == pytest.approx(0.2 + 0.3j)
    assert measurements["xphase_vratio_mag"] == pytest.approx(0.3605551275463989)
    assert measurements["xphase_vratio_phase_deg"] == pytest.approx(56.30102354155978)
    assert measurements["v(input)"] == pytest.approx(1 - 2j)
    assert measurements["i(l1)"] == pytest.approx(-0.0125 + 0.004j)


def test_find_ngspice_executable_uses_path_lookup():
    with patch("pns.ngspice.shutil.which", return_value="/usr/bin/ngspice"):
        assert find_ngspice_executable() == "/usr/bin/ngspice"


def test_run_ngspice_batch_uses_batch_mode_and_returns_output(tmp_path):
    netlist_path = tmp_path / "test.cir"
    netlist_path.write_text("* test\n.end\n", encoding="utf-8")
    completed = Mock(returncode=0, stdout="stdout text", stderr="stderr text")

    with patch("pns.ngspice.subprocess.run", return_value=completed) as run:
        output = run_ngspice_batch(netlist_path, "/usr/bin/ngspice")

    run.assert_called_once_with(
        ["/usr/bin/ngspice", "-b", str(netlist_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "stdout text" in output
    assert "stderr text" in output


def test_run_ngspice_batch_raises_when_executable_missing(tmp_path):
    with patch("pns.ngspice.find_ngspice_executable", return_value=None):
        with pytest.raises(FileNotFoundError):
            run_ngspice_batch(tmp_path / "test.cir")


def test_run_ngspice_batch_raises_on_nonzero_exit(tmp_path):
    completed = Mock(returncode=1, stdout="bad output", stderr="")

    with patch("pns.ngspice.subprocess.run", return_value=completed):
        with pytest.raises(RuntimeError, match="exit code 1"):
            run_ngspice_batch(tmp_path / "test.cir", "/usr/bin/ngspice")


def test_example_ngspice_filename_ends_in_cir():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "ngspice" / "xphase_40m_topology_b.cir"

    assert path.name == "xphase_40m_topology_b.cir"
    assert path.suffix == ".cir"
