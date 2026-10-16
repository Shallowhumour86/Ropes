## 0.12.0

- Remove doubled-rope controls and construction, plus figure-eight and legacy
  knot styles. Migrate saved ropes to single overhands, retaining their anchors,
  widths, identities and knot stations.
- Retain the accepted line overhand and reuse its parametrization at both kinds
  of junction. Open its eye with a smooth monotone radial transformation around
  the passive axis; the passive core stays straight.
- Delete the previous independent junction formula, collision relaxation and
  attachment shear. Seat both components with a common translation and join
  their ports with long tangent-continuous cubic leads.
- Add Rope / Centre Curves / Rope + Curves views. The actual generated centreline
  is inspectable Bezier data with vector handles, avoiding hidden smoothing.
- Preserve ordinary strand-contact junctions, routing, spans, drafting and
  surface deformation. Replace removed-feature tests with shared-template,
  smooth eye opening, self/other junction, curve-view and migration coverage.

## 0.11.1

- Close residual crossing gaps against the three actual fibre centrelines and
  tube radii, retaining the braid phase of the complete rope. Check crossings
  again after other path edits so the final rendered strands determine contact.
- Align the junction knot's full entry/exit chord to the active rope using an
  axial shear. Apply the same spatial deformation to body and leads, preserving
  radial clearance around the unchanged passive line; resolve contacts afterward.
- Add rendered mesh contact checks at different twists, port alignment checks,
  and wrapping/clearance checks alongside canonical knot topology tests.
- Keep doubled Run Spacing and saved controls unchanged. Rebuild existing ropes.

## 0.11.0

- Select the closest crossing candidate within each detection cluster so the
  overpass apex lines up with the passive curve rather than its detection band.
- Remove the doubled-run padding: spacing 1 is exactly 2 × rope radius. Apply
  the same convention to bundle footprints, knot fitting and upgrade checks.
- Fit the knot eye to the exact sum of active/passive radii. Tighten actual knot
  runs with capsule and nonlocal self-contact constraints rather than scaling
  the whole bundle. Preserve knot ports, then seat the body and blend its leads.
- Add apex alignment and snug knot regression checks alongside existing
  topology, unequal width, surface seating and installation tests.

## 0.10.1

- Fit ordinary overpasses against actual single or doubled run curves. Their
  closest segment separation is the sum of the two rope radii, with only a
  numerical tolerance. Account for independent widths and Tightness heights.
- Keep bundle envelopes for horizontal crossing footprints and broad-phase
  detection; remove their use as vertical overpass clearance.
- Crossing detection now uses both ropes' radii rather than the larger one,
  avoiding missed junctions between curves with different Tightness heights.
- Audited doubled spacing, knot fitting, lead constraints and surface offsets:
  doubled spacing is lateral; knot fitting and leads already use actual rope
  radii. Their existing small collision margins and span safety are retained.
- Existing scenes update through Rebuild Ropes; no saved settings are changed.

## 0.10.0

- Changed Tightness to control normal centreline clearance: radius at 0, half
  radius at 0.5, and zero at 1. Normal routes and paired offsets no longer use
  full-tube surface collision correction that caused lateral valley detours.
- Kept full physical clearance for spans and knot cores; blended normal/span
  endpoint heights and stabilized doubled core frame initialization.
- Squishiness now deforms the mesh beneath a fixed ordinary route, with maximum
  indentation radius × Tightness × Squishiness. Knot body seating is retained.
- Replaced the loose overhand eye with a closer passive cross-section fit;
  radial room is added at self-crossings. Paired active runs are checked against
  both actual passive runs. Lower entries, topology and grounding are retained.
- Added exact clearance, independent deformation, narrow-valley centreline and
  snug passive-top contact tests. Updated previous full-radius assertions to
  the new centreline model. Existing settings update through Rebuild Ropes.

## 0.9.2

- Removed excess clearance beneath junction knots by lowering both knot
  components together until their actual rope runs meet the target surface.
- Used the separate centerlines and radii of doubled runs for the support
  calculation, excluding the trial folded end that is not part of the knot.
- Kept the lower entry shape and straight passive section; regenerated approach
  curves meet the junction at its new height. Free-span junctions are excluded.
- Added flat/curved, single/doubled, unequal-width, run-spacing and free-span
  regression coverage. Existing junctions update through Rebuild Ropes.

## 0.9.1

- Rotated compact-overhand junction bodies by a half-turn around the passive
  axis, retaining their knot shape and eye while bringing their ports lower.
- Aligned the short entry/exit sections with the tying rope so the approach
  curves no longer need to arch over the knot's attachment points.
- Added single/doubled approach-height and tangent checks, plus a
  comparison against the passive rope path generated by the shipped 0.9.0
  within floating-point precision.
  Existing junctions update through Rebuild Ropes.

## 0.9.0

- Junctions now use one tying rope around a passive rope's straight core,
  replacing the paired overhand knots. The passive section has smooth clearance
  approaches so the tying rope can pass below it without entering the mesh.
- Right-click selection chooses the tying rope at distinct-rope junctions.
  At self-crossings the upper section ties around the lower one. Ownership
  survives repathing, state restore, draft edits and scene persistence; older
  junctions default to their upper rope.
- Added exact unfolded routing across adjacent planar faces, including the
  precise fold point. Corrected crease-face normals to remove tangential drift.
- Added off-centre/dense corner, diagonal unfolded route, active/passive
  ownership, knot winding and straight-passive-core regression checks.

## 0.8.0

- Replaced independently cut junction loops with paired open knot centerlines.
  Both participating ropes follow the selected overhand/figure-eight topology;
  tests verify knot determinants of 3/5 using an outside closure of the ports.
- Fixed knot cores during junction collision resolution, preventing the lead
  solver from distorting their traced structure. Included all doubled runs.
- Removed broad excess clearance around convex edges while preserving the
  concave-valley handling and soft curved-surface contact.
- Used physical-distance tangent estimates for doubled runs and uniform
  arclength samples for visible strands, avoiding dense-waypoint frame flips.
- Added Blender 4.4 regression coverage and single/doubled junction and cube-edge
  previews. Existing scenes update through Rebuild Ropes.

# 0.7.0

- Removed broad bend-cushion lift from smooth curved surfaces; retained clearance
  cushions at genuine hard mesh edges.
- Retained ordinary surface contacts during offset relaxation and settled doubled
  runs independently on smooth sections, preserving knots, crossings and spans.
- Rounded deliberate waypoint corners along the surface without inflating height.
- Recut compact-overhand attachment ports and rigidly reoriented whole knot bodies
  along their attachment chord, with a compact roll and smooth entry joins.
- Added upper contact-gap regressions on a sphere and a rippled surface, including
  deformation; checked body orientation before the endpoint fairing correction.

# 0.6.0

- Added waypoint display size with a corresponding smaller pick radius.
- Added waypoint depth visibility/picking toggle, defaulting to occlusion by solid
  objects; display controls update without rebuilding geometry.
- Added Edit Waypoint Draft for generated ropes, plus automatic conversion when
  extending with Waypoint Mode enabled. Pending knots/crossings survive saving.
- Reduced shared junction core scale and aligned knot attachment tangents.
- Added coupled capsule contact constraints and fairing for junction knots/entries.
- Replaced amplified signed-plane bundle offsets with bounded distance-based
  corrections; relaxed both runs together through changing valley widths.
- Added local clearance cushions for smooth, tube-safe bends at sharp corners.

# 0.5.0

- Stabilized contact normals and offset paths through concave valleys.
- Transported doubled-run frames along the actual 3D rope instead of independently
  projecting raised sections back onto the object.
- Matched span endpoint height to normal rope clearance and relaxed transitions.
- Eased indentation to zero at surface/span joins to prevent compression steps.
- Placed markers on their stored surface contacts.
- Removed routing, rendering, crossing and compression work from draft clicks,
  moves and draft undo/redo; updates affect only draft metadata and markers.
- Normalized Run Spacing to a minimum/default of 1 (nearly touching), migrating
  previous settings to preserve physical separation.
- Reduced minimum doubled compact-overhand core size further.

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
