# Blender 4.4 viewport acceptance — version 0.2

These checks need Blender's interactive desktop UI. Headless tests verify the
underlying geometry and projected mouse math, rather than all UI behavior.

- Disable 0.1, install the 0.2 ZIP, restart Blender and enable Surface Ropes.
  Verify the Ropes sidebar and version without console errors.
- Open an old 0.1 blend. Confirm its ropes retain their width and compression
  values in independent controls. Rebuild to generate three-strand geometry.
- Draw two separated ropes on the same dense surface. Select A using Active Rope
  or a strand plus Use Selected Rope. Change A's width, tightness, squishiness,
  indent width and twist pitch. A updates immediately; B's settings remain intact.
- Change New Rope Defaults and confirm existing ropes retain their settings.
  Create C and confirm it receives the new defaults.
- Draw three anchors. Press Ctrl+Z while drawing: only the final placement is
  removed. Ctrl+Shift+Z restores it. Repeat with Backspace. Undo the first anchor
  of a new rope: earlier ropes remain. Redo restores the new rope.
- Toggle a knot, undo and redo while drawing. Finish with Enter, choose an active
  rope, and use Remove Last Point: earlier anchors remain. Verify normal Blender
  Undo restores that action.
- On a coarse, uneven grid, draw a diagonal span and move Path Smoothing from 0 to
  1. The staircase becomes a smooth path and then a straight diagonal on the flat
  surface. Repeat on a sphere and inspect that the rope stays outside the surface.
- Draw unequal-width ropes crossing each other. Confirm the new strand is under,
  and swapping reverses the crossing. Toggle a crossing knot in both directions.
  Repeat on a self-crossing.
- Inspect strands in Solid mode, then Material Preview and Rendered mode. Look
  for three twisted strands and longitudinal fiber shading. Change twist pitch
  and width, then inspect the knot and the ends in close-up.
- Set both ropes' squishiness to positive values, then turn A to zero: B's
  indentation remains. Remove all ropes and confirm restoration of the surface.
- Save/reopen and check independent settings, anchors, crossings and knots.
  Extend an old rope, undo the extension in-tool and redo it.
- Check sidebar invocation, orbit/zoom during drawing, empty clicks, disconnected
  islands, shared meshes and non-mesh selections. Errors should be informative.
