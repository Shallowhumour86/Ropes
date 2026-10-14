"""Surface routing and rope geometry. Runs inside Blender without UI dependencies."""
import heapq
import math

import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree


class Surface:
    """World-space routing graph on a subdivided copy of the undeformed mesh."""

    def __init__(self, obj, subdivisions=2):
        self.obj = obj
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        if len(bm.faces)*(subdivisions+1)**2 > 500000:
            bm.free()
            raise ValueError('Routing graph is too large. Reduce Routing Detail or simplify the mesh.')
        if subdivisions:
            bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=subdivisions,
                                      use_grid_fill=True)
            bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.normal_update()
        self.vertices = [obj.matrix_world @ v.co for v in bm.verts]
        self.faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        self.adjacency = [[] for _ in self.vertices]
        for edge in bm.edges:
            a, b = (v.index for v in edge.verts)
            length = (self.vertices[a] - self.vertices[b]).length
            self.adjacency[a].append((b, length))
            self.adjacency[b].append((a, length))
        bm.free()
        if not self.faces:
            raise ValueError('The surface must contain mesh faces.')
        self.bvh = BVHTree.FromPolygons(self.vertices, self.faces, all_triangles=True)

    def project(self, point):
        co, normal, face, _ = self.bvh.find_nearest(Vector(point))
        if co is None:
            raise ValueError('Could not find a surface near this point.')
        return co, normal, face

    def route(self, start, end, smoothing=1.0):
        start, _, sf = self.project(start)
        end, _, ef = self.project(end)
        if sf == ef:
            return uniform_samples([start, end], 100)
        distances = [float('inf')] * len(self.vertices)
        parents = {}
        queue = []
        for v in self.faces[sf]:
            distances[v] = (start - self.vertices[v]).length
            heapq.heappush(queue, (distances[v], v))
            parents[v] = None
        goals = set(self.faces[ef])
        best, last = float('inf'), None
        while queue:
            distance, vertex = heapq.heappop(queue)
            if distance > distances[vertex]:
                continue
            if distance > best:
                break
            if vertex in goals:
                total = distance + (end - self.vertices[vertex]).length
                if total < best:
                    best, last = total, vertex
            for other, length in self.adjacency[vertex]:
                candidate = distance + length
                if candidate < distances[other]:
                    distances[other] = candidate
                    parents[other] = vertex
                    heapq.heappush(queue, (candidate, other))
        if last is None:
            raise ValueError('These points lie on disconnected mesh islands.')
        chain = []
        while last is not None:
            chain.append(self.vertices[last])
            last = parents[last]
        points = [start] + list(reversed(chain)) + [end]
        return smooth_surface_path(self, points, smoothing)


def uniform_samples(points, count=100):
    lengths = cumulative(points)
    return [sample_at(points, lengths, lengths[-1]*i/count)[0] for i in range(count+1)]


def smooth_surface_path(surface, points, amount):
    """Blend the edge route toward a surface-constrained elastic path.

    On a plane the maximum is the exact straight line, not a smoothed staircase.
    Curved surfaces keep the graph's chosen side and relax on that surface.
    """
    points = uniform_samples(points, 100)
    if amount <= 0:
        return points
    start, end = points[0], points[-1]
    direct = [start.lerp(end, i/100) for i in range(101)]
    tolerance = max((end-start).length*1e-5, 1e-6)
    if all((surface.project(p)[0]-p).length < tolerance for p in direct):
        relaxed = direct
    else:
        relaxed = [p.copy() for p in points]
        for stride in (12, 8, 4, 2, 1):
            for _ in range(8):
                updated = [start]
                for i in range(1, 100):
                    a, b = relaxed[max(0, i-stride)], relaxed[min(100, i+stride)]
                    candidate = relaxed[i]*.25 + (a+b)*.375
                    projected, normal, _ = surface.project(candidate)
                    _, original_normal, _ = surface.project(relaxed[i])
                    # Avoid jumping through thin shells to the opposite side.
                    updated.append(projected if normal.dot(original_normal) > -.1 else relaxed[i])
                relaxed = updated+[end]
    result = [surface.project(a.lerp(b, amount))[0] for a, b in zip(points, relaxed)]
    result[0], result[-1] = start, end
    return result


def three_strands(points, radius, pitch=12.0):
    """Three touching helices around the centerline with parallel-transport frames."""
    dense = resample(points, radius*.6)
    lengths = cumulative(dense)
    strands = [[], [], []]
    last_x = None
    for i, (point, distance) in enumerate(zip(dense, lengths)):
        tangent = dense[min(i+1, len(dense)-1)]-dense[max(i-1, 0)]
        if tangent.length < 1e-9:
            tangent = Vector((1, 0, 0))
        tangent.normalize()
        if last_x is None:
            x = tangent.orthogonal().normalized()
        else:
            x = last_x-tangent*last_x.dot(tangent)
            if x.length < 1e-5:
                x = tangent.orthogonal()
            x.normalize()
        y = tangent.cross(x).normalized()
        last_x = x
        angle = 2*math.pi*distance/(radius*pitch)
        for strand in range(3):
            phase = angle+strand*2*math.pi/3
            strands[strand].append(point+radius*.54*(math.cos(phase)*x+math.sin(phase)*y))
    return strands


def strand_tube(points, radius, rope_radius, sides=10):
    """A smooth tube mesh with UVs running along the strand, including end caps."""
    lengths = cumulative(points)
    vertices, faces, face_uvs = [], [], []
    last_x = None
    for i, point in enumerate(points):
        tangent = points[min(i+1, len(points)-1)]-points[max(0, i-1)]
        if tangent.length < 1e-9:
            tangent = Vector((1, 0, 0))
        tangent.normalize()
        x = tangent.orthogonal() if last_x is None else last_x-tangent*last_x.dot(tangent)
        if x.length < 1e-5:
            x = tangent.orthogonal()
        x.normalize()
        y = tangent.cross(x).normalized()
        last_x = x
        for j in range(sides):
            angle = 2*math.pi*j/sides
            vertices.append(point+radius*(math.cos(angle)*x+math.sin(angle)*y))
        if i:
            u0, u1 = lengths[i-1]/(rope_radius*12), lengths[i]/(rope_radius*12)
            for j in range(sides):
                nxt = (j+1)%sides
                faces.append(((i-1)*sides+j, (i-1)*sides+nxt, i*sides+nxt, i*sides+j))
                face_uvs.append(((u0, j/sides), (u0, (j+1)/sides),
                                 (u1, (j+1)/sides), (u1, j/sides)))
    faces.append(tuple(reversed(range(sides))))
    face_uvs.append(tuple((0, j/sides) for j in reversed(range(sides))))
    last = (len(points)-1)*sides
    faces.append(tuple(last+j for j in range(sides)))
    face_uvs.append(tuple((lengths[-1]/(rope_radius*12), j/sides) for j in range(sides)))
    return vertices, faces, face_uvs


def resample(points, spacing):
    result = [Vector(points[0])]
    for a, b in zip(points, points[1:]):
        count = max(1, min(512, math.ceil((b-a).length / spacing)))
        result.extend(a.lerp(b, i/count) for i in range(1, count+1))
    return result


def cumulative(points):
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + (b-a).length)
    return lengths


def sample_at(points, lengths, distance):
    import bisect
    i = max(0, min(len(points)-2, bisect.bisect_right(lengths, distance)-1))
    span = lengths[i+1] - lengths[i]
    t = max(0.0, min(1.0, (distance-lengths[i])/span)) if span else 0.0
    tangent = points[i+1] - points[i]
    if tangent.length < 1e-9:
        tangent = Vector((1, 0, 0))
    return points[i].lerp(points[i+1], t), tangent.normalized()


def closest_segments(p, q, a, b):
    """Closest positions on two finite segments (including parallel segments)."""
    u, v, w = q-p, b-a, p-a
    aa, bb, cc, dd, ee = u.dot(u), u.dot(v), v.dot(v), u.dot(w), v.dot(w)
    if aa < 1e-16 or cc < 1e-16:
        return p, a, 0.0, 0.0
    denom = aa*cc-bb*bb
    s = max(0.0, min(1.0, (bb*ee-cc*dd)/denom)) if denom > 1e-16 else 0.0
    t = (bb*s+ee)/cc
    if t < 0:
        t, s = 0.0, max(0.0, min(1.0, -dd/aa))
    elif t > 1:
        t, s = 1.0, max(0.0, min(1.0, (bb-dd)/aa))
    return p+u*s, a+v*t, s, t


def crossings(paths, radius):
    """Return transverse crossings, deduplicated along both rope arc lengths."""
    found = []
    names = list(paths)
    radii = radius if isinstance(radius, dict) else {name: radius for name in names}
    lengths = {name: cumulative(paths[name]) for name in names}
    for na, name_a in enumerate(names):
        pa = paths[name_a]
        for name_b in names[na:]:
            pb = paths[name_b]
            radius = max(radii[name_a], radii[name_b])
            la, lb = lengths[name_a], lengths[name_b]
            for i, (a, b) in enumerate(zip(pa, pa[1:])):
                for j, (c, d) in enumerate(zip(pb, pb[1:])):
                    if name_a == name_b and (j <= i or abs(la[i]-lb[j]) < radius*8):
                        continue
                    # Cheap bounding box rejection before the segment calculation.
                    if any(max(a[k], b[k])+radius < min(c[k], d[k]) or
                           max(c[k], d[k])+radius < min(a[k], b[k]) for k in range(3)):
                        continue
                    u, v = b-a, d-c
                    if u.length < 1e-9 or v.length < 1e-9:
                        continue
                    if abs(u.normalized().dot(v.normalized())) > .94:
                        continue
                    x, y, s, t = closest_segments(a, b, c, d)
                    if (x-y).length > radius:
                        continue
                    sa = la[i] + s*u.length
                    sb = lb[j] + t*v.length
                    center = (x+y)/2
                    if any(f['a'] == name_a and f['b'] == name_b and
                           abs(f['sa']-sa) < radius*6 and abs(f['sb']-sb) < radius*6
                           for f in found):
                        continue
                    found.append(dict(a=name_a, b=name_b, sa=sa, sb=sb, center=center))
    return found


def point_segment_distance(point, a, b):
    delta = b-a
    t = max(0.0, min(1.0, (point-a).dot(delta)/delta.length_squared)) if delta.length_squared else 0.0
    return (point-a-delta*t).length


def knot_points(center, tangent, normal, radius):
    """A closed trefoil knot: a visible geometric knot, not a physics constraint."""
    x = tangent.normalized()
    z = normal.normalized()
    y = z.cross(x).normalized()
    if y.length < .1:
        y = x.orthogonal().normalized()
    z = x.cross(y).normalized()
    result = []
    for i in range(128):
        t = 2*math.pi*i/128
        # Standard (2,3) torus knot, sitting above the surface.
        result.append(center + radius*((2+math.cos(3*t))*math.cos(2*t)*x +
                      (2+math.cos(3*t))*math.sin(2*t)*y + (1.6+math.sin(3*t))*z))
    return result
