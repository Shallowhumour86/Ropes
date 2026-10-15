# Blender 4.4 viewport acceptance — version 0.7

These checks need Blender's interactive desktop UI. Headless tests verify the
underlying geometry and projected mouse math, rather than all UI behavior.

- Install the 0.7.0 ZIP over an enabled 0.1 add-on without restarting Blender.
  Repeat after a failed 0.2 install and confirm that enabling recovers.
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

- Toggle Show Waypoints and enter Extend / Edit Ropes. Select a marker, click a
  different surface location, and confirm only that anchor moves. Undo and redo.
  Repeat with an endpoint and a middle waypoint. W toggles the markers; Esc/RMB
  cancels a pending move. Confirm markers do not render.
- Create a knot away from the main path on a dense surface. Increase squishiness;
  confirm indentation follows the knot footprint. Toggle it off and verify that
  only its additional imprint disappears.
- Switch Compact Overhand / Figure Eight / Legacy Trefoil. Override one manual
  knot and one junction knot independently. Verify other knots retain their style.
- Enable Doubled Rope. Inspect two runs, the folded first endpoint, and two free
  final ends. Adjust spacing, add a knot, move a waypoint, and inspect crossings.
  Confirm compression follows both runs and the fold. Disable doubling again.
- Save/reopen with marker visibility, doubled mode and knot overrides enabled.
  Confirm those settings persist and remain editable.

- Enable Waypoint Mode, place Normal and Spanning points using T, finish with Enter.
  Confirm only markers exist until Generate Rope. Move a draft point, undo/redo,
  change a point type in the list, save/reopen, then generate.
- Bridge a concave gap with two Spanning points. Confirm the clear section is
  straight, has no indentation, and stays clear when doubled or widened. Check
  that an obstructed span detours or reports an error. Mixed Normal/Spanning
  pairs must follow the surface and indent normally.
- Inspect a minimum-size doubled overhand. At a junction knot, follow both ropes
  through the shared interwoven shape; neither should continue straight beneath.
  Swap, toggle off/on, change style, and repeat at a self-crossing.

- Draw along a sharp concave crease, then across a curved waist/valley. Inspect
  single and doubled runs in Solid and Rendered modes for bunching, backtracking
  and unexpected junctions. Repeat with squishiness enabled.
- Inspect Normal/Spanning transitions on flat and curved geometry. Markers should
  sit on the surface, and rope centerlines should have only thickness clearance.
- Add draft points with many generated ropes already present: existing strand
  meshes must not regenerate on each click. Repeat moving points and undo/redo.
- Set Run Spacing to 1: both runs should be nearly touching. Open a 0.4 scene
  with custom spacing and verify conversion preserves the physical separation.

- Decrease Waypoint Size and place close points. Marker and click target should
  shrink together. Put a solid mesh in front of a marker: by default it must be
  hidden and unpickable. Enable Waypoints Through Objects and repeat.
- Return a generated rope to Edit Waypoint Draft. Add/move/retype points, undo and
  redo, save/reopen, then Generate Rope. Verify its knots and crossing choices.
  Repeat by enabling Waypoint Mode before Extend / Edit Ropes.
- Compare minimum-size normal/junction knots, including doubled ropes. Follow the
  entering runs through the shared knot and inspect entry clearance from all sides.
- On a coarse cube, inspect single/doubled turns for pinched inner tubes. On a
  coarse Suzanne and a varying-width groove, inspect doubled ropes for spikes.

- Wrap a smoothly curved, dense mesh and a rippled surface with single/doubled
  normal ropes. Inspect at grazing angles: running sections should have only the
  rope-thickness offset. Repeat with compression; spans and over-crossings should
  keep their intended clearance. Check that hard cube corners still round safely.
- Make a deliberate right-angle waypoint turn on a flat mesh. The turn should be
  rounded in the plane, with no height step or floating cushion.
- Inspect compact-overhand bodies from above and from the side: entry/exit ports
  should align with the running rope after rotating the whole body. Repeat after
  moving the knot and on a doubled rope.
