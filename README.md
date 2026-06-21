# Phased Network Synthesizer

A small Python tool for synthesizing lumped L/C phasing and matching networks for coupled amateur-radio antenna arrays.

The first target case is a 40-meter two-element phased inverted-V array. Antenna modeling is done externally in NEC/4NEC2/AutoEZ. This program takes NEC-derived complex port impedances and a desired port voltage or current ratio, then searches practical lumped-component network topologies.

Initial scope:
- two complex antenna/feedline port loads
- target V2/V1 magnitude and phase
- target 50-ohm input impedance
- fixed topology search
- component voltage/current estimates
- estimated loss using component Q
- LTspice netlist export

Out of scope for the first version:
- GUI
- direct NEC file parsing
- automatic antenna geometry optimization
- relay control or hardware design
