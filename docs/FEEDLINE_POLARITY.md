# Feedline polarity choices

XPhase should treat feedline polarity as part of the evaluation matrix for two-element arrays.

For each element feed path, the user may allow one or more polarity choices:

- normal polarity
- reversed polarity, equivalent to a 180-degree sign change in that element's excitation convention

This is separate from the physical feedline length and from the scalar impedance transformation through the coax. A polarity reversal does not change the magnitude of the load impedance seen through a given feedline length. Instead, it changes the phase reference for the element voltage/current used when comparing the achieved excitation ratio against the NEC-derived target.

## Why this matters

Some practical installations may make a normal feed connection easier. Other cases may be easier to build if one element feed is deliberately reversed. A 180-degree polarity choice can turn an awkward phasing-network solution into a more practical one with better component values, lower stress, lower loss, or wider usable bandwidth.

Therefore, the feed-system search should eventually include these combinations:

```text
port1: normal, port2: normal
port1: normal, port2: reversed
port1: reversed, port2: normal
port1: reversed, port2: reversed
```

One polarity can be treated as the reference, so some combinations may be equivalent after the target ratio is normalized. Even so, the configuration should be explicit in reports so the user knows how the selected candidate must be wired.

## Implementation guidance

Feedline polarity should be represented explicitly in the candidate model and result report.

Recommended staged work:

1. Add case-schema fields for allowed polarity choices per port.
2. Add a candidate field such as `port1_polarity` and `port2_polarity`.
3. Add tests showing that a reversed feed changes the reported excitation ratio by 180 degrees relative to normal feed.
4. Include polarity choices in feedline-sweep result tables.
5. Include polarity choice in ngspice/LTspice export comments and build sheets.

## Reporting guidance

A candidate summary should say something like:

```text
Feedline 1: 63.0 ft RG-213, normal polarity
Feedline 2: 71.5 ft RG-213, reversed polarity
```

The report should make the polarity requirement hard to miss, because it is an easy wiring detail to get wrong in the field.
