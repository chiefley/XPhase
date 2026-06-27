# XPhase / Phased Network Synthesizer

XPhase is a Python tool for designing practical phasing and matching systems for two-element amateur-radio HF antenna arrays.

The long-term workflow is:

1. Use an NEC-based antenna modeling tool, such as 4NEC2, AutoEZ, or another NEC front end, to optimize the physical array for the desired pattern objective: gain, front-to-back ratio, elevation angle, or other operating goal.
2. Give XPhase the resulting NEC-derived two-port feedpoint information and the desired element excitation ratio.
3. Specify the physically practical feedline length ranges for the installation, along with coax impedance, velocity factor, loss assumptions, and whether each element feedline path is normal or intentionally inverted.
4. Let XPhase sweep candidate feedline-length and feedline-polarity combinations, transform the feedpoint impedances through those feedlines, synthesize matching/phasing networks, and rank the resulting designs by RF correctness and practical buildability.

The first target case is a 40-meter two-element phased inverted-V array. Antenna modeling is currently done externally in NEC/4NEC2/AutoEZ. The present code takes fixed NEC-derived complex port/feedline impedances and a desired port voltage ratio, then searches lumped-component network topologies.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the staged development plan.

## Current implemented scope

- two complex antenna/feedline port loads
- target `V2/V1` magnitude and phase
- target 50-ohm input impedance
- fixed Topology A and Topology B network search
- Topology B input L-match synthesis
- additive lossless feedpoint-to-box-end coax transformation layer
- equal-length feedline sweep at the design frequency
- differential/offset feedline sweep at the design frequency
- normal, port-1-inverted, and port-2-inverted voltage-reference variants
- post-solve per-component RMS voltage/current estimates
- per-component and total estimated loss using component Q
- LTspice netlist export
- optional ngspice batch verification

## Current limitations

- general coax length ranges are not searched yet
- full independent feedline length grids are not searched yet
- case files still provide fixed complex port/feedline impedances
- target element current ratio is not yet a first-class input
- bandwidth scoring is not implemented yet
- NEC output parsing is not implemented yet
- component voltage/current/loss are reported after optimization, not used as primary optimization objectives yet
- practical part series and discrete component selections are not modeled yet

## Out of scope for the current version

- GUI
- automatic antenna geometry optimization
- relay control or hardware design

NEC parsing is a desired future feature, but XPhase should not attempt to replace NEC antenna modeling. NEC remains the antenna-physics engine; XPhase is the feed-system synthesis, verification, and practicality-ranking engine.

## Examples

Run the shipped 40-meter Topology B example:

```bash
python3 examples/optimize_40m_topology_b.py
```

Demonstrate the additive lossless feedpoint-to-box-end transform layer without
running the optimizer:

```bash
python3 examples/transform_40m_feedpoints.py
```

Compare equal-length and offset feedline sweeps by mathematical and practical
center-frequency metrics:

```bash
python3 examples/compare_40m_feedline_sweeps.py
```

Write the same combined sweep comparison data to CSV:

```bash
python3 examples/compare_40m_feedline_sweeps.py --write-csv
```

Compare normal and single-port-inverted voltage-reference variants:

```bash
python3 examples/compare_40m_feedline_sweeps.py --include-polarity-variants
```

Write all physical and polarity candidates to CSV:

```bash
python3 examples/compare_40m_feedline_sweeps.py --include-polarity-variants --write-csv
```

Show the per-component RMS voltage, current, and estimated loss for displayed
candidates:

```bash
python3 examples/compare_40m_feedline_sweeps.py --limit 3 --show-component-stress
```

CSV exports include these per-component stress fields automatically.

Polarity inversion does not change the feedpoint impedance transform. Inverting
either port changes the optimizer target `V2/V1` ratio by 180 degrees.

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

and compares ngspice's simulated `V(port2)/V(port1)` against XPhase's computed ideal Topology B result.
