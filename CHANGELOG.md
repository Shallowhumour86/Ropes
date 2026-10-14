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
