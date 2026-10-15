# 0.4.0

- Added draft waypoint placement and explicit Generate Rope.
- Added Normal/Spanning waypoint types, editable per point; only two spanning
  endpoints create a free, collision-checked leg with no compression.
- Tightened minimum-size doubled compact overhand knots.
- Made junction knots shared interwoven sections involving both crossing ropes.
- Preserved existing installation recovery and enabled-upgrade support.

# 0.3.0

- Added visible waypoint markers and click-marker/click-surface relocation with
  rope rebuilding, knot/crossing updates, and in-tool undo/redo. W toggles markers.
- Compression now includes generated knot footprints, doubled runs, and folds.
- Added compact overhand and figure-eight knot styles, legacy trefoil, per-rope
  defaults, individual/junction overrides and knot size. Mathematical references
  and the inspected MIT license are documented in KNOT_SOURCES.md.
- Added one continuous doubled rope with paired surface runs, adjustable spacing,
  a folded end at the first waypoint, and two free ends at the final waypoint.
- Retained cached-module refresh, restricted-registration handling, and recovery
  after failed installs. Verified upgrade paths from 0.1 and 0.2.1.
- 25 headless Blender 4.4 integration checks plus installer/lifecycle checks pass;
  complete desktop interaction still requires the manual acceptance checklist.

# 0.2.1

- Fixed the `cannot import name 'three_strands'` installation error when Blender
  retains version 0.1's geometry module during an in-place upgrade.
- Deferred existing-scene initialization until Blender releases the restricted
  enable context, fixing `_RestrictData` errors during registration.
- Clean up partial registrations left by failed installs so a retry can succeed.
- Added a regression check that installs and enables 0.1, then installs 0.2.1
  without restarting Blender. It also checks existing rope data migration.

# 0.2.0

- Added independent per-rope width, tightness, squishiness, indentation width,
  routing detail, smoothing and twist pitch. Scene values now set new-rope defaults.
- Width and other rope controls update immediately, including crossings and the
  combined surface compression. Strand selection survives those updates.
- Added in-tool Ctrl+Z / Backspace undo and Ctrl+Shift+Z redo for individual edits,
  plus Remove Last Point outside drawing mode.
- Added surface-constrained smoothing from edge routing to relaxed paths;
  maximum smoothing is an exact straight span on planar surfaces.
- Replaced plain tubes with three twisted strand meshes and UV-aligned fiber
  shading. Added controls for strand twist pitch.
- Added migration of version 0.1 shared settings to independent rope settings,
  preserving existing anchors, knots and crossing preferences.
- Validated 19 Blender 4.4 integration checks and ZIP installation/enable/disable.
  Full interactive desktop acceptance remains a manual check.

# 0.1.0

Initial release: surface ropes, extension, over/under crossings, knot toggles,
and reversible geometric compression.
