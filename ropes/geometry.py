"""Surface routing and rope geometry. Runs inside Blender without UI dependencies."""
import heapq
import math

import bmesh
from mathutils import Vector
from mathutils.geometry import barycentric_transform
from mathutils.bvhtree import BVHTree


class Surface:
    """World-space routing graph on a subdivided copy of the undeformed mesh."""

    def __init__(self, obj, subdivisions=2, routing=True):
        self.obj = obj
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        if routing and len(bm.faces)*(subdivisions+1)**2 > 500000:
            bm.free()
            raise ValueError('Routing graph is too large. Reduce Routing Detail or simplify the mesh.')
        if subdivisions:
            bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=subdivisions,
                                      use_grid_fill=True)
            bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.normal_update()
        self.closed = all(len(e.link_faces) == 2 for e in bm.edges)
        self.vertices = [obj.matrix_world @ v.co for v in bm.verts]
        self.faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        normal_matrix=obj.matrix_world.to_3x3().inverted_safe().transposed()
        self.normals=[(normal_matrix @ v.normal).normalized() for v in bm.verts]
        self.sharp_edges=[]
        self.convex_edges=[]
        self.convex_normals=[]
        for edge in (bm.edges if routing else []):
            if len(edge.link_faces)==2:
                na,nb=[(normal_matrix @ face.normal).normalized() for face in edge.link_faces]
                if na.dot(nb)<math.cos(math.radians(45)):
                    segment=tuple(self.vertices[v.index] for v in edge.verts)
                    self.sharp_edges.append(segment)
                    fa,fb=edge.link_faces
                    if fa.normal.dot(fb.calc_center_median()-fa.calc_center_median()) < -1e-7:
                        self.convex_edges.append(segment)
                        self.convex_normals.append((na+nb).normalized())
        self.adjacency = [[] for _ in self.vertices]
        for edge in (bm.edges if routing else []):
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

    def inside(self, point):
        if not self.closed:
            return False
        direction=Vector((.812381,.371193,.449157)).normalized()
        origin=Vector(point)
        count=0
        for _ in range(256):
            hit,_,_,_=self.bvh.ray_cast(origin,direction)
            if hit is None:
                return count%2==1
            count+=1
            origin=hit+direction*1e-6
        return True

    def normal_at(self, point):
        co,normal,face=self.project(point)
        # Flat crease faces must not inherit a tangential component from
        # averaged corner-vertex normals. At the edge use its actual bisector.
        planar=[(point_segment_distance(co,a,b),i) for i,(a,b) in enumerate(self.convex_edges)
                if abs((co-a).dot(normal))<1e-6 and abs((b-a).dot(normal))<1e-6]
        if planar:
            gap,index=min(planar)
            return self.convex_normals[index] if gap<1e-6 else normal
        ids=self.faces[face]
        direction=barycentric_transform(co,*(self.vertices[i] for i in ids),
                                        *(self.normals[i] for i in ids))
        if direction.length<1e-8 or direction.dot(normal)<.05:
            direction=normal
        return direction.normalized()

    def contact(self, point, radius):
        """Continuous offset direction with enough room on both sides of a crease."""
        co,normal,face=self.project(point)
        direction=self.normal_at(co)
        # A smoothed vertex normal on a flat face has an arbitrary component
        # along the edge. It must not steer the route sideways around a crease.
        nearby=[(point_segment_distance(co,a,b),i) for i,(a,b) in enumerate(self.convex_edges)]
        if nearby:
            gap,index=min(nearby)
            if gap<radius*3:
                direction=self.convex_normals[index] if gap<1e-6 else normal
        height=radius*1.05
        for _ in range(12):
            candidate=co+direction*height
            near,n,_=self.project(candidate)
            gap=(candidate-near).length
            if gap>=radius*1.045 and (candidate-near).dot(n)>=0:
                return candidate
            height+=max(radius*.02,radius*1.05-gap)/max(direction.dot(n),.1)
        return co+normal*radius*1.05

    def route(self, start, end, smoothing=1.0):
        start, _, sf = self.project(start)
        end, _, ef = self.project(end)
        if sf == ef:
            return uniform_samples([start, end], 100)
        shortcut=self.unfolded_edge_route(start,end)
        if smoothing>0 and shortcut is not None:
            if smoothing>=1:
                return edge_route_samples(shortcut)
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
        if shortcut is not None and smoothing>0:
            original=uniform_samples(points,100)
            direct=edge_route_samples(shortcut,100)
            return [self.project(a.lerp(b,smoothing))[0] for a,b in zip(original,direct)]
        return smooth_surface_path(self, points, smoothing)

    def unfolded_edge_route(self,start,end):
        """Exact shortest route across two flat faces sharing a hard edge."""
        _,na,_=self.project(start)
        _,nb,_=self.project(end)
        if abs(na.dot(nb))>.99999:
            return None
        tolerance=max((end-start).length*1e-5,1e-6)
        candidates=[]
        for a,b in self.sharp_edges:
            if any(abs((p-start).dot(na))>tolerance or abs((p-end).dot(nb))>tolerance for p in (a,b)):
                continue
            axis=(b-a).normalized()
            ta,tb=(start-a).dot(axis),(end-a).dot(axis)
            ha,hb=(start-a-axis*ta).length,(end-a-axis*tb).length
            along=(ta*hb+tb*ha)/max(ha+hb,1e-12)
            point=a+axis*max(0,min((b-a).length,along))
            # Check the actual finite faces, not just their infinite planes.
            if all((self.project(p.lerp(q,i/16))[0]-p.lerp(q,i/16)).length<tolerance
                   for p,q in ((start,point),(point,end)) for i in range(17)):
                candidates.append([start,point,end])
        return min(candidates,key=lambda ps:cumulative(ps)[-1]) if candidates else None


def edge_route_samples(points,count=100):
    """Retain the exact fold point instead of replacing it with an inside chord."""
    first=(points[1]-points[0]).length
    second=(points[2]-points[1]).length
    if first<1e-8:
        return uniform_samples(points[1:],count)
    if second<1e-8:
        return uniform_samples(points[:2],count)
    split=max(1,min(count-1,round(count*first/max(first+second,1e-12))))
    return uniform_samples(points[:2],split)+uniform_samples(points[1:],count-split)[1:]


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
    dense = uniform_samples(points,max(2,math.ceil(cumulative(points)[-1]/(radius*.3))))
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
            rotation = last_tangent.rotation_difference(tangent)
            x = rotation @ last_x
            x -= tangent*x.dot(tangent)
            if x.length < 1e-5:
                x = tangent.orthogonal()
            x.normalize()
        y = tangent.cross(x).normalized()
        last_x = x
        last_tangent = tangent.copy()
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
            clearance = radii[name_a]+radii[name_b]
            la, lb = lengths[name_a], lengths[name_b]
            for i, (a, b) in enumerate(zip(pa, pa[1:])):
                for j, (c, d) in enumerate(zip(pb, pb[1:])):
                    if name_a == name_b and (j <= i or abs(la[i]-lb[j]) < radius*8):
                        continue
                    # Cheap bounding box rejection before the segment calculation.
                    if any(max(a[k], b[k])+clearance < min(c[k], d[k]) or
                           max(c[k], d[k])+clearance < min(a[k], b[k]) for k in range(3)):
                        continue
                    u, v = b-a, d-c
                    if u.length < 1e-9 or v.length < 1e-9:
                        continue
                    if abs(u.normalized().dot(v.normalized())) > .94:
                        continue
                    x, y, s, t = closest_segments(a, b, c, d)
                    if (x-y).length > clearance:
                        continue
                    sa = la[i] + s*u.length
                    sb = lb[j] + t*v.length
                    center = (x+y)/2
                    candidate=dict(a=name_a,b=name_b,sa=sa,sb=sb,center=center,ia=i,ib=j,ta=s,tb=t,gap=(x-y).length)
                    match=next((f for f in found if f['a']==name_a and f['b']==name_b
                                and abs(f['sa']-sa)<radius*6 and abs(f['sb']-sb)<radius*6),None)
                    if match is not None:
                        # Choose the actual intersection, not the first nearby
                        # segment to enter the detection envelope.
                        if candidate['gap']<match['gap']-1e-9:
                            match.update(candidate)
                        continue
                    found.append(candidate)
    return found


def point_segment_distance(point, a, b):
    delta = b-a
    t = max(0.0, min(1.0, (point-a).dot(delta)/delta.length_squared)) if delta.length_squared else 0.0
    return (point-a-delta*t).length


def orient_knot_body(points,center,tangent,normal,radius):
    """Rigidly orient the knot's attachment chord along the running rope.

    Roll the whole body onto its most compact surface-facing support plane.
    This changes the actual knot orientation, not just its first few samples.
    """
    origin=(points[0]+points[-1])/2
    axis=(points[-1]-points[0]).normalized()
    up=normal-axis*normal.dot(axis)
    if up.length<1e-8:
        up=axis.orthogonal()
    up.normalize()
    across=up.cross(axis).normalized()
    local=[Vector(((p-origin).dot(axis),(p-origin).dot(across),(p-origin).dot(up))) for p in points]
    best=None
    for i in range(72):
        angle=2*math.pi*i/72
        sine,cosine=math.sin(angle),math.cos(angle)
        heights=[p.y*sine+p.z*cosine for p in local]
        score=(min(heights),-max(heights))
        if best is None or score>best[0]:
            best=(score,sine,cosine)
    _,sine,cosine=best
    floor=min(p.y*sine+p.z*cosine for p in local)
    x=tangent.normalized()
    y=normal.cross(x).normalized()
    z=x.cross(y).normalized()
    return [center+x*p.x+y*(p.y*cosine-p.z*sine)+z*(p.y*sine+p.z*cosine-floor+radius*1.05) for p in local]


def knot_points(center, tangent, normal, radius, kind='OVERHAND',count=180):
    """The single overhand template shared by all three placement cases."""
    x=tangent.normalized();y=normal.cross(x).normalized();z=x.cross(y).normalized()
    result=[]
    for i in range(count):
        t=math.radians(46.5+267*i/(count-1))
        a=(2+math.cos(3*t))*math.cos(2*t)
        b=(2+math.cos(3*t))*math.sin(2*t)
        result.append(center+radius*(-b*.9*x+a*.85*y+(2.3+1.25*math.sin(3*t))*z))
    return orient_knot_body(result,center,x,z,radius)


def overhand_eye(points,tangent,normal):
    """Centre of the bounded eye between the template's projected crossings."""
    x=tangent.normalized();depth=normal.cross(x).normalized();up=x.cross(depth).normalized()
    stride=max(1,len(points)//180)
    points=points[::stride]+([points[-1]] if (len(points)-1)%stride else [])
    crossings=[]
    for i,(a,b) in enumerate(zip(points,points[1:])):
        u=b-a
        for c,d in zip(points[i+2:],points[i+3:]):
            v=d-c;w=c-a
            determinant=u.dot(x)*v.dot(up)-u.dot(up)*v.dot(x)
            if abs(determinant)<1e-12:continue
            t=(w.dot(x)*v.dot(up)-w.dot(up)*v.dot(x))/determinant
            q=(w.dot(x)*u.dot(up)-w.dot(up)*u.dot(x))/determinant
            if 0<t<1 and 0<q<1:
                point=a+u*t
                point-=depth*(point.dot(depth)-(points[0]+points[-1]).dot(depth)*.5)
                if not any((point-p).length<1e-6 for p in crossings):crossings.append(point)
    if len(crossings)<2:
        raise ValueError('Overhand template has no central eye in its attachment frame')
    return sum(crossings,Vector())/len(crossings)


def expand_overhand_eye(points,eye,axis,clearance):
    """Smooth monotone radial opening; preserve the template's crossing order.

    r -> sqrt(r*r + delta) opens the inner chamber without uniformly inflating
    the hemispheres or introducing a local bend/collision projection.
    """
    axis=axis.normalized()
    radial=[p-eye-axis*(p-eye).dot(axis) for p in points]
    minimum=min(r.length for r in radial)
    delta=max(0,clearance*clearance-minimum*minimum)
    result=[]
    for p,r in zip(points,radial):
        if r.length<1e-10:raise ValueError('Passive axis passes through an overhand centreline')
        result.append(p+r*(math.sqrt(r.length_squared+delta)/r.length-1))
    return result


def bezier_join(a, a_tangent, b, b_tangent, count=16):
    distance = (b-a).length*.3
    c = a+a_tangent.normalized()*distance
    d = b-b_tangent.normalized()*distance
    return [(1-t)**3*a+3*(1-t)**2*t*c+3*(1-t)*t*t*d+t**3*b
            for t in (i/count for i in range(1, count))]


def segment_clear(surface, a, b, radius):
    """Conservative sphere tracing plus an exact central-ray intersection check."""
    delta = b-a
    length = delta.length
    if length < 1e-9:
        co, n, _ = surface.project(a)
        return (a-co).length >= radius
    direction = delta/length
    hit, _, _, distance = surface.bvh.ray_cast(a, direction, length)
    if hit is not None and distance < length-1e-7:
        return False
    walked = 0.0
    for _ in range(8192):
        point = a+direction*walked
        co, normal, _ = surface.project(point)
        gap = (point-co).length
        if gap < radius or (surface.closed and (point-co).dot(normal) < -1e-7):
            return False
        if walked >= length:
            return True
        step = max(gap-radius, 1e-7)
        walked = min(length, walked+step*.8)
    return False


def spanning_route(surface, start, end, radius):
    """Shortest verified line first; otherwise shorten a safe outside route."""
    start, sn, _ = surface.project(start)
    end, en, _ = surface.project(end)
    a, b = surface.contact(start,radius), surface.contact(end,radius)
    safe_radius = radius*1.01
    if segment_clear(surface, a, b, safe_radius):
        return uniform_samples([a, b], 100)
    candidates = []
    try:
        base = surface.route(start, end, 1)
        for lift in (2.5, 4, 8):
            points = [surface.project(p)[0]+surface.project(p)[1]*radius*lift for p in base]
            points = [a]+points+[b]
            if all(segment_clear(surface, p, q, safe_radius) for p,q in zip(points,points[1:])):
                candidates.append(points)
                break
    except ValueError:
        pass
    # A bounding-box visibility graph also works across disconnected islands.
    low = Vector(tuple(min(p[k] for p in surface.vertices)-radius*3 for k in range(3)))
    high = Vector(tuple(max(p[k] for p in surface.vertices)+radius*3 for k in range(3)))
    nodes = [a,b]+[Vector((x,y,z)) for x in (low.x,high.x) for y in (low.y,high.y) for z in (low.z,high.z)]
    graph = [[] for _ in nodes]
    for i,p in enumerate(nodes):
        for j in range(i+1,len(nodes)):
            if segment_clear(surface,p,nodes[j],safe_radius):
                weight=(p-nodes[j]).length
                graph[i].append((j,weight))
                graph[j].append((i,weight))
    queue=[(0.0,0)]
    distances={0:0.0}
    previous={}
    while queue:
        distance,node=heapq.heappop(queue)
        if node==1:
            chain=[1]
            while chain[-1] != 0:
                chain.append(previous[chain[-1]])
            candidates.append([nodes[i] for i in reversed(chain)])
            break
        if distance > distances[node]:
            continue
        for other,weight in graph[node]:
            if distance+weight < distances.get(other,float('inf')):
                distances[other]=distance+weight
                previous[other]=node
                heapq.heappush(queue,(distance+weight,other))
    if not candidates:
        raise ValueError('No collision-free span found. Reduce width or move the waypoints.')
    best=min(candidates,key=lambda p:cumulative(p)[-1])
    # Visibility shortcutting never substitutes an unverified chord.
    result=[best[0]]
    i=0
    while i < len(best)-1:
        j=len(best)-1
        while j > i+1 and not segment_clear(surface,best[i],best[j],safe_radius):
            j-=1
        result.append(best[j])
        i=j
    return resample(result,max(radius*.5,cumulative(result)[-1]/600))


def junction_points(center,frame,lead,normal,ra,rb,component,kind='OVERHAND',size=1):
    """The line-knot template, with the passive rope through its expanded eye."""
    body=align_knot_entries(knot_points(Vector(),lead,normal,ra*size,count=720),lead,count=72)
    eye=overhand_eye(body,lead,normal)
    axis=frame.normalized()
    body=expand_overhand_eye(body,eye,axis,(ra+rb)*1.01)
    body=[center+p-eye for p in body]
    if component:
        reach=max(abs((p-center).dot(axis)) for p in body)+ra*3
        return [center+axis*(reach*(2*i/30-1)) for i in range(31)]
    return body


def junction_support_offset(surface,normal,cores,max_shift):
    """Lower a rigid junction until one actual rope run meets the surface.

    Whole-bundle envelopes overestimate vertical thickness when paired runs
    lie side by side. Sphere tracing uses their actual centerlines and radii.
    """
    samples=[(p,radius) for points,radius in cores for p in points]
    if not samples:
        return Vector()
    for p,radius in samples:
        co,n,_=surface.project(p)
        if (p-co).dot(n)<-1e-7 and (not surface.closed or surface.inside(p)):
            return Vector()
    distance=0.0
    tolerance=min(radius for p,radius in samples)*1e-4
    for _ in range(40):
        margin=min((p-normal*distance-surface.project(p-normal*distance)[0]).length-radius*1.05
                   for p,radius in samples)
        if margin<=tolerance or distance>=max_shift:
            break
        # Distance to a surface is 1-Lipschitz, so this step cannot pass
        # through any sampled rope's clearance envelope.
        distance=min(max_shift,distance+margin*.99)
    return -normal*distance


def fair_contact_path(surface, points, radius, amount=1, pinned=(), references=None):
    """Relax an offset path in free space, pushing out only on contact.

    Free/crease sections can bridge small valleys. Supplied ordinary surface
    contacts stay fixed; their routing was already relaxed on the base mesh.
    Index/station correspondence and span endpoint contacts are retained.
    """
    if amount <= 0 or len(points)<3:
        return points
    result=[p.copy() for p in points]
    fixed=set(pinned)|{0,len(points)-1}
    refs=[p.copy() if p is not None else None for p in references] if references is not None else None
    for stride in (6,3,1):
        for _ in range(10):
            updated=[]
            for i,p in enumerate(result):
                if i in fixed:
                    updated.append(p)
                    continue
                a,b=result[max(0,i-stride)],result[min(len(result)-1,i+stride)]
                candidate=p.lerp((a+b)/2,.65*amount)
                if refs is not None and refs[i] is not None:
                    # The surface router has already relaxed these anchors.
                    # Repeatedly projecting an elevated sample chooses one wall
                    # of a valley and walks away from its original contact.
                    candidate=points[i]
                else:
                    co,n,_=surface.project(candidate)
                    signed=(candidate-co).dot(n)
                    if signed<radius*1.05:
                        candidate=candidate+n*(radius*1.05-signed)
                updated.append(candidate)
            result=updated
    return result


def contact_correction(surface,point,radius,reference=None):
    co,n,_=surface.project(point)
    delta=point-co
    gap=delta.length
    # A closest face's infinite plane is not a solid. At edges its signed
    # distance can be negative even when the point is well outside the object.
    inside=delta.dot(n)<-1e-7 and surface.inside(point)
    crossed=False
    if reference is not None and not surface.closed:
        ray=point-reference
        if ray.length>1e-7:
            hit,_,_,dist=surface.bvh.ray_cast(reference,ray.normalized(),ray.length)
            crossed=hit is not None and dist<ray.length-1e-6
    if gap>=radius*1.045 and not inside and not crossed:
        return Vector()
    if inside:
        direction=-delta.normalized() if gap>1e-8 else n
        return co+direction*radius*1.05-point
    if crossed:
        direction=n if n.dot(reference-co)>=0 else -n
        return co+direction*radius*1.05-point
    direction=delta.normalized() if gap>1e-8 else n
    return direction*max(0,radius*1.05-gap)


def round_bends(surface,points,radius,minimum_radius,protected=None):
    """Round tight corners with a local clearance cushion, not an inside miter."""
    if len(points)<3:
        return points
    lengths=cumulative(points)
    bends=[]
    for i,(a,p,b) in enumerate(zip(points,points[1:],points[2:]),1):
        if protected is not None and protected[i]:
            continue
        u,v=p-a,b-p
        cross=u.cross(v).length
        bend_radius=u.length*v.length*(b-a).length/(2*cross) if cross>1e-10 else 1e20
        if bend_radius<minimum_radius and any(point_segment_distance(p,a,b)<radius*3 for a,b in surface.sharp_edges):
            bends.append(lengths[i])
    if not bends and not surface.convex_edges:
        return points
    padding=[]
    for station in lengths:
        d=min((abs(station-b) for b in bends),default=float('inf'))
        t=max(0,min(1,(minimum_radius*5-d)/(minimum_radius*3)))
        padding.append(radius+(minimum_radius-radius)*t*t*(3-2*t))
    result=[p.copy() for p in points]
    for _ in range(60):
        updated=[result[0]]
        for i in range(1,len(result)-1):
            if protected is not None and protected[i]:
                updated.append(result[i])
                continue
            p=result[i].lerp((result[i-1]+result[i+1])/2,.55)
            p+=contact_correction(surface,p,padding[i],result[i])
            updated.append(p)
        result=updated+[result[-1]]
    # Convex edges need a radius-sized offset arc, not a large clearance
    # cushion. Settle every affected sample back onto that offset envelope.
    convex=[i for i,p in enumerate(points) if any(point_segment_distance(p,a,b)<minimum_radius*6 for a,b in surface.convex_edges)
            and not (protected is not None and protected[i])]
    for _ in range(32):
        updated=list(result)
        for i in convex:
            p=result[i]
            if 0<i<len(result)-1:
                p=p.lerp((result[i-1]+result[i+1])/2,.45)
            co,n,_=surface.project(p)
            delta=p-co
            direction=delta.normalized() if delta.length>1e-8 and not surface.inside(p) else n
            updated[i]=co+direction*radius*1.05
        result=updated
    return result


def align_knot_entries(points,tangent,count=18):
    """Preserve the knot core while aligning its two attachment tangents."""
    result=[p.copy() for p in points]
    count=min(count,len(points)//5)
    for incoming in (True,False):
        if incoming:
            a,b=points[0],points[count]
            ta,tb=tangent,points[count+1]-points[count-1]
            indices=range(count)
        else:
            a,b=points[-count-1],points[-1]
            ta,tb=points[-count]-points[-count-2],tangent
            indices=range(len(points)-count-1,len(points))
        scale=(b-a).length*.45
        c=a+ta.normalized()*scale
        d=b-tb.normalized()*scale
        for j,index in enumerate(indices):
            t=j/count
            result[index]=(1-t)**3*a+3*(1-t)**2*t*c+3*(1-t)*t*t*d+t**3*b
    return result
