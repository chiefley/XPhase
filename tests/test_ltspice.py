from pathlib import Path

import pytest

from pns.ltspice import (
    export_topology_b_ltspice_netlist,
    write_topology_b_ltspice_netlist,
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


def test_exported_netlist_contains_key_node_names(topology_b_result):
    netlist = export_topology_b_ltspice_netlist(
        topology_b_result,
        FREQUENCY_HZ,
        Z1,
        Z2,
    )

    assert " input" in netlist
    assert " split" in netlist
    assert " port1" in netlist
    assert " port2" in netlist


def test_exported_netlist_contains_expected_component_names(topology_b_result):
    netlist = export_topology_b_ltspice_netlist(
        topology_b_result,
        FREQUENCY_HZ,
        Z1,
        Z2,
    )

    for component_name in (
        "Vsrc",
        "Rsrc",
        "Cm_series",
        "Lm_shunt",
        "L1",
        "C1",
        "C2",
        "L2",
        "Rload1",
        "Rload2",
    ):
        assert component_name in netlist


def test_exported_netlist_contains_ac_command(topology_b_result):
    netlist = export_topology_b_ltspice_netlist(
        topology_b_result,
        FREQUENCY_HZ,
        Z1,
        Z2,
    )

    assert ".ac dec 101" in netlist


def test_exported_netlist_contains_complex_load_representations(topology_b_result):
    netlist = export_topology_b_ltspice_netlist(
        topology_b_result,
        FREQUENCY_HZ,
        Z1,
        Z2,
    )

    assert "Rload1 port1 load1_x" in netlist
    assert "Cload1 load1_x 0" in netlist
    assert "Rload2 port2 load2_x" in netlist
    assert "Lload2 load2_x 0" in netlist


def test_write_topology_b_ltspice_netlist_creates_file(tmp_path, topology_b_result):
    output_path = tmp_path / "xphase_40m_topology_b.cir"

    written_path = write_topology_b_ltspice_netlist(
        output_path,
        topology_b_result,
        FREQUENCY_HZ,
        Z1,
        Z2,
    )

    assert written_path == output_path
    assert Path(output_path).exists()
    assert "Vsrc" in output_path.read_text(encoding="utf-8")
