# Surface Ropes 0.2.0 — Blender 4.4

Draw ropes across a mesh, extend them, create over/under crossings and knots, and
compress the underlying surface. Each rope has independent settings. Ropes use
three twisted strands with UV-aligned natural-fiber shading. No external packages
are needed in Blender.

## Download and install

[Download version 0.2.0](https://github.com/Shallowhumour86/Ropes/raw/refs/heads/main/dist/surface-ropes-0.2.0.zip).
If the link opens a GitHub page, use **Download raw**; sign in if required.

1. Save your scene. Disable the previous Surface Ropes version in Preferences.
2. In Blender 4.4, open **Edit → Preferences → Add-ons**.
3. Open the top-right menu, choose **Install from Disk**, and select the ZIP.
4. Enable **Surface Ropes**, then restart Blender to ensure the updated Python
   modules are loaded. Press **N** in the 3D View and open the **Ropes** tab.

Use the ZIP directly; do not unzip it before installing. Version 0.1 scenes are
supported: the old shared settings are copied onto each existing rope when the
add-on is enabled or the scene opens. Existing ropes retain edge routing until
**Path Smoothing** is adjusted. Click **Rebuild Ropes** to generate the new strands.
Your first-version ZIP remains available in the repository.

## What changed

- Width, tightness, squishiness, indent width, routing detail, path smoothing,
  and twist pitch are independent for each rope.
- All active-rope settings update immediately, including width.
- Ctrl+Z or Backspace undoes the latest edit while drawing. Ctrl+Shift+Z redoes it.
  History includes placements, new ropes, and knot toggles within that session.
- Path Smoothing runs from mesh-edge routing at 0 to a relaxed surface path at 1.
  On a flat surface, 1 is the exact straight line between clicked anchors.
- Three twisted strand meshes give ropes a real three-lobed silhouette. UVs follow
  each strand, so the fiber texture bends and twists with the rope.

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
spread of that rope's compression in multiples of its radius. The strongest
local indentation wins where contact regions overlap. Setting one rope's
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
- Knots are connected open trefoil sections spliced into a rope. Junction knots
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
```

The 19 integration checks cover routing, flat/curved smoothing, independent
settings, immediate width changes, unequal-width crossings, knots, compression,
placement undo/redo, strand geometry/UVs/materials, old-settings migration, and
save/reload. Package installation/enabling/disabling is checked in a temporary
Blender profile. NumPy 1.26 is pinned for Blender 4.4's native ABI. Testing packages
are for the cloud only; desktop Blender users just install the ZIP.

Headless tests include projected mouse math but cannot establish complete desktop
interaction. See `tests/MANUAL.md` for viewport acceptance checks. Generate an
editable demo and a real Blender render with:

```sh
/workspace/.ropes-tools/venv/bin/python tools/demo.py
```
