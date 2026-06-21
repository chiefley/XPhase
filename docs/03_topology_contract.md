# Topology Contract

## First Supported Topology Family

The first supported topology family is **Topology A: integrated
low-pass/high-pass branch L networks**.

Topology A uses two branch networks connected in parallel at the source split
node. Each branch both contributes phase shift and participates in the input
impedance transformation seen by the source.

### Circuit

Branch 1 is the low-pass branch:

```text
Split -> series L1 -> Port1 node -> load Z1
Port1 node -> shunt C1 -> return
```

Branch 2 is the high-pass branch:

```text
Split -> series C2 -> Port2 node -> load Z2
Port2 node -> shunt L2 -> return
```

The source sees the two complete branch networks in parallel at `Split`.

The target voltage ratio is:

```text
V(Port2) / V(Port1)
```

where `V(Port1)` and `V(Port2)` are the voltages at the respective port nodes
across loads `Z1` and `Z2`.

### Optimization Targets

The optimizer for Topology A should try to satisfy all of these constraints:

- Target `V(Port2) / V(Port1)` magnitude and phase.
- Target input impedance at `Split`, normally `50 + j0` ohms.
- Component practicality limits.
- Loss and voltage/current stress limits.

The voltage ratio and input match are both primary design objectives. Topology A
must not optimize for SWR alone.

### Integrated Phasing and Matching

Topology A integrates phasing and matching in the same branch components. The
series/shunt components are not only phase-shift elements and are not only input
matching elements; they jointly determine:

- The branch transfer functions from `Split` to each port node.
- The voltage ratio between the two antenna/feedline ports.
- The aggregate input impedance seen at `Split`.
- Component loss and voltage/current stress.

A separate input matching network is allowed only as a later optional extension.
It is not part of Topology A.

## Future Topology Variants

These variants are named for future discussion and testing, but are not part of
the first supported solver implementation.

- **Topology A0: series-only lead/lag branches**. Each branch uses only a series
  reactance element to create a lead/lag relationship before the loads.
- **Topology B: low-pass/high-pass branches plus optional input L-match**. This
  starts with the same integrated branch structure as Topology A, then adds an
  optional source-side L-match at `Split`.
- **Topology C: separate phasing section followed by separate 50-ohm input
  match**. This treats phasing and final source matching as distinct network
  sections rather than one integrated branch-network problem.
