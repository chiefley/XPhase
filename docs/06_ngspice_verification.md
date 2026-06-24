# ngspice Verification

XPhase can export SPICE netlists for manual LTspice inspection and for
automated ngspice verification. ngspice is useful here because it has a
command-line batch mode that can be run from tests, examples, and CI-like
scripts without opening an interactive schematic or waveform viewer.

## LTspice Export vs ngspice Verification

The LTspice export remains a plain `.cir` file intended for manual inspection
in LTspice. It is useful for plotting node voltages, checking component stress,
and reviewing the network interactively.

The ngspice path is separate. It writes a plain `.cir` file with the same
Topology B structure, runs a single-frequency AC analysis in batch mode, prints
machine-readable quantities, and compares those quantities against XPhase's
computed result. ngspice is optional; ordinary pytest runs use mocked
subprocess calls and do not require ngspice to be installed.

## Install on Ubuntu or WSL

```bash
sudo apt update
sudo apt install ngspice
```

Check that it is available:

```bash
ngspice --version
```

## Run the 40m Verification Example

From the repository root:

```bash
python3 examples/verify_40m_with_ngspice.py
```

The example loads `cases/40m_inverted_v_90ft_feedlines.json`, runs the existing
Topology B optimizer, writes:

```text
ngspice/xphase_40m_topology_b.cir
```

and then runs ngspice in batch mode if `ngspice` is on `PATH`. If ngspice is
not installed, the example prints:

```text
ngspice not found. Install with: sudo apt install ngspice
```

and exits without a traceback.

## Checked Quantities

The ngspice netlist uses:

- an independent AC source
- a 50-ohm source resistor
- the optimized input matching section
- the Topology A branch components
- complex port loads represented as resistance plus series inductance or
  capacitance
- optional ESR components when `include_loss=True`
- exact single-frequency AC analysis:

```spice
.ac lin 1 <frequency_hz> <frequency_hz>
```

The control block prints:

- complex `V(port2)/V(port1)`
- magnitude of `V(port2)/V(port1)`
- phase of `V(port2)/V(port1)` in degrees
- complex `V(input)`
- currents through the input series element, `L1`, `C2`, and `L2`

The 40m verification example writes an ideal netlist with `include_loss=False`
so the simulated `V(port2)/V(port1)` is compared directly against XPhase's
current ideal Topology B result.
