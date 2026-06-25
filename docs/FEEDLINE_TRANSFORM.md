# Feedline Reference-Plane Transform

XPhase now has an additive lossless feedline transformation layer. This layer
does not replace or modify the existing topology solvers. It prepares the
box-end impedances that those solvers already consume.

## Reference Planes

The **NEC feedpoint reference plane** is the impedance at the antenna element
feedpoint in the antenna model. This is the impedance before any physical coax
feedline between the antenna and the phasing box.

The **phasing-box reference plane** is the impedance seen by the phasing and
matching network at the box end of the feedline. This is the impedance that the
existing Topology A and Topology B solvers operate on.

For a physical array, these two reference planes are usually not the same. A
coax line transforms the antenna feedpoint impedance according to its
characteristic impedance, velocity factor, physical length, and eventually loss
and polarity conventions.

## Why Solvers Use Box-End Impedances

The topology solvers are network solvers for the phasing box. Their job is to
find lumped L/C values that create the desired port voltage ratio and source
input match for the impedances presented at the box terminals.

Keeping the topology solvers focused on box-end impedances avoids mixing
feedline modeling with phasing-network math. Feedline transformations can be
done before calling the existing solvers:

```text
NEC feedpoint impedance -> feedline transform -> box-end impedance -> topology solver
```

This keeps the existing Topology A and Topology B calculations stable while
allowing future case files to start from antenna feedpoint impedances.

## Lossless Transform

The current feedline model is lossless coax with:

- real characteristic impedance `Z0`
- velocity factor
- physical length

The implemented impedance transform is:

```text
Zin = Z0 * (ZL + j * Z0 * tan(beta * l)) /
           (Z0 + j * ZL * tan(beta * l))
```

where:

```text
ZL   = antenna feedpoint/load impedance
Zin  = box-end impedance
Z0   = coax characteristic impedance
l    = physical line length
beta = 2*pi / wavelength_on_line
```

and:

```text
wavelength_on_line = c * velocity_factor / frequency_hz
```

## Current API

The current helper module is:

```text
src/pns/feedline.py
```

It provides:

- `LosslessCoaxLine`
- `feet_to_meters()`
- `meters()`
- `transform_lossless_feedline_impedance()`
- `transform_feedpoint_to_box_end()`
- `transform_two_feedpoints_to_box_end()`

## Current Limits

Feedline loss is not implemented yet.

Feedline polarity or intentional inversion is not implemented yet, although the
layer is separate enough to add it later.

Feedline length sweep is not implemented yet. The current helpers transform
specific physical lengths supplied by the caller.

The case schema is not changed yet. Existing case files still provide fixed
port impedances directly to the topology solvers.
