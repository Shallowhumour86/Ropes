# Surface Ropes 0.3.0 — Blender 4.4

Draw ropes across a mesh, extend them, create over/under crossings and knots, and
compress the underlying surface. Each rope has independent settings. Ropes use
three twisted strands with UV-aligned natural-fiber shading. No external packages
are needed in Blender.

## Download and install

[Download version 0.3.0](https://github.com/Shallowhumour86/Ropes/raw/refs/heads/main/dist/surface-ropes-0.3.0.zip).
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

## New in 0.3.0

- Toggle waypoint markers, select a marker in Draw / Edit mode, then click a new
  surface location to move it. The rope, crossings, knots and indentation update.
  Waypoint moves participate in in-tool undo/redo.
- Knots now indent the surface beneath their generated footprint, instead of only
  along the original waypoint path. The same applies to both runs and the folded
  end of a doubled rope.
- Choose **Compact Overhand**, **Figure Eight** or **Legacy Trefoil**. Each rope
  has a default, and individual knots/junction knots can override it.
- **Doubled Rope** creates two parallel runs of one continuous rope, with a bight
  at the first waypoint and two free ends at the final waypoint. **Run Spacing**
  adjusts their separation.
- Independent controls, live width updates, smoothing, three-strand shading,
  in-tool undo/redo, and the installer fixes from 0.2.1 remain available.

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
    **Swap Over / Under**. This also selects which strand carries a junction knot.

The width control uses **radius** in Blender world units; the full rope diameter
is twice that value. **Twist Pitch** is the length of one strand revolution in
multiples of rope radius. Geometry is visible in Solid mode; use **Material
Preview** or **Rendered** mode to see the natural-fiber color and bump texture.

After changing the surface topology or scale, click **Rebuild Ropes**. Ropes and
strands are parented to the surface and follow object movement/rotation. Do not
edit or delete strand meshes independently; they are generated from the rope.

## Move waypoints

Enable **Show Waypoints** in the sidebar, then enter **Extend / Edit Ropes**.
Click a marker to select it; it highlights. Click elsewhere on the selected
surface to relocate that waypoint. This moves the existing point rather than
adding a new one. Earlier/later waypoints remain in place. Knots retain their relative positions
within each edited span, so a knot on a moved waypoint follows it. A lone crossing
between the same rope pair retains its knot and over/under choices when moved.

**W** toggles the markers while the tool is running. **Esc** or **RMB** cancels a
pending relocation; press Esc again to finish the tool. **Ctrl+Z** undoes a move,
and **Ctrl+Shift+Z** redoes it. To add a point exactly where a marker is, hide the
markers first with W. Markers are viewport-only and do not render. They can appear
in front of the mesh for editing; orbit to the desired point if markers overlap.

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
**Run Spacing** uses multiples of that radius; the default is 2.2 radii. Knot
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

- Paths are approximations on a triangulated mesh. Disconnected islands cannot
  be joined. Routing uses the base mesh rather than modifier-generated geometry
  or other animated shape keys. Apply required geometry modifiers first.
- Use outward-facing normals and a manifold mesh. Apply nonuniform scale.
- Nearly parallel strands are not treated as crossings; very close crossings
  can merge. Dense knots and extreme compression may intersect.
- Knots are connected procedural overhand/figure-eight sections spliced into a rope.
  Junction knots
  place this section on the selected over strand. They do not physically tie
  both strands together. Compression is geometric, without collision solving,
  volume preservation, soft-body simulation, or calculated rope tension.
- Knot editing uses a 16-pixel screen-distance threshold inside Draw / Edit mode.
  It does not resolve occlusion: orbit to the desired strand if several overlap.
- Drawing-mode undo/redo is specific to the current session. After finishing,
  Blender's normal Undo reverses the complete drawing session. Use **Remove Last
  Point** to remove just one anchor after leaving the tool.
- Large meshes and many ropes take longer to update. Three-strand geometry adds
  more vertices than the simple tube used in 0.1. Saved blend files retain the
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

The 25 integration checks cover routing, flat/curved smoothing, independent
settings, immediate width changes, unequal-width crossings, knots, compression,
placement undo/redo, strand geometry/UVs/materials, old-settings migration, waypoint relocation/undo, knot footprints/styles, doubled runs/folds, and
save/reload. Package installation/enabling/disabling and in-process upgrades from 0.1 and 0.2.1
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
