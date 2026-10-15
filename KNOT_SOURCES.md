# Knot geometry references

The compact overhand and figure-eight styles use standard trefoil and figure-eight
parameterizations, independently adapted into open centerlines with curved leads,
rope thickness, surface clearance, and optional paired runs.

Junction knots use independently implemented two-component torus-link curves,
with each rope following one component. They are visual interwoven junctions;
style selection changes the winding rather than simulating a named rope bend.

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
