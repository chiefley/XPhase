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
- Treat feedline length variation and bandwidth evaluation as separate concerns:
  - feedline length variation is a center-frequency candidate-generation problem
  - bandwidth evaluation is a frozen-design verification problem
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
- per-component RMS voltage/current stress and Q-loss estimates for reporting and CSV export
- LTspice export
- ngspice export and batch verification
- lossless feedline transformation from NEC feedpoint reference plane to phasing-box reference plane
- fixed-feedline example using NEC feedpoint data for a +Y 40 m test case
- equal-length center-frequency feedline sweep
- differential/offset center-frequency feedline sweep using `port2_length = common_length + offset`
- center-frequency normal, port-1-inverted, and port-2-inverted voltage-reference variants
- Level 1 static/frozen network bandwidth evaluation using fixed center-frequency NEC feedpoint impedances
- tests for core topology, ngspice behavior, feedline transformation, feedline sweeps, and the +Y feedpoint case

Known limitations:

- no full independent feedline length grid yet
- no feedline loss model yet
- no direct NEC parsing
- no first-class target `I2/I1`
- no Level 2 frequency-dependent NEC feedpoint bandwidth evaluation
- no full NEC current/pattern bandwidth verification
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

## Stage 3: feedline-length variation and candidate generation

Goal: search practical physical feedline lengths before solving the phasing network.

This stage is a center-frequency candidate-generation problem. It should answer: for the design frequency, feedpoint impedances, feedline type, and allowed physical lengths, what box-end impedances and network solutions are available?

Keep the candidate generator separate from the network optimizer. Feedline search modes can be clever, but they should all emit concrete candidate pairs:

- port 1 physical feedline length
- port 2 physical feedline length
- transformed port 1 box-end impedance
- transformed port 2 box-end impedance

Search modes to support in stages:

1. Balanced or equal-length sweep
   - vary both feedlines together
   - example: 60/60 ft, 65/65 ft, 70/70 ft
   - useful for finding whether a shared physical length produces more practical network values

2. One-feedline or differential-offset sweep
   - vary one feedline relative to the other
   - example: port 1 fixed at 70 ft while port 2 is 60, 65, 70, 75, 80 ft
   - alternatively use common length plus offset: `port2_length = common_length + offset`
   - current convention: positive offset adds physical coax length to port 2, the forward +Y NEC voltage phase-reference source
   - useful when intentional extra length in one element path reduces component values or stress
   - direction switching may require switching the extra line length along with the network, but XPhase should still evaluate the RF tradeoff

3. Full independent grid sweep
   - vary both feedlines independently
   - example: every port 1 length against every port 2 length
   - useful as a broad search, but can produce many combinations quickly

Implemented polarity variants may be evaluated with the equal-length and offset
search modes. Normal polarity uses the original `V2/V1` target. Inverting port 1
or port 2 reverses that port's voltage/current reference and shifts the target
ratio by 180 degrees without changing the transformed feedpoint impedance.
Both-inverted is equivalent to normal for `V2/V1` and is not emitted separately.

Tasks:

- Add feedline length range inputs for port 1 and port 2.
- Add step-size control for feedline sweep resolution.
- Add explicit search-mode support rather than assuming only a full independent grid.
- For each concrete length pair, transform both feedpoint impedances to the phasing-box end.
- Run the existing topology optimizer against each transformed load pair.
- Return a ranked list of candidates instead of only one result.
- Add pruning rules for obviously bad or duplicate candidates.

Acceptance criteria:

- A case can specify practical feedline ranges, such as 30 to 90 feet for each element.
- XPhase can produce multiple candidate network solutions for different length pairs.
- Results include feedline lengths, transformed impedances, network values, phasing error, SWR, stress, and loss.
- Results identify which search mode produced each candidate.

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

This stage is separate from feedline-length variation. Feedline variation chooses candidate physical lengths and network values at the design frequency. Bandwidth evaluation verifies a selected physical design across frequency.

Important rule: solve the network at the design frequency, then freeze the physical feedline lengths and component values. Re-evaluate that same physical design across the requested frequency range. Do not re-optimize components or feedline lengths at each frequency point when judging a physical design.

Bandwidth evaluation should be staged by confidence level:

1. Level 1: frozen-load network-only bandwidth (implemented)
   - use the design-frequency NEC feedpoint impedances at every frequency point
   - sweep the feedline electrical lengths and L/C reactances with frequency
   - compute SWR, achieved `V2/V1`, component stress, and loss
   - useful as a first screen for obviously narrow or fragile network solutions
   - not a proof of real array pattern bandwidth

2. Level 2: frequency-dependent NEC feedpoint impedance bandwidth (future)
   - use NEC-derived feedpoint impedances at each frequency point
   - better evaluates SWR and network behavior as antenna loads move with frequency
   - still does not fully prove array pattern bandwidth unless the target current behavior is also evaluated consistently

3. Level 3: full NEC current/pattern verification
   - verify the selected physical design against NEC current ratios and/or patterns across frequency
   - this is the real proof for gain, front-to-back ratio, and pattern bandwidth
   - XPhase can screen and report candidates, but NEC remains the authority for antenna physics

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
- Results identify which bandwidth confidence level was used.
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

1. Build a feedline sweep candidate generator that can emit concrete length pairs and transformed box-end impedances.
2. Start with a balanced/equal-length sweep and a small full-grid sweep example.
3. Add an optimizer runner around the sweep that uses the existing Topology B optimizer without changing solver internals.
4. Add result-table reporting that includes search mode, feedline lengths, transformed impedances, network values, SWR, stress, and loss.
5. Add Level 1 frozen-load bandwidth evaluation only after feedline sweep can produce multiple candidates.
6. Add frequency-dependent NEC feedpoint data and Level 2 bandwidth evaluation later.

## Notes for AI-assisted development

Each implementation task should be small and testable. Prefer prompts such as:

- Add a lossless coax impedance transformer and tests for quarter-wave and half-wave cases.
- Extend the case schema to include feedline length ranges, but do not change optimizer behavior yet.
- Add a feedline sweep function that returns transformed load pairs and tests only that transformation grid.
- Add a candidate-ranking dataclass before changing the command-line examples.
- Add frequency-sweep evaluation for an already-solved Topology B candidate.

Avoid prompts that ask for the whole roadmap in one step.
