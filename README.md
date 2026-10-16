# Surface Ropes 0.12.0 — Blender 4.4

Draw single braided ropes across a mesh, create over/under junctions and overhand
knots, and compress the underlying surface. Each rope has independent controls.

[Download the add-on ZIP](https://github.com/Shallowhumour86/Ropes/raw/refs/heads/main/dist/surface-ropes-0.12.0.zip)

## This release

Doubled ropes and the figure-eight/legacy knot styles have been removed. There is
one overhand template and three ways to place it:

1. **On a line:** the existing heart-shaped overhand, with two hemispheres, their
   crossing, and the central eye.
2. **At a self-crossing:** the upper part of the rope ties that same overhand;
   the lower part passes straight through its expanded eye.
3. **At a crossing between ropes:** the clicked rope ties that same overhand;
   the passive rope passes straight through the expanded eye.

Junction knots start with the line-knot mathematics. A smooth radial expansion
opens the eye to fit the sum of the two rope radii. The outer hemispheres grow
less than the eye. The template's crossing order and axial depth are retained.
Long cubic leads meet the body tangentially. Surface placement translates both
components together; the previous junction knot construction, local collision
relaxation and attachment shear have been removed.

[Three cases as ropes](dist/surface-ropes-0.12.0-overhands.png) ·
[Their centre curves](dist/surface-ropes-0.12.0-curves.png) ·
[Open the review scene in Blender](https://github.com/Shallowhumour86/Ropes/raw/refs/heads/main/dist/surface-ropes-0.12.0-review.blend)

## Install and update

1. Save a copy of your scene, then disable the previous Surface Ropes add-on.
2. In Blender 4.4, open **Edit → Preferences → Add-ons → Install from Disk**.
3. Select the ZIP and enable **Surface Ropes**.
4. Open **3D View → Sidebar → Ropes**. Use **Rebuild Ropes** after updating.

Older scenes convert to single ropes and overhand knots when loaded or enabled.
Their waypoints, rope identities, widths and knot stations are retained. Previous
release ZIPs remain in `dist` if you need to reopen the earlier configuration.
No external Python installation or downloaded mesh assets are needed in Blender.

## Inspect the underlying curves

The **Display** control at the top of the Ropes panel has three modes:

- **Rope:** show the braided strands.
- **Centre Curves:** hide the strands and show thin black centre curves.
- **Rope + Curves:** overlay the centre curves in the viewport.

Select a rope in Centre Curves mode and press **Tab** to inspect its Bézier data.
The generated curves use vector handles so they match the sampled centreline
exactly; automatic handle smoothing would otherwise change the shape being
reviewed. Junction eyes use denser sampling to keep the expanded curves smooth,
including at oblique crossings. Rebuild regenerates these curves from the
waypoints, so this is an inspection view rather than a saved manual-edit workflow.
The review `.blend` opens in Centre Curves mode with all three cases side by side.

## Draw and edit

Choose a mesh using **Use Selected Surface**, then **Draw New Rope**. Click on the
surface to place waypoints. Use **Extend / Edit Ropes** to continue an existing
rope. The active rope's controls are shown in its own box; **New Rope Defaults**
only affects ropes created afterward.

During placement:

- **LMB:** add a point.
- **N:** start another rope on the same surface.
- **RMB on a rope:** toggle an overhand at that point or junction.
- **W:** show or hide waypoint markers.
- **T:** switch the new point between Normal and Spanning.
- **Ctrl+Z / Backspace:** undo; **Ctrl+Shift+Z:** redo.
- **Enter / Esc:** finish placement.

Enable **Waypoint Mode** to place a draft first, then use **Generate Rope**.
**Edit Waypoint Draft** returns a generated rope to its editable plan. You can
select a waypoint in the panel, change its type, or move its marker and rebuild.
Waypoint size and X-Ray controls affect marker visibility, not rope thickness.
Selecting a fibre helper and using **Use Selected Rope** selects its owning rope.

## Knots and junctions

Right-click away from a crossing to toggle a knot on a line. At a crossing between
ropes, the clicked rope becomes the tying rope. At a self-crossing, the upper
passage ties around the lower passage. The passive core stays straight through
the eye. **Swap Over / Under** changes an ordinary junction's crossing order.
**Knot Size** scales the shared overhand; its minimum is 1. A junction eye opens
further when the passive rope is wider, without changing the knot into another
shape. Closely spaced knots share the available lead distance between stations.

Ordinary crossings retain the strand-based contact calculation: the actual braid
surfaces meet rather than leaving a gap between circular rope envelopes.

## Rope and surface controls

- **Width (Radius):** world-space rope radius. The three twisted fibre strands
  form one rope; their total diameter is twice this value.
- **Twist Pitch:** strand twist length in multiples of the rope radius.
- **Path Smoothing:** relax the route between waypoints.
- **Routing Detail:** refine surface routing on complex meshes.
- **Tightness:** normal-route centreline clearance. At 0 it is one radius above
  the base surface, at 0.5 half a radius, and at 1 directly on the surface.
- **Squishiness:** deform the target beneath the route. Maximum indentation is
  radius × Tightness × Squishiness; the ordinary centreline stays fixed.
- **Indent Width:** control the width of the deformation footprint.

High Tightness can place part of the rope inside the original mesh; Squishiness
controls the corresponding indentation. Spans and knot bodies retain physical
clearance. Existing shape keys are preserved; the add-on manages its own surface
indentation key and removes its effect when the last rope is removed.

Mark both ends of a segment **Spanning** to bridge a gap. Span routes avoid the
surface and do not indent it. A single spanning endpoint retains normal surface
behavior. Move the waypoints or reduce width if a span cannot clear an obstacle.

## Development

`bash tools/setup-cloud.sh` runs the pinned Blender 4.4 integration suite, builds
the ZIP, checks installation and restricted-context recovery, and tests upgrades
from prior releases. `tools/overhand_review.py` generates the current rope/curve
previews and review scene. See [tests/MANUAL.md](tests/MANUAL.md) for visual checks
and [KNOT_SOURCES.md](KNOT_SOURCES.md) for geometry references and attribution.
