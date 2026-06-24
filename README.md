# Phased Network Synthesizer

A small Python tool for synthesizing lumped L/C phasing and matching networks for coupled amateur-radio antenna arrays.

The first target case is a 40-meter two-element phased inverted-V array. Antenna modeling is done externally in NEC/4NEC2/AutoEZ. This program takes NEC-derived complex port impedances and a desired port voltage or current ratio, then searches practical lumped-component network topologies.

Current implemented scope:
- two complex antenna/feedline port loads
- target V2/V1 magnitude and phase
- target 50-ohm input impedance
- fixed Topology A and Topology B network search
- Topology B input L-match synthesis
- post-solve component voltage/current estimates
- estimated loss using component Q
- LTspice netlist export
- optional ngspice batch verification

Current limitations:
- coax length ranges are not searched yet
- case files provide fixed complex port/feedline impedances
- component voltage/current/loss are reported after optimization, not used as
  primary optimization objectives yet
- practical part series and discrete component selections are not modeled yet

Out of scope for the current version:
- GUI
- direct NEC file parsing
- automatic antenna geometry optimization
- relay control or hardware design

## Examples

Run the shipped 40-meter Topology B example:

```bash
python3 examples/optimize_40m_topology_b.py
```

Write the LTspice netlist:

```bash
python3 examples/optimize_40m_topology_b.py --write-ltspice
```

This creates:

```text
ltspice/xphase_40m_topology_b.cir
```

Run optional ngspice verification, if ngspice is installed:

```bash
python3 examples/verify_40m_with_ngspice.py
```

This creates:

```text
ngspice/xphase_40m_topology_b.cir
```

and compares ngspice's simulated `V(port2)/V(port1)` against XPhase's computed
ideal Topology B result.
