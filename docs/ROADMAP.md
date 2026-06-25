# XPhase staged roadmap

This document captures the intended direction for XPhase and breaks the work into small development stages.

XPhase should remain focused on feed-system synthesis for two-element HF arrays. NEC-based tools remain responsible for antenna geometry and pattern optimization. XPhase consumes the resulting two-port feedpoint data, explores practical feedline and network choices, verifies the resulting RF behavior, and ranks candidate solutions for construction.

## Ultimate workflow

1. Build and optimize the antenna array in an NEC-based tool such as 4NEC2 or AutoEZ.
2. Select the desired operating objective: gain, front-to-back ratio, elevation angle, RDF, or another pattern metric.
3. Capture the resulting two-feedpoint data and the desired element excitation ratio.
4. Enter installation constraints:
   - practical feedline length range for each element
   - coax characteristic impedance
   - coax velocity factor
   - coax loss assumptions
   - operating frequency or frequency range
   - target system impedance, normally 50 ohms
   - transmitter power
   - component Q and rating assumptions
5. XPhase sweeps practical feedline-length combinations.
6. For each feedline pair, XPhase transforms the NEC feedpoint impedances through the selected coax lengths.
7. XPhase tries applicable phasing and matching network topologies.
8. XPhase verifies the solved network analytically and, where possible, by ngspice.
9. XPhase ranks the candidate designs by correctness, bandwidth, stress, loss, and buildability.
10. The user chooses a small number of practical designs to build or refine.

## Design principles

- NEC models the antenna. XPhase models the feed system.
- Prefer element current ratio as the user-facing phasing target, because the array pattern is driven by element currents.
- Keep voltage ratio support because the current implementation uses `V2/V1`, and voltage ratios are useful for internal network calculations.
- Treat single-frequency optimization as only the first pass.
- Freeze solved component values when evaluating bandwidth. Do not re-optimize components at each frequency point when judging a physical design.
- Prefer practical, buildable solutions over mathematically exact but fragile or high-stress solutions.
- Use ngspice as an independent verification path for solved networks.
- Keep development incremental, with tests for each new RF calculation.

## Stage 0: current prototype

Implemented now:

- fixed two-port complex load cases
- target `V2/V1` magnitude and phase
- Topology A branch-network evaluator
- Topology A optimizer
- Topology B evaluator with input L-match
- Topology B optimizer
- component stress and Q-loss estimates
- LTspice export
- ngspice export and batch verification
- tests for core topology and ngspice behavior

Known limitations:

- fixed port/feedline impedances only
- no feedline-length sweep
- no coax model abstraction
- no direct NEC parsing
- no first-class target `I2/I1`
- no frequency sweep or bandwidth score
- no practical part-series selection

## Stage 1: clarify case schema and target conventions

Goal: make the input case format ready for future feedline and bandwidth work without breaking the current example.

Tasks:

- Document the current JSON case schema.
- Add explicit target type metadata, such as `voltage_ratio_v2_over_v1` versus `current_ratio_i2_over_i1`.
- Add frequency-range fields while preserving the existing single-frequency field.
- Add power, component-Q, and rating assumptions in a stable location.
- Add tests that load and validate representative case files.

Acceptance criteria:

- Current 40 m example still runs.
- Existing tests still pass.
- Case files clearly indicate whether the target is voltage ratio or current ratio.

## Stage 2: feedline modeling

Goal: add a tested coax/feedline impedance transformer.

Tasks:

- Add a coax model with characteristic impedance, velocity factor, and optional loss.
- Implement complex impedance transformation through a line of given physical length.
- Support length units such as feet and meters at the case/config boundary.
- Add tests for known quarter-wave, half-wave, and arbitrary-length transformations.
- Keep the first implementation lossless if necessary, then add loss after the lossless math is trusted.

Acceptance criteria:

- Given a load impedance, frequency, coax `Z0`, velocity factor, and length, XPhase returns the transformed impedance at the network end.
- Unit tests cover important transmission-line edge cases.

## Stage 3: feedline-length sweep

Goal: search practical physical feedline lengths before solving the phasing network.

Tasks:

- Add feedline length range inputs for port 1 and port 2.
- Add step-size control for feedline sweep resolution.
- For each length pair, transform both feedpoint impedances to the phasing-box end.
- Run the existing topology optimizer against each transformed load pair.
- Return a ranked list of candidates instead of only one result.
- Add pruning rules for obviously bad or duplicate candidates.

Acceptance criteria:

- A case can specify practical feedline ranges, such as 30 to 90 feet for each element.
- XPhase can produce multiple candidate network solutions for different length pairs.
- Results include feedline lengths, transformed impedances, network values, phasing error, SWR, stress, and loss.

## Stage 4: current-ratio targets

Goal: make target element current ratio a first-class design input.

Tasks:

- Add `I2/I1` target support to the case schema.
- Decide and document current direction/sign convention at the antenna ports.
- Compute achieved element current ratio from solved network port voltages and port impedances.
- Add objective scoring for current-ratio magnitude and phase errors.
- Preserve voltage-ratio support for compatibility and internal checks.

Acceptance criteria:

- A case can request a target current ratio directly.
- XPhase reports both achieved current ratio and voltage ratio.
- Tests verify sign conventions and ratio calculations.

## Stage 5: bandwidth evaluation

Goal: evaluate each physical candidate across a frequency range.

Important rule: solve the network at the design frequency, then freeze the physical feedline lengths and component values. Re-evaluate that same physical design across the requested frequency range.

Metrics to compute across the sweep:

- achieved `I2/I1` or `V2/V1`
- magnitude error versus target
- phase error versus target
- input impedance
- SWR
- component RMS voltage
- component RMS current
- component loss
- feedline loss, when modeled
- estimated efficiency

Candidate bandwidth summary:

- worst phase error over range
- worst magnitude error over range
- worst SWR over range
- worst component voltage/current over range
- worst and average estimated efficiency
- usable bandwidth for configured thresholds

Acceptance criteria:

- A candidate has center-frequency results and swept-frequency results.
- Results distinguish phasing bandwidth from SWR bandwidth.
- Ranking can prefer a slightly imperfect but broadband solution over a perfect narrowband solution.

## Stage 6: practicality scoring

Goal: rank solutions by buildability, not just mathematical accuracy.

Scoring factors:

- phasing accuracy at center frequency
- phasing bandwidth
- SWR bandwidth
- estimated network loss
- feedline loss
- component voltage stress
- component current stress
- component value reasonableness
- proximity to optimizer bounds
- number of components
- sensitivity to small component or feedline-length errors

Practicality warnings:

- extremely small capacitors
- very large inductors
- high circulating current
- high capacitor voltage
- high loss in a coil or capacitor
- narrow frequency sensitivity
- feedline length requiring unrealistic physical routing

Acceptance criteria:

- Candidate reports include human-readable warnings.
- Ranking can be tuned by objective weights.
- The best result is not merely the lowest mathematical error if another result is much more buildable.

## Stage 7: NEC import path

Goal: reduce manual copying from 4NEC2/AutoEZ while keeping the first parser modest.

Possible staged approach:

1. Document the manual values required from NEC.
2. Add a simple CSV/table import format that can be copied from 4NEC2 or AutoEZ.
3. Add a parser for one known NEC output format.
4. Add tests using small fixture files.

Acceptance criteria:

- The manual JSON workflow remains available.
- A user can import or paste NEC-derived port data with fewer chances for transcription error.
- Parser behavior is covered by tests and fails clearly when the format is not recognized.

## Stage 8: reporting and artifacts

Goal: produce reports useful at the bench and in the shack.

Possible outputs:

- console summary table
- JSON result file
- CSV candidate table
- ngspice netlist for selected candidates
- LTspice netlist for selected candidates
- plots of SWR, phase error, magnitude error, loss, and component stress versus frequency
- build sheet with component values, ratings, and warnings

Acceptance criteria:

- The user can compare the top candidates without reading raw optimizer output.
- Selected candidates can be exported for SPICE verification and practical construction review.

## Near-term recommended next tasks

1. Add this roadmap and keep the README concise.
2. Document the current case schema.
3. Add a lossless feedline transformer with tests.
4. Add feedline range fields to a new example case, without changing the existing optimizer yet.
5. Build a feedline sweep driver that runs the existing Topology B optimizer over transformed load pairs.
6. Add bandwidth evaluation after the feedline sweep can produce multiple candidates.

## Notes for AI-assisted development

Each implementation task should be small and testable. Prefer prompts such as:

- Add a lossless coax impedance transformer and tests for quarter-wave and half-wave cases.
- Extend the case schema to include feedline length ranges, but do not change optimizer behavior yet.
- Add a feedline sweep function that returns transformed load pairs and tests only that transformation grid.
- Add a candidate-ranking dataclass before changing the command-line examples.
- Add frequency-sweep evaluation for an already-solved Topology B candidate.

Avoid prompts that ask for the whole roadmap in one step.
