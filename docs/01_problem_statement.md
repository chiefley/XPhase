# Problem Statement

XPhase is a small numerical RF engineering tool for synthesizing phasing and
matching networks for a two-element antenna array.

The long-term goal is to compute useful design options that include:

- coax/feedline lengths inside ranges requested by case files
- lumped network component values
- the desired voltage or current ratio between the two antenna ports
- a good source input match, normally near `50 + j0` ohms
- practical component values
- low working voltage and current stress
- reasonable estimated component loss

## Current Implemented Problem

The current implementation solves a narrower problem. It assumes antenna and
feedline modeling has already been done externally, and that the case file
already contains the resulting complex port impedances:

```text
Z1 = ports.port1.z_ohms.r + j * ports.port1.z_ohms.x
Z2 = ports.port2.z_ohms.r + j * ports.port2.z_ohms.x
```

Given those fixed impedances, XPhase searches lumped L/C network values for the
target `V(port2)/V(port1)` magnitude and phase. Topology B then adds an ideal
input L-match to transform the split impedance to the requested real source
resistance.

The shipped validation case is:

```text
cases/40m_inverted_v_90ft_feedlines.json
```

It is a preliminary 40-meter two-element inverted-V case. Its notes explicitly
state that the NEC/feedline model may be replaced, so it should be treated as a
numerical anchor rather than a final antenna design.

## Not Implemented Yet

The current case schema and optimizer do not yet search coax lengths. They do
not model requested coax length ranges, velocity factor, loss, characteristic
impedance, or discrete feedline choices.

The current optimizer also does not yet optimize directly for component stress,
loss, or practical preferred-value series. Stress and loss are estimated after a
solution is found.
