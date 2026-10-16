# Overhand geometry reference

Surface Ropes 0.12 uses one open overhand template for all placements. The
line-knot parametrization is retained from the previous compact overhand:

- a(t) = (2 + cos(3t)) cos(2t)
- b(t) = (2 + cos(3t)) sin(2t)
- h(t) = 2.3 + 1.25 sin(3t)

The open interval, coordinate scaling, rigid attachment orientation and cubic
leads turn this standard trefoil parametrization into the displayed overhand.
The two projected crossings bound its central eye. At a junction, an axis
through that eye carries the straight passive rope. Its radial opening uses
r_new = sqrt(r² + delta), choosing delta so the minimum radius accommodates
the sum of both rope radii minus 30% of the smaller radius, allowing slight
intersection to suggest compression. This monotone expansion preserves angular crossing order and
axial depth. Surface seating is a shared translation, not a local knot solver.

The previous separate junction formulas, doubled runs, figure-eight and legacy
style options have been removed. These are procedural visual curves rather than
a physical tying simulation. No external dependency or mesh asset is bundled.

Reference inspected during the original implementation:

- pyknotid, Alexander Taylor and contributors, MIT licensed:
  https://github.com/SPOCKnots/pyknotid
- Named trefoil coordinates, pinned source:
  https://github.com/SPOCKnots/pyknotid/blob/4d248ff32712702530e458b9dfa276038a5e61b2/pyknotid/make/named.py
- License at the same commit:
  https://github.com/SPOCKnots/pyknotid/blob/4d248ff32712702530e458b9dfa276038a5e61b2/LICENSE.txt

Copyright 2018 Alexander Taylor and other contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
