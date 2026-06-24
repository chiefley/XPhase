# Validation Contract

## Required Test Coverage

Every implementation change should include or update pytest tests. The full
test suite should pass with:

```bash
python3 -m pytest
```

Ordinary pytest runs must not require LTspice or ngspice to be installed.
External simulator execution should be optional or mocked in tests.

## Numerical Anchor

The first numerical anchor is:

```text
cases/40m_inverted_v_90ft_feedlines.json
```

This case is preliminary, but it anchors expected behavior for the current
solver. Tests should continue to verify that it loads, that its target ratio is
interpreted correctly, and that the optimizer returns a finite solution near
the requested `V(port2)/V(port1)` magnitude and phase.

## Solver Validation

Validation should cover:

- case schema loading and rejection of invalid numeric fields
- complex math helpers, including magnitude/phase conversion and phase wrapping
- Topology A network evaluation
- Topology B input L-match behavior
- optimizer behavior against the shipped 40m case
- stress/loss estimate scaling with requested power and Q
- LTspice netlist generation
- ngspice parser, netlist generation, and mocked batch runner

## Manual and Optional Verification

The LTspice export path is intended for manual circuit inspection:

```bash
python3 examples/optimize_40m_topology_b.py --write-ltspice
```

The optional ngspice path provides automated external simulator verification
when ngspice is installed:

```bash
python3 examples/verify_40m_with_ngspice.py
```

The ngspice example should exit gracefully with an installation hint if ngspice
is not available.

## Known Validation Limits

The current validation does not prove coax-length search behavior because that
feature is not implemented yet.

The ngspice verification example compares the ideal exported netlist against
the ideal XPhase Topology B result. It does not validate the post-solve lossy
stress estimate as a separate circuit model.
