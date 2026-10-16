# Surface Ropes 0.12 visual checks

1. Open `surface-ropes-0.12.0-review.blend`. In Centre Curves mode compare the
   line knot, self-crossing knot and two-rope junction side by side. Look for the
   same heart outline, hemispheres and crossing order; the junction eye is larger.
2. Switch between Rope, Centre Curves and Rope + Curves. Inspect a selected rope
   in Edit Mode. Vector handles must match the generated centreline exactly.
3. Add a line knot. Its accepted shape should remain unchanged. Change Knot Size
   from 1 to 2; both hemispheres should scale smoothly with curved leads.
4. At a self-crossing, swap the upper passage and create a knot: only that
   passage ties the overhand; the lower passage runs straight through the eye.
5. Cross separate ropes with different radii. Right-click each in turn to choose
   the tying rope. The eye must accommodate the passive radius without sharp
   elbows or independently generated junction lobes.
6. Repeat at oblique angles and on a sphere. The knot body must keep its shared
   shape; placement translates it to the surface instead of pinching its points.
7. Confirm ordinary over/under junctions still touch at their braided surfaces.
8. Draw in valleys, across corners, and over mixed Normal/Spanning waypoints.
   Change Tightness and Squishiness independently; spans must remain clear.
9. Save and reload a waypoint draft and a generated rope with knots. Check their
   controls, anchors and curve view. Undo/redo waypoint edits and regenerate.
10. Upgrade an old scene with doubled ropes and alternative knot styles. The
    result should be single overhands with the same waypoints, widths, identities
    and knot stations. The removed controls should no longer appear.

Old release ZIPs and rendered previews remain in `dist` for comparison.
