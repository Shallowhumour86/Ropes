# Surface Ropes 0.9.1 — Blender 4.4

Draw ropes across a mesh, extend them, create over/under crossings and knots, and
compress the underlying surface. Each rope has independent settings. Ropes use
three twisted strands with UV-aligned natural-fiber shading. No external packages
are needed in Blender.

## Download and install

[Download version 0.9.1](https://github.com/Shallowhumour86/Ropes/raw/refs/heads/main/dist/surface-ropes-0.9.1.zip).
If the link opens a GitHub page, use **Download raw**; sign in if required.

1. Save your scene. Disable the previous Surface Ropes version in Preferences.
2. In Blender 4.4, open **Edit → Preferences → Add-ons**.
3. Open the top-right menu, choose **Install from Disk**, and select the ZIP.
4. Enable **Surface Ropes**. This version refreshes cached geometry modules
   during installation, so upgrading from 0.1 does not require restarting. Press **N** in the 3D View and open the **Ropes** tab.

Use the ZIP directly; do not unzip it before installing. Version 0.1 scenes are
supported: the old shared settings are copied onto each existing rope when the
add-on is enabled or the scene opens. Existing ropes retain edge routing until
**Path Smoothing** is adjusted. Click **Rebuild Ropes** after upgrading to update existing knot shapes and their
indentation. Choose Legacy Trefoil if you want to retain the previous knot style.
Your first-version ZIP remains available in the repository.

## New in 0.9.1

- Compact overhand junction knots attach on the lower side of the passive rope,
  with short entry sections aligned along the tying rope. This removes the steep
  approach arches, including on doubled ropes.
- The knot is rotated around the passive axis; its eye and overhand topology
  are retained. The passive rope's path is unchanged from 0.9.0.
- Individual knots, figure-eight junctions and surface routing retain their
  existing behavior.

[Lower junction approaches, single and doubled](dist/surface-ropes-0.9.1-junction.png)

Install the ZIP and click **Rebuild Ropes** to update existing junction knots.
There is no need to toggle them off and recreate them for this update.

## New in 0.9.0

- At a junction, the rope you right-click ties around the other rope. The passive
  rope has a straight section through the knot's eye, with smooth approaches
  that provide room for the tying rope to pass underneath. Both ropes no longer
  try to tie separate overhand knots. Doubled ropes use the same active/passive
  behavior with clearance for the paired runs.
- At a self-crossing, the upper section ties around the lower section, following
  the existing Over / Under choice. Clicking the junction toggles the knot off.
- The tying-rope choice survives rebuilding, waypoint edits, undo/redo and saving.
  Existing junction knots default to the upper rope. To change the tying rope,
  toggle the knot off, then right-click the rope you want to tie.
- Fully smoothed routes across two flat faces now use their unfolded shortest
  path and retain the exact edge crossing. Flat crease faces use their actual
  normals instead of averaged corner-vertex normals that can steer sideways.
  This removes the corner detour for off-centre and tightly packed waypoints.
- Individual knots, normal curved-surface contact and convex-edge thickness
  clearance are retained.

[Active rope (green) around passive rope (red)](dist/surface-ropes-0.9.0-junction.png) ·
[Sparse and dense waypoint paths across a cube edge](dist/surface-ropes-0.9.0-corners.png)

Install the ZIP and click **Rebuild Ropes** to update existing rope geometry.

## Plan with waypoints

Enable **Waypoint Mode**, then **Draw New Rope**. Place your points and press
**Enter** to finish planning. Click **Generate Rope** when ready. Draft markers
remain visible at the clicked surface contacts, and can be moved before generation.
Placement only updates markers and undo metadata; routing, strand generation,
crossings and compression are deferred until Generate Rope. No rope geometry or surface
compression is created until you generate the rope.

Choose **Normal** or **Spanning** for the next point in the sidebar, or press **T**
while drawing to switch. Normal markers are spheres; spanning markers are cubes.
Select a waypoint in the active rope's list to change its type later.

Only a pair of adjacent Spanning waypoints creates a free span. Normal/Spanning
and Spanning/Normal pairs follow the surface as usual. Free spans use a direct
line when clear, otherwise try a collision-checked detour around the target mesh.
Each generated run is checked for rope-thickness clearance, including doubled
runs. Spans contribute no
indentation. The route is an approximate shortest clear path, not a physical
rope simulation. If no safe route is found, reduce the width or move the points.
Collision checks use the target object's base mesh, not other scene objects.

See `KNOT_SOURCES.md` for the inspected MIT-licensed reference and attribution.
No downloaded knot meshes or additional runtime dependencies are required.

## Draw and edit

1. Select the object to wrap in **Object Mode** and click **Use Selected Surface**.
2. Expand **New Rope Defaults** if you want to choose settings for future ropes.
   These settings do not change existing ropes.
3. Click **Draw New Rope**, then left-click two surface points. Additional clicks
   extend the same rope through each new anchor.
4. Press **N** while drawing to begin a separate rope. New ropes pass **under**
   existing ropes. At self-crossings the later pass goes under the earlier pass.
5. Right-click on a rope to add a knot; right-click it again to remove it.
   Right-click a crossing to toggle it between a junction and a knot.
6. Use **Ctrl+Z** or **Backspace** to undo the last placement or knot edit without
   leaving the tool. **Ctrl+Shift+Z** redoes it. Starting a new edit clears redo.
7. Press **Enter** or **Esc** to finish and retain your edits. Right-clicking empty
   space also finishes. Middle mouse, wheel and Alt gestures navigate the viewport.
8. Choose an **Active Rope** from the dropdown, or select any visible strand and
   click **Use Selected Rope**. Change the controls in that rope's named box;
   changes apply immediately to that rope. Nearby ropes still follow any shared
   surface indentation at an overlap, but their own settings stay independent.
9. Click **Extend / Edit Ropes** to continue the active rope. **Remove Last Point**
   removes only its final anchor outside drawing mode. **Remove Active Rope**
   removes the entire rope and its junctions.
10. Finish drawing, choose a crossing in the junction list, then use
    **Swap Over / Under**. For a knot, right-click the rope that should tie around
    the other one. At self-crossings the upper section makes the knot.

The width control uses **radius** in Blender world units; the full rope diameter
is twice that value. **Twist Pitch** is the length of one strand revolution in
multiples of rope radius. Geometry is visible in Solid mode; use **Material
Preview** or **Rendered** mode to see the natural-fiber color and bump texture.

After changing the surface topology or scale, click **Rebuild Ropes**. Ropes and
strands are parented to the surface and follow object movement/rotation. Do not
edit or delete strand meshes independently; they are generated from the rope.

## Move waypoints

Adjust **Waypoint Size** before drawing to reduce both marker dimensions and the
pick radius. Hidden markers cannot be selected through a solid mesh unless
**Waypoints Through Objects** is enabled. The through-object toggle starts off.

To plan more points on an already generated rope, select that rope and click
**Edit Waypoint Draft**, then **Extend / Edit Ropes**. Its generated geometry and
compression are replaced by markers while you edit. Click **Generate Rope** after
finishing. With **Waypoint Mode** enabled, entering **Extend / Edit Ropes** on a
generated rope also starts a draft automatically. Draft placement, relocation and
undo/redo do not rebuild the other ropes. Native Blender Undo can restore the
conversion to a draft; in-tool undo handles subsequent point edits.


Enable **Show Waypoints** in the sidebar, then enter **Extend / Edit Ropes**.
Click a marker to select it; it highlights. Click elsewhere on the selected
surface to relocate that waypoint. This moves the existing point rather than
adding a new one. Earlier/later waypoints remain in place. Knots retain their relative positions
within each edited span, so a knot on a moved waypoint follows it. A lone crossing
between the same rope pair retains its knot and over/under choices when moved.

**W** toggles the markers while the tool is running. **Esc** or **RMB** cancels a
pending relocation; press Esc again to finish the tool. **Ctrl+Z** undoes a move,
and **Ctrl+Shift+Z** redoes it. To add a point exactly where a marker is, hide the
markers first with W. Markers are viewport-only and do not render. Enable **Waypoints Through Objects** when you need to select hidden points;
otherwise orbit to the desired side if markers overlap or are occluded.

## Knot styles and doubled ropes

Set **Default Knot Type** in the active rope's box. Existing knots using **Rope
Default** change with it. To override one knot, select its row in the knot list
and change **Knot Type**. For a junction knot, select the junction and change
**Junction Knot Type**. **Knot Size** enlarges the knot; its minimum keeps clearance
for the rope thickness. The compact styles use open parameterized centerlines
and curved leads instead of the original large, closed-looking trefoil tangle.

Enable **Doubled Rope** on an existing or new rope. Both runs follow the same
waypoints with an offset, and a continuous folded end joins them at the first
waypoint. Each run retains the active rope's radius and three-strand construction.
**Run Spacing** is a separation multiplier, with a default and minimum of **1**.
At 1 the centers are 2.02 radii apart, leaving only a small clearance between the
runs. At 2 the separation doubles. Knot
geometry expands to accommodate the pair. Right-clicking either run edits the
same logical knot station. This is a paired visual rope, not a simulated tying
procedure, hitch, or physical constraint. Keep waypoints away from narrow mesh
boundaries so there is room for both runs and the folded end.

## Surface path smoothing

- **0** retains mesh-edge routing, including the staircase effect on coarse grids.
- Intermediate values blend toward a smoother route on the surface.
- **1** removes edge snapping. Flat spans become exact straight lines; curved spans
  relax around the surface, with rope thickness offset above it.

A literal straight chord through a sphere would run inside it, so the maximum
smoothing on a curved object remains surface-constrained. Clicked anchors are
preserved. Every successive pair of anchors defines its own smoothed leg.
**Routing Detail** improves the initial graph approximation, at additional cost.

## Squishiness

Each rope's **Squishiness** controls how readily the surface compresses beneath
it; **Tightness** controls indentation strength. **Indent Width** controls the
spread of that rope's compression in multiples of its radius. The generated runs, folded ends, and knot footprints contribute to compression.
The strongest local indentation wins where contact regions overlap. Setting one rope's
squishiness/tightness to zero removes its compression; other ropes retain theirs.

The add-on uses one combined **Ropes Compression** relative shape key per surface,
leaves the base mesh intact, and preserves existing shape keys. Do not rename or
manually edit its compression key. Compression needs vertices near the rope:
subdivide coarse surfaces first if you want smooth indentations. A shared mesh
must be made single-user before compression can be enabled. Removing the last
rope restores the visible surface.

## Practical limits

- Paths are approximations on a triangulated mesh. Normal surface routes cannot join disconnected islands; spanning routes can. Routing uses the base mesh rather than modifier-generated geometry
  or other animated shape keys. Apply required geometry modifiers first.
- Use outward-facing normals and a manifold mesh. Apply nonuniform scale.
- Nearly parallel strands are not treated as crossings; very close crossings
  can merge. Junction contact relaxation improves clearance but is a procedural
  approximation; dense arrangements and extreme compression can still intersect.
- Knots are connected procedural overhand/figure-eight sections spliced into a rope.
  Junction knots use one tying component and one straight passive section, with
  smooth clearance approaches. These are procedural visual approximations of tied
  ropes. Compression is geometric, without collision solving,
  volume preservation, soft-body simulation, or calculated rope tension.
- Knot editing uses a 16-pixel screen-distance threshold inside Draw / Edit mode.
  It does not resolve occlusion: orbit to the desired strand if several overlap.
- Drawing-mode undo/redo is specific to the current session. After finishing,
  Blender's normal Undo reverses the complete drawing session. Use **Remove Last
  Point** to remove just one anchor after leaving the tool.
- Large meshes and many ropes take longer to update. Three-strand geometry adds
  more vertices than the simple tube used in 0.1. Junction-knot contact relaxation
  also adds generation time; waypoint drafts defer that work until generation. Saved blend files retain the
  editable anchors, per-rope settings, knots, and crossing choices.

## Development

Use the existing cloud checkout; each task is already isolated and needs no Git
worktree. For Python 3.11 and hash-verified Blender 4.4 testing dependencies:

```sh
bash tools/setup-cloud.sh
```

Or, after setup:

```sh
/workspace/.ropes-tools/venv/bin/python tests/blender_integration.py
/workspace/.ropes-tools/venv/bin/python tools/package.py
/workspace/.ropes-tools/venv/bin/python tests/package_install.py
/workspace/.ropes-tools/venv/bin/python tests/package_upgrade.py
/workspace/.ropes-tools/venv/bin/python tests/restricted_registration.py
```

The 53 integration checks cover routing, flat/curved smoothing, independent
settings, immediate width changes, unequal-width crossings, knots, compression,
placement undo/redo, strand geometry/UVs/materials, old-settings migration, waypoint relocation/undo, knot footprints/styles, doubled runs/folds, and
marker size/depth picking, generated-rope draft editing/persistence, coarse
valleys, cube-corner bend radii, bounded contact gaps on curved surfaces, knot
body orientation, knot tangents, junction winding/entry clearance, active/passive ownership and unfolded edge routes, and
save/reload. Package installation/enabling/disabling and in-process upgrades from 0.1, 0.2.1, 0.3.0, 0.4.0, 0.5.0, 0.6.0, 0.7.0, 0.8.0 and 0.9.0
are checked in temporary Blender profiles. Restricted registration and recovery
from partial failed registrations are checked explicitly as well. NumPy 1.26 is pinned for Blender 4.4's native ABI. Testing packages
are for the cloud only; desktop Blender users just install the ZIP.

Headless tests include projected mouse math but cannot establish complete desktop
interaction. See `tests/MANUAL.md` for viewport acceptance checks. Generate an
editable demo and a real Blender render with:

```sh
/workspace/.ropes-tools/venv/bin/python tools/demo.py
/workspace/.ropes-tools/venv/bin/python tools/knot_gallery.py
```
