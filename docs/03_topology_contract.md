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

## Supported Topology B Family

The second supported topology family is **Topology B: Topology A branch
networks plus an input matching L-network**.

Topology B keeps the Topology A branch section intact and adds an input matching
section before the split node:

```text
50-ohm source -> input matching L-network -> Split node -> Topology A branch networks
```

### Branch Section

The branch section remains the same low-pass/high-pass pair used by Topology A.

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

The Split impedance is the impedance presented by these two complete phasing
branches in parallel before input matching.

### Input Matching Section

Topology B supports two input match families. Each family may be realized in
either mathematical orientation depending on which ideal L-match solution is
valid for the Split impedance:

- `series-then-shunt`: source/input node -> series element -> Split, with the
  shunt element at `Split`.
- `shunt-then-series`: shunt element at the source/input node, then a series
  element from source/input node to `Split`.

**B-LP** uses a low-pass input L-network:

```text
Source/input node -> series Lm -> Split
Split -> shunt Cm -> return
```

or, when the valid solution is shunt-then-series:

```text
Source/input node -> shunt Cm -> return
Source/input node -> series Lm -> Split
```

**B-HP** uses a high-pass input L-network:

```text
Source/input node -> series Cm -> Split
Split -> shunt Lm -> return
```

or, when the valid solution is shunt-then-series:

```text
Source/input node -> shunt Lm -> return
Source/input node -> series Cm -> Split
```

The input impedance target is measured looking into the source-side input of the
matching section, not looking directly into `Split`.

Generated reports and LTspice exports should label both the family and the
actual orientation returned by the matcher, for example `B-LP,
shunt-then-series`.

### Topology B Targets

The measured phasing target remains:

```text
V(Port2) / V(Port1)
```

This ratio is measured at the antenna/feedline port nodes. It is not measured at
the source-side input node and should not use the input matching section voltage
as either numerator or denominator.

Topology B currently allows the optimizer to:

- Prioritize branch phasing at `Split`.
- Transform the Split impedance to `50 + j0` at the input.
- Evaluate loss and component stress for both branch and input matching parts
  after solving.

The current implementation does not yet optimize directly for loss or
voltage/current stress. Those quantities are reported after the network is
found.

## Future Topology Variants

These variants are named for future discussion and testing, but are not part of
the first supported solver implementation.

- **Topology A0: series-only lead/lag branches**. Each branch uses only a series
  reactance element to create a lead/lag relationship before the loads.
- **Topology C: separate phasing section followed by separate 50-ohm input
  match**. This treats phasing and final source matching as distinct network
  sections rather than one integrated branch-network problem.
