# Math Contract

## Phasor Convention

All RF quantities are represented as complex phasors at one operating
frequency. Impedances use ohms, inductance uses henries, capacitance uses
farads, and frequency uses hertz.

The current target ratio is a port voltage ratio:

```text
V(port2) / V(port1)
```

where the port voltages are measured at the antenna/feedline load nodes in the
network. For Topology B, this ratio is still measured at the two port nodes, not
at the source-side input node and not across the input matching section.

## Component Impedance

Ideal lumped components are evaluated as:

```text
Z_L = j * 2*pi*f*L
Z_C = 1 / (j * 2*pi*f*C)
```

Parallel impedances use:

```text
Z_parallel = 1 / (1/Z_a + 1/Z_b)
```

## Objective Scoring

The optimizer scores voltage-ratio error using:

- magnitude error in dB
- phase error in degrees, wrapped to `[-180, +180]`

For Topology A, the default objective also includes input resistance and input
reactance error at the split node.

For Topology B, the branch network is searched for the target ratio and an
ideal input L-match is synthesized afterward for the requested real source
resistance. The default Topology B objective sets input impedance error weights
to zero because the L-match handles the input transformation.

The solver must not optimize for SWR alone. SWR is reported and tested, but the
voltage-ratio target remains a primary design requirement.

## Stress and Loss Estimates

Stress reporting scales the ideal network solution to the case `power_watts`.
It estimates per-component RMS voltage, RMS current, ESR, and loss from the
component reactance and assumed Q:

```text
ESR = abs(X_component) / Q
P_loss = I_rms^2 * ESR
```

These values are currently post-solve estimates. They are not yet included in
the optimizer objective.

## SPICE Verification

LTspice export and ngspice verification use plain `.cir` netlists with an
independent AC source and a 50-ohm source resistor. The source amplitude is the
Thevenin RMS voltage that would deliver the requested power into a matched
load:

```text
V_source = 2 * sqrt(P * Z0)
```

The ngspice verification example compares the simulated ideal
`V(port2)/V(port1)` result against XPhase's computed ideal Topology B result.
