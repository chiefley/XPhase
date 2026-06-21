# I/O Contract

## Case JSON Schema

Case files describe one externally modeled antenna/feedline case and the
electrical target the synthesizer should match. The current format is a single
JSON object with these required fields.

### Top-Level Fields

- `name`: String identifier for the case.
- `description`: String description of the case source and purpose.
- `frequency_hz`: Positive numeric operating frequency in hertz.
- `ports`: Object containing exactly the modeled port load definitions used by
  the first solver target.
- `target`: Object containing the desired port ratio and source input match.
- `power_watts`: Positive numeric source power used for later component stress
  estimates.
- `component_assumptions`: Object containing positive component Q assumptions.
- `notes`: Array of strings with caveats or provenance notes.

### Port Fields

The first version requires two ports:

- `ports.port1.z_ohms.r`: Numeric resistance for port 1, in ohms.
- `ports.port1.z_ohms.x`: Numeric reactance for port 1, in ohms.
- `ports.port2.z_ohms.r`: Numeric resistance for port 2, in ohms.
- `ports.port2.z_ohms.x`: Numeric reactance for port 2, in ohms.

Port impedances are interpreted as complex values:

- `Z1 = ports.port1.z_ohms.r + j * ports.port1.z_ohms.x`
- `Z2 = ports.port2.z_ohms.r + j * ports.port2.z_ohms.x`

### Target Fields

- `target.voltage_ratio_v2_over_v1.magnitude`: Positive numeric magnitude of
  the desired port voltage ratio.
- `target.voltage_ratio_v2_over_v1.phase_deg`: Numeric phase angle of the
  desired port voltage ratio, in degrees.
- `target.input_impedance_ohms.r`: Numeric target input resistance, in ohms.
- `target.input_impedance_ohms.x`: Numeric target input reactance, in ohms.

The target input impedance is interpreted as:

- `Zin_target = target.input_impedance_ohms.r + j * target.input_impedance_ohms.x`

### Component Assumption Fields

- `component_assumptions.inductor_q`: Positive numeric unloaded inductor Q.
- `component_assumptions.capacitor_q`: Positive numeric capacitor Q.

### Validation Rules

Validation must reject:

- Missing required fields.
- Nonnumeric impedance, frequency, target, power, or Q values.
- `frequency_hz <= 0`.
- `power_watts <= 0`.
- `target.voltage_ratio_v2_over_v1.magnitude <= 0`.
- `component_assumptions.inductor_q <= 0`.
- `component_assumptions.capacitor_q <= 0`.
