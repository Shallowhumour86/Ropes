# Knot geometry references

The compact overhand and figure-eight styles use standard trefoil and figure-eight
parameterizations, independently adapted into open centerlines with curved leads,
rope thickness, surface clearance, and optional paired runs.

Version 0.9 junctions use a single open parameterized overhand/figure-eight
around the passive rope's axis. The passive section remains straight through
its eye; clearance approaches allow the active rope to pass beneath it.
The eye clears the passive bundle, and depth separates the active over/under
passes. Tests check the active knot determinant and winding around that axis,
together with an unknotted passive section. This replaces 0.8's paired knots.

Version 0.8 junction knots use two parallel components of the same open
parameterized knot, with a transported cross-section frame. This replaces the
independently cut torus-link loops from earlier versions. Both ropes traverse
the selected overhand or figure-eight path; doubled bundles carry four runs.
Their core paths remain fixed during the local lead-clearance correction.
Regression tests verify the selected knot's determinant after an outside
closure of its open ports (3 for overhand/trefoil, 5 for figure-eight).
Version 0.7 selects better-aligned overhand attachment ports and rigidly rotates
the knot body along its attachment chord before fairing the joins.
Version 0.6 aligns attachment tangents and relaxes shared junction curves under
local capsule-clearance and fairness constraints; this is a geometric visual
model rather than a physical tying simulation.

A freely available reference was inspected during implementation:

- **pyknotid**, Alexander Taylor and other contributors, MIT licensed:
  https://github.com/SPOCKnots/pyknotid
- Named knot coordinate examples (`k3_1` / `trefoil` and `k4_1` / `figure_eight`):
  https://github.com/SPOCKnots/pyknotid/blob/4d248ff32712702530e458b9dfa276038a5e61b2/pyknotid/make/named.py
- License checked at the same commit:
  https://github.com/SPOCKnots/pyknotid/blob/4d248ff32712702530e458b9dfa276038a5e61b2/LICENSE.txt

No pyknotid runtime dependency or external mesh asset is bundled. The add-on uses
procedural geometric knot models. These are visual approximations, not simulated
rope tying or physically tensioned knot meshes. The legacy trefoil remains an
option for comparison. Attribution and the reference's MIT notice follow.

Copyright 2018 Alexander Taylor and other contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
