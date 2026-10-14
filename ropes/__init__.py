bl_info = {
    'name': 'Surface Ropes',
    'author': 'Ropes contributors',
    'version': (0, 2, 0),
    'blender': (4, 4, 0),
    'location': '3D View > Sidebar > Ropes',
    'description': 'Draw ropes on a mesh, create crossings and knots, and indent the surface',
    'category': 'Object',
}

import json
import math
import uuid
from contextlib import contextmanager

import bpy
from bpy.app.handlers import persistent
from bpy.props import (BoolProperty, CollectionProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, PointerProperty, StringProperty)
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree
from bpy_extras import view3d_utils

from .geometry import (Surface, cumulative, crossings, knot_points,
                       point_segment_distance, sample_at, resample, three_strands, strand_tube)


_UPDATING = 0


@contextmanager
def quiet_updates():
    global _UPDATING
    _UPDATING += 1
    try:
        yield
    finally:
        _UPDATING -= 1


def update_rope(self, context, route=False, crossing=False):
    if _UPDATING or not self.enabled or not self.target or context is None:
        return
    scene = context.scene
    try:
        if route or crossing:
            rebuild(scene, self.target, repath=route)
        else:
            refresh_render(scene, self.target)
        scene.ropes_settings.message = ''
    except (ValueError, RuntimeError) as exc:
        scene.ropes_settings.message = str(exc)


def rope_path_update(self, context):
    update_rope(self, context, route=True)


def rope_width_update(self, context):
    update_rope(self, context, crossing=True)


def rope_render_update(self, context):
    update_rope(self, context)


def active_rope_update(self, context):
    if _UPDATING or not self.active_rope or context is None:
        return
    if self.active_rope.ropes_rope.enabled:
        migrate_rope(context.scene, self.active_rope)



def rope_poll(self, obj):
    return obj.type == 'CURVE' and obj.ropes_rope.enabled


def mesh_poll(self, obj):
    return obj.type == 'MESH' and not obj.get('ropes_generated')


class ROPES_PG_Anchor(bpy.types.PropertyGroup):
    position: FloatVectorProperty(size=3)


class ROPES_PG_Knot(bpy.types.PropertyGroup):
    # Arc length from the start, so extension does not move existing knots.
    distance: FloatProperty(min=0)


class ROPES_PG_Rope(bpy.types.PropertyGroup):
    enabled: BoolProperty(default=False)
    target: PointerProperty(type=bpy.types.Object)
    anchors: CollectionProperty(type=ROPES_PG_Anchor)
    knots: CollectionProperty(type=ROPES_PG_Knot)
    uid: StringProperty()
    order: IntProperty(default=0)
    initialized: BoolProperty(default=False)
    radius: FloatProperty(name='Width (Radius)', default=.025, min=.001, soft_max=.2,
                          subtype='DISTANCE', update=rope_width_update)
    subdivisions: IntProperty(name='Routing Detail', default=2, min=0, max=6,
                             update=rope_path_update)
    smoothing: FloatProperty(name='Path Smoothing', default=1, min=0, max=1,
                            update=rope_path_update,
                            description='0 follows mesh edges; 1 relaxes toward a straight surface path')
    squish: FloatProperty(name='Squishiness', default=0, min=0, max=1, update=rope_render_update)
    tension: FloatProperty(name='Tightness', default=.5, min=0, max=1, update=rope_render_update)
    falloff: FloatProperty(name='Indent Width', default=4, min=1, max=20, update=rope_render_update)
    strand_pitch: FloatProperty(name='Twist Pitch', default=12, min=6, max=30,
                               update=rope_render_update,
                               description='Strand twist length in multiples of rope radius')


class ROPES_PG_Junction(bpy.types.PropertyGroup):
    rope_a: PointerProperty(type=bpy.types.Object)
    rope_b: PointerProperty(type=bpy.types.Object)
    position: FloatVectorProperty(size=3)
    distance_a: FloatProperty()
    distance_b: FloatProperty()
    is_knot: BoolProperty(default=False)
    over_a: BoolProperty(default=True)
    uid: StringProperty()


class ROPES_PG_Settings(bpy.types.PropertyGroup):
    target: PointerProperty(type=bpy.types.Object, poll=mesh_poll)
    active_rope: PointerProperty(type=bpy.types.Object, poll=rope_poll, update=active_rope_update)
    radius: FloatProperty(name='Rope Radius', default=.025, min=.001, soft_max=.2,
                          subtype='DISTANCE')
    subdivisions: IntProperty(name='Routing Detail', default=2, min=0, max=6)
    smoothing: FloatProperty(name='Path Smoothing', default=1, min=0, max=1)
    strand_pitch: FloatProperty(name='Twist Pitch', default=12, min=6, max=30)
    show_defaults: BoolProperty(name='New Rope Defaults', default=False)
    squish: FloatProperty(name='Squishiness', default=0, min=0, max=1)
    tension: FloatProperty(name='Tightness', default=.5, min=0, max=1)
    falloff: FloatProperty(name='Indent Width', default=4, min=1, max=20)
    junctions: CollectionProperty(type=ROPES_PG_Junction)
    message: StringProperty()
    active_junction: IntProperty(default=0, min=0)


COPY_SETTINGS = ('radius', 'subdivisions', 'squish', 'tension', 'falloff', 'smoothing', 'strand_pitch')


def migrate_rope(scene, rope):
    props = rope.ropes_rope
    if props.initialized:
        return
    with quiet_updates():
        for name in COPY_SETTINGS:
            setattr(props, name, getattr(scene.ropes_settings, name))
        # Retain the original routing of a 0.1 scene until smoothing is requested.
        props.smoothing = 0
        props.initialized = True


@persistent
def migrate_on_load(_):
    with quiet_updates():
        for scene in bpy.data.scenes:
            for obj in scene.objects:
                if obj.type == 'CURVE' and obj.ropes_rope.enabled:
                    migrate_rope(scene, obj)



def rope_objects(scene, target):
    return sorted((o for o in scene.objects if o.type == 'CURVE' and
                   o.ropes_rope.enabled and o.ropes_rope.target == target),
                  key=lambda o: o.ropes_rope.order)


def generated_collection(scene):
    # Only reuse a collection we created; never adopt a user's named collection.
    for col in scene.collection.children:
        if col.get('ropes_collection'):
            return col
    col = bpy.data.collections.new('Surface Ropes')
    col['ropes_collection'] = True
    scene.collection.children.link(col)
    return col


def material():
    name = 'Surface Ropes · Natural Fiber 0.2'
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (.45, .29, .13, 1)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value = .85
    bsdf.inputs['Sheen Weight'].default_value = .22
    tex = nodes.new('ShaderNodeTexCoord')
    grain = nodes.new('ShaderNodeTexNoise')
    grain.name = 'Natural color variation'
    grain.inputs['Scale'].default_value = 35
    grain.inputs['Detail'].default_value = 3
    links.new(tex.outputs['UV'], grain.inputs['Vector'])
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = .15
    ramp.color_ramp.elements[0].color = (.20, .105, .04, 1)
    ramp.color_ramp.elements[1].position = .85
    ramp.color_ramp.elements[1].color = (.63, .43, .21, 1)
    links.new(grain.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    stretch = nodes.new('ShaderNodeVectorMath')
    stretch.operation = 'MULTIPLY'
    stretch.inputs[1].default_value = (8, 1200, 1)
    links.new(tex.outputs['UV'], stretch.inputs[0])
    fibers = nodes.new('ShaderNodeTexNoise')
    fibers.name = 'Longitudinal natural fibers'
    fibers.inputs['Scale'].default_value = 1
    fibers.inputs['Detail'].default_value = 2
    links.new(stretch.outputs['Vector'], fibers.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .32
    bump.inputs['Distance'].default_value = .0005
    links.new(fibers.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def new_curve(scene, target, name):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 1
    data.bevel_resolution = 3
    data.use_fill_caps = True
    data.materials.append(material())
    obj = bpy.data.objects.new(name, data)
    generated_collection(scene).objects.link(obj)
    obj['ropes_generated'] = True
    obj.parent = target
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = Matrix.Identity(4)
    return obj


def set_curve(obj, points, radius, cyclic=False):
    obj.data.splines.clear()
    if len(points) < 2:
        return
    inverse = obj.parent.matrix_world.inverted_safe()
    spline = obj.data.splines.new('POLY')
    spline.points.add(len(points)-1)
    for p, world in zip(spline.points, points):
        local = inverse @ world
        p.co = (*local, 1)
    spline.use_cyclic_u = cyclic
    # Blender's bevel is in object space. Uniform scale is supported exactly.
    scale = sum(obj.parent.matrix_world.to_scale())/3
    obj.data.bevel_depth = radius/max(abs(scale), 1e-6)


def new_strand(scene, target, name):
    data = bpy.data.meshes.new(name)
    data.materials.append(material())
    obj = bpy.data.objects.new(name, data)
    generated_collection(scene).objects.link(obj)
    obj.parent = target
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = Matrix.Identity(4)
    obj['ropes_generated'] = True
    return obj


def set_strand(obj, points, rope_radius):
    vertices, faces, face_uvs = strand_tube(points, rope_radius*.46, rope_radius)
    inverse = obj.parent.matrix_world.inverted_safe()
    mesh = obj.data
    mesh.clear_geometry()
    mesh.from_pydata([inverse @ p for p in vertices], [], faces)
    for layer in list(mesh.uv_layers):
        mesh.uv_layers.remove(layer)
    uv = mesh.uv_layers.new(name='FiberUV')
    for polygon, coordinates in zip(mesh.polygons, face_uvs):
        polygon.use_smooth = polygon.loop_total == 4
        for loop, coordinate in zip(polygon.loop_indices, coordinates):
            uv.data[loop].uv = coordinate
    obj['ropes_tube_radius'] = rope_radius*.46
    mesh.update()


def new_rope(scene, target):
    order = max((o.ropes_rope.order for o in rope_objects(scene, target)), default=-1)+1
    obj = new_curve(scene, target, 'Rope')
    with quiet_updates():
        for name in COPY_SETTINGS:
            setattr(obj.ropes_rope, name, getattr(scene.ropes_settings, name))
        obj.ropes_rope.initialized = True
    obj.ropes_rope.enabled = True
    obj.ropes_rope.target = target
    obj.ropes_rope.uid = uuid.uuid4().hex
    obj.ropes_rope.order = order
    scene.ropes_settings.active_rope = obj
    return obj


def rest_path(rope):
    target = rope.ropes_rope.target
    return [target.matrix_world @ Vector(p) for p in json.loads(rope.get('ropes_path', '[]'))]


def visible_path(rope):
    if not rope.data.splines:
        return []
    return [rope.matrix_world @ Vector(p.co[:3]) for p in rope.data.splines[0].points]


def rebuild(scene, target, repath=True):
    settings = scene.ropes_settings
    surfaces = {}
    surface = Surface(target, 0)
    ropes = rope_objects(scene, target)
    paths = {}
    inverse = target.matrix_world.inverted_safe()
    for rope in ropes:
        migrate_rope(scene, rope)
        if not repath and rope.get('ropes_path'):
            path = rest_path(rope)
            if len(path) > 1:
                paths[rope.name] = path
            continue
        detail = rope.ropes_rope.subdivisions
        if detail not in surfaces:
            surfaces[detail] = Surface(target, detail)
        routing = surfaces[detail]
        anchors = [target.matrix_world @ Vector(a.position) for a in rope.ropes_rope.anchors]
        path = []
        for a, b in zip(anchors, anchors[1:]):
            leg = routing.route(a, b, rope.ropes_rope.smoothing)
            path.extend(leg if not path else leg[1:])
        rope['ropes_path'] = json.dumps([list(inverse @ p) for p in path])
        if len(path) > 1:
            paths[rope.name] = path
    active_uid = (settings.junctions[settings.active_junction].uid
                  if settings.active_junction < len(settings.junctions) else None)
    old = [dict(a=j.rope_a, b=j.rope_b, p=Vector(j.position), knot=j.is_knot,
                over_a=j.over_a, uid=j.uid)
           for j in settings.junctions if j.rope_a and j.rope_a.ropes_rope.target == target]
    for index in reversed(range(len(settings.junctions))):
        j = settings.junctions[index]
        if j.rope_a is None or j.rope_a.ropes_rope.target == target:
            settings.junctions.remove(index)
    radii = {r.name: r.ropes_rope.radius for r in ropes}
    for crossing in crossings(paths, radii):
        j = settings.junctions.add()
        j.rope_a = scene.objects[crossing['a']]
        j.rope_b = scene.objects[crossing['b']]
        j.position = inverse @ crossing['center']
        j.distance_a, j.distance_b = crossing['sa'], crossing['sb']
        j.uid = uuid.uuid4().hex
        matches = [o for o in old if o['a'] == j.rope_a and o['b'] == j.rope_b and
                   (target.matrix_world @ o['p']-crossing['center']).length <
                   max(radii[j.rope_a.name], radii[j.rope_b.name])*8]
        if matches:
            match = min(matches, key=lambda o: (target.matrix_world @ o['p']-crossing['center']).length)
            j.is_knot, j.uid, j.over_a = match['knot'], match['uid'], match['over_a']
    if active_uid:
        for i, junction in enumerate(settings.junctions):
            if junction.uid == active_uid:
                settings.active_junction = i
                break
    render_ropes(scene, target, surface, ropes, paths)


def refresh_render(scene, target):
    surface = Surface(target, 0)
    ropes = rope_objects(scene, target)
    for rope in ropes:
        migrate_rope(scene, rope)
    paths = {r.name: rest_path(r) for r in ropes if len(rest_path(r)) > 1}
    render_ropes(scene, target, surface, ropes, paths)


def render_ropes(scene, target, surface, ropes, paths):
    settings = scene.ropes_settings
    pressure = PressureField(scene, target)
    helpers = {(o.get('ropes_owner'), o.get('ropes_strand')): o for o in scene.objects
               if o.get('ropes_helper') and o.parent == target}
    used_helpers = set()
    for rope in ropes:
        radius = rope.ropes_rope.radius
        path = paths.get(rope.name, [])
        if not path:
            set_curve(rope, [], radius)
            continue
        lengths = cumulative(path)
        rendered = []
        junctions = [j for j in settings.junctions if
                     (j.rope_a == rope and j.over_a) or (j.rope_b == rope and not j.over_a)]
        for p, s in zip(path, lengths):
            _, normal, _ = surface.project(p)
            lift = radius*1.05 - pressure.value(p)
            for j in junctions:
                # The first rope stays over by default; the new rope passes under.
                station = j.distance_a if j.over_a else j.distance_b
                delta = abs(s-station)
                under = j.rope_b if j.over_a else j.rope_a
                under_radius = under.ropes_rope.radius
                span = max(radius, under_radius)*6
                if delta < span:
                    lift += (under_radius*2.1+radius*.1)*.5*(1+math.cos(math.pi*delta/span))
            rendered.append(p + normal*lift)
        knot_stations = [k.distance for k in rope.ropes_rope.knots]
        for j in settings.junctions:
            if j.is_knot:
                if j.over_a and j.rope_a == rope:
                    knot_stations.append(j.distance_a)
                elif not j.over_a and j.rope_b == rope:
                    knot_stations.append(j.distance_b)
        rendered, stations = insert_knots(scene, surface, path, lengths, rendered,
                                          knot_stations, radius, pressure)
        set_curve(rope, rendered, radius)
        rope['ropes_stations'] = json.dumps(stations)
        # The editable rope keeps its centerline for picking. Three visible
        # helical strands supply the silhouette and the fiber material.
        rope.data.bevel_depth = 0
        for index, strand in enumerate(three_strands(rendered, radius, rope.ropes_rope.strand_pitch)):
            key = (rope.ropes_rope.uid, index)
            helper = helpers.get(key)
            if helper is not None and helper.type != 'MESH':
                delete_rope(helper)
                helper = None
            if helper is None:
                helper = new_strand(scene, target, f'{rope.name} · Strand {index+1}')
            helper['ropes_helper'] = True
            helper['ropes_owner'] = rope.ropes_rope.uid
            helper['ropes_strand'] = index
            used_helpers.add(helper)
            set_strand(helper, strand, radius)
    for helper in list(scene.objects):
        if helper.get('ropes_helper') and helper.parent == target and helper not in used_helpers:
            delete_rope(helper)
    deform(scene, target, pressure)
    bpy.context.view_layer.update()
    settings.message = ''


def insert_knots(scene, surface, path, lengths, rendered, knot_stations, radius, pressure):
    # Splice an open trefoil into the actual curve, with connected entering and
    # exiting leads. Arc stations remain mapped to the undeformed surface path.
    knots = sorted(set(max(0, min(lengths[-1], s)) for s in knot_stations))
    if not knots:
        return rendered, lengths
    result, stations = [], []
    i = 0
    for station in knots:
        low, high = max(0, station-radius*6), min(lengths[-1], station+radius*6)
        while i < len(lengths) and lengths[i] < low:
            result.append(rendered[i])
            stations.append(lengths[i])
            i += 1
        center, tangent = sample_at(path, lengths, station)
        _, normal, _ = surface.project(center)
        p, _ = sample_at(path, lengths, low)
        _, n, _ = surface.project(p)
        result.append(p+n*(radius*1.05-pressure.value(p)))
        stations.append(low)
        loop = knot_points(center+normal*(radius-pressure.value(center)), tangent, normal, radius*1.5)
        # The omitted closing edge opens the trefoil so it belongs to this rope.
        result.extend(loop)
        stations.extend([station]*len(loop))
        p, _ = sample_at(path, lengths, high)
        _, n, _ = surface.project(p)
        result.append(p+n*(radius*1.05-pressure.value(p)))
        stations.append(high)
        while i < len(lengths) and lengths[i] <= high:
            i += 1
    result.extend(rendered[i:])
    stations.extend(lengths[i:])
    return result, stations


class PressureField:
    """Combine per-rope contact masks without sharing any rope's settings."""
    def __init__(self, scene, target):
        self.contacts = []
        for rope in rope_objects(scene, target):
            props = rope.ropes_rope
            depth = props.radius*2*props.squish*props.tension
            path = rest_path(rope)
            if depth <= 0 or len(path) < 2:
                continue
            width = props.radius*props.falloff
            segments = list(zip(path, path[1:]))
            samples = [(point, i) for i, (a, b) in enumerate(segments)
                       for point in resample([a, b], width/2)]
            tree = KDTree(len(samples))
            for i, (point, _) in enumerate(samples):
                tree.insert(point, i)
            tree.balance()
            self.contacts.append((tree, samples, segments, width, depth))

    def value(self, point):
        result = 0.0
        for tree, samples, segments, width, depth in self.contacts:
            candidates = {samples[i][1] for _, i, _ in tree.find_n(point, min(8, len(samples)))}
            distance = min(point_segment_distance(point, *segments[i]) for i in candidates)
            if distance < width*3:
                result = max(result, depth*math.exp(-2*(distance/width)**2))
        return result


def deform(scene, target, pressure=None):
    pressure = pressure or PressureField(scene, target)
    key_name = target.get('ropes_compression_key')
    keys = target.data.shape_keys
    if not pressure.contacts:
        if key_name and keys and key_name in keys.key_blocks:
            keys.key_blocks[key_name].value = 0
        return
    if target.data.users > 1:
        raise ValueError('Make the surface mesh single-user before enabling squishiness.')
    if keys and not keys.use_relative:
        raise ValueError('Squishiness requires relative shape keys.')
    if not keys:
        target.shape_key_add(name='Basis', from_mix=False)
        keys = target.data.shape_keys
    if not key_name or key_name not in keys.key_blocks:
        key = target.shape_key_add(name='Ropes Compression', from_mix=False)
        key_name = key.name
        target['ropes_compression_key'] = key_name
    key = target.data.shape_keys.key_blocks[key_name]
    basis = target.data.shape_keys.reference_key
    inverse = target.matrix_world.inverted_safe()
    normal_matrix = target.matrix_world.to_3x3().inverted_safe().transposed()
    for vertex, base, output in zip(target.data.vertices, basis.data, key.data):
        p = target.matrix_world @ base.co
        normal = (normal_matrix @ vertex.normal).normalized()
        output.co = inverse @ (p-normal*pressure.value(p))
    key.value = 1
    target.data.update()


def knot_at(scene, rope, distance):
    """Toggle crossing knot first; otherwise toggle a manual knot at this station."""
    settings = scene.ropes_settings
    target = rope.ropes_rope.target
    radius = rope.ropes_rope.radius
    junctions = [j for j in settings.junctions if
                 (j.rope_a == rope and abs(j.distance_a-distance) < radius*7) or
                 (j.rope_b == rope and abs(j.distance_b-distance) < radius*7)]
    if junctions:
        j = min(junctions, key=lambda j: min(
            [abs(j.distance_a-distance)] if j.rope_b != rope else
            [abs(j.distance_b-distance)] if j.rope_a != rope else
            [abs(j.distance_a-distance), abs(j.distance_b-distance)]))
        j.is_knot = not j.is_knot
        settings.active_junction = list(settings.junctions).index(j)
    else:
        knots = rope.ropes_rope.knots
        closest = next((i for i, k in enumerate(knots) if abs(k.distance-distance) < radius*5), None)
        if closest is not None:
            knots.remove(closest)
        else:
            knots.add().distance = distance
    rebuild(scene, target, repath=False)


class ROPES_OT_Rebuild(bpy.types.Operator):
    bl_idname = 'ropes.rebuild'
    bl_label = 'Rebuild Ropes'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target = context.scene.ropes_settings.target
        if not target:
            self.report({'ERROR'}, 'Choose a surface mesh first.')
            return {'CANCELLED'}
        try:
            rebuild(context.scene, target)
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


class ROPES_OT_UseSelected(bpy.types.Operator):
    bl_idname = 'ropes.use_selected'
    bl_label = 'Use Selected Surface'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not mesh_poll(None, obj):
            self.report({'ERROR'}, 'Select the mesh you want to wrap.')
            return {'CANCELLED'}
        context.scene.ropes_settings.target = obj
        return {'FINISHED'}


def screen_pick(context, event, ropes, region=None, rv3d=None):
    region = region or context.region
    rv3d = rv3d or context.region_data
    mouse = Vector((event.mouse_x-region.x, event.mouse_y-region.y))
    best = None
    best_distance = 16.0
    for rope in ropes:
        path = visible_path(rope)
        rest = rest_path(rope)
        if len(path) < 2 or len(rest) < 2:
            continue
        lengths = json.loads(rope.get('ropes_stations', '[]'))
        if len(lengths) != len(path):
            continue
        for i, (a, b) in enumerate(zip(path, path[1:])):
            sa = view3d_utils.location_3d_to_region_2d(region, rv3d, a)
            sb = view3d_utils.location_3d_to_region_2d(region, rv3d, b)
            if sa is None or sb is None:
                continue
            delta = sb-sa
            t = max(0.0, min(1.0, (mouse-sa).dot(delta)/delta.length_squared)) if delta.length_squared else 0
            d = (mouse-sa-delta*t).length
            if d < best_distance:
                best_distance = d
                best = rope, lengths[i]+t*(lengths[i+1]-lengths[i])
    return best


def capture_state(scene, target, current_rope=None):
    states = []
    for rope in rope_objects(scene, target):
        states.append(dict(uid=rope.ropes_rope.uid, name=rope.name,
                           order=rope.ropes_rope.order,
                           anchors=[tuple(a.position) for a in rope.ropes_rope.anchors],
                           knots=[k.distance for k in rope.ropes_rope.knots],
                           props={name: getattr(rope.ropes_rope, name) for name in COPY_SETTINGS},
                           path=rope.get('ropes_path', '[]')))
    junctions = [dict(a=j.rope_a.ropes_rope.uid, b=j.rope_b.ropes_rope.uid,
                      position=tuple(j.position), sa=j.distance_a, sb=j.distance_b,
                      knot=j.is_knot, over_a=j.over_a, uid=j.uid)
                 for j in scene.ropes_settings.junctions if
                 j.rope_a and j.rope_b and j.rope_a.ropes_rope.target == target]
    active = scene.ropes_settings.active_rope
    return dict(ropes=states, junctions=junctions,
                active=active.ropes_rope.uid if active else None,
                current=current_rope.ropes_rope.uid if current_rope else None)


def delete_rope(rope):
    data = rope.data
    bpy.data.objects.remove(rope, do_unlink=True)
    if data.users == 0:
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        else:
            bpy.data.curves.remove(data)


def restore_state(scene, target, state):
    with quiet_updates():
        existing = {r.ropes_rope.uid: r for r in rope_objects(scene, target)}
        wanted = {r['uid'] for r in state['ropes']}
        for uid, rope in list(existing.items()):
            if uid not in wanted:
                delete_rope(rope)
                del existing[uid]
        for record in state['ropes']:
            rope = existing.get(record['uid'])
            if rope is None:
                rope = new_rope(scene, target)
                existing[record['uid']] = rope
            props = rope.ropes_rope
            rope.name = record['name']
            props.uid, props.order = record['uid'], record['order']
            for name, value in record['props'].items():
                setattr(props, name, value)
            props.anchors.clear()
            props.knots.clear()
            for point in record['anchors']:
                props.anchors.add().position = point
            for distance in record['knots']:
                props.knots.add().distance = distance
            rope['ropes_path'] = record['path']
        settings = scene.ropes_settings
        for i in reversed(range(len(settings.junctions))):
            j = settings.junctions[i]
            if not j.rope_a or j.rope_a.ropes_rope.target == target:
                settings.junctions.remove(i)
        for record in state['junctions']:
            j = settings.junctions.add()
            j.rope_a, j.rope_b = existing[record['a']], existing[record['b']]
            j.position = record['position']
            j.distance_a, j.distance_b = record['sa'], record['sb']
            j.is_knot, j.over_a, j.uid = record['knot'], record['over_a'], record['uid']
        settings.active_rope = existing.get(state['active'])
    rebuild(scene, target, repath=False)
    return existing.get(state['current'])


def modal_history(operator, context, redo=False):
    source = operator.redo_history if redo else operator.undo_history
    destination = operator.undo_history if redo else operator.redo_history
    if not source:
        operator.report({'INFO'}, 'No more edits to redo.' if redo else 'No more edits to undo in this session.')
        return
    current = capture_state(context.scene, operator.target, operator.rope)
    state = source[-1]
    operator.rope = restore_state(context.scene, operator.target, state)
    source.pop()
    destination.append(current)
    operator.area.tag_redraw()



class ROPES_OT_Draw(bpy.types.Operator):
    bl_idname = 'ropes.draw'
    bl_label = 'Draw / Edit Ropes'
    bl_description = 'Click surface anchors; N starts a rope; right-click a rope toggles a knot'
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}
    extend: BoolProperty(default=False)

    def invoke(self, context, event):
        settings = context.scene.ropes_settings
        target = settings.target
        if context.mode != 'OBJECT' or context.area.type != 'VIEW_3D':
            self.report({'ERROR'}, 'Use Object Mode in a 3D View.')
            return {'CANCELLED'}
        if not target or target.type != 'MESH':
            self.report({'ERROR'}, 'Choose a surface mesh first.')
            return {'CANCELLED'}
        try:
            self.surface = Surface(target, settings.subdivisions)
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.area = context.area
        self.region = next(r for r in self.area.regions if r.type == 'WINDOW')
        self.rv3d = context.space_data.region_3d
        self.target = target
        self.undo_history = []
        self.redo_history = []
        self.rope = settings.active_rope if self.extend else None
        if self.rope and (not self.rope.ropes_rope.enabled or self.rope.ropes_rope.target != target):
            self.rope = None
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set('Ropes: LMB add point · N new rope · RMB on rope knot/crossing · Enter/Esc finish · Ctrl+Z / Backspace undo · Ctrl+Shift+Z redo')
        return {'RUNNING_MODAL'}

    def finish(self, context):
        self.area.header_text_set(None)
        self.area.tag_redraw()
        return {'FINISHED'}

    def modal(self, context, event):
        if event.value == 'PRESS' and ((event.type == 'Z' and getattr(event, 'ctrl', False)) or
                                     event.type == 'BACK_SPACE'):
            try:
                modal_history(self, context, redo=getattr(event, 'shift', False))
            except (ValueError, RuntimeError) as exc:
                self.report({'ERROR'}, str(exc))
            return {'RUNNING_MODAL'}
        if event.type in {'ESC', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            return self.finish(context)
        if event.type == 'N' and event.value == 'PRESS':
            self.rope = None
            return {'RUNNING_MODAL'}
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} or event.alt:
            return {'PASS_THROUGH'}
        if event.value != 'PRESS':
            return {'RUNNING_MODAL'}
        if not (self.region.x <= event.mouse_x < self.region.x+self.region.width and
                self.region.y <= event.mouse_y < self.region.y+self.region.height):
            return {'RUNNING_MODAL'}
        try:
            if event.type == 'RIGHTMOUSE':
                pick = screen_pick(context, event, rope_objects(context.scene, self.target), self.region, self.rv3d)
                if pick:
                    before = capture_state(context.scene, self.target, self.rope)
                    knot_at(context.scene, *pick)
                    self.undo_history.append(before)
                    self.redo_history.clear()
                    context.area.tag_redraw()
                    return {'RUNNING_MODAL'}
                return self.finish(context)
            if event.type == 'LEFTMOUSE':
                origin = view3d_utils.region_2d_to_origin_3d(self.region, self.rv3d,
                                                          (event.mouse_x-self.region.x, event.mouse_y-self.region.y))
                direction = view3d_utils.region_2d_to_vector_3d(self.region, self.rv3d,
                                                             (event.mouse_x-self.region.x, event.mouse_y-self.region.y))
                point, _, _, _ = self.surface.bvh.ray_cast(origin, direction)
                if point is None:
                    self.report({'INFO'}, 'Click on the chosen surface.')
                    return {'RUNNING_MODAL'}
                before = capture_state(context.scene, self.target, self.rope)
                if self.rope is None:
                    self.rope = new_rope(context.scene, self.target)
                anchors = self.rope.ropes_rope.anchors
                if anchors and (self.target.matrix_world @ Vector(anchors[-1].position)-point).length < 1e-5:
                    return {'RUNNING_MODAL'}
                anchor = anchors.add()
                anchor.position = self.target.matrix_world.inverted_safe() @ point
                try:
                    rebuild(context.scene, self.target)
                except (ValueError, RuntimeError):
                    anchors.remove(len(anchors)-1)
                    rebuild(context.scene, self.target)
                    raise
                self.undo_history.append(before)
                self.redo_history.clear()
                context.scene.ropes_settings.active_rope = self.rope
                context.area.tag_redraw()
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
        return {'RUNNING_MODAL'}


class ROPES_OT_Remove(bpy.types.Operator):
    bl_idname = 'ropes.remove'
    bl_label = 'Remove Active Rope'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.ropes_settings
        rope = settings.active_rope
        if not rope or not rope.ropes_rope.enabled:
            return {'CANCELLED'}
        target, data = rope.ropes_rope.target, rope.data
        settings.active_rope = None
        bpy.data.objects.remove(rope, do_unlink=True)
        if data.users == 0:
            bpy.data.curves.remove(data)
        if target:
            try:
                rebuild(context.scene, target)
            except (ValueError, RuntimeError) as exc:
                self.report({'ERROR'}, str(exc))
                return {'CANCELLED'}
        return {'FINISHED'}


class ROPES_OT_RemoveLastPoint(bpy.types.Operator):
    bl_idname = 'ropes.remove_last_point'
    bl_label = 'Remove Last Point'
    bl_description = 'Remove only the last anchor of the active rope, keeping its earlier placements'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rope = context.scene.ropes_settings.active_rope
        if not rope or not rope.ropes_rope.enabled or not rope.ropes_rope.anchors:
            return {'CANCELLED'}
        props = rope.ropes_rope
        props.anchors.remove(len(props.anchors)-1)
        try:
            rebuild(context.scene, props.target)
            path = rest_path(rope)
            total = cumulative(path)[-1] if path else 0
            for index in reversed(range(len(props.knots))):
                if props.knots[index].distance > total:
                    props.knots.remove(index)
            refresh_render(context.scene, props.target)
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


class ROPES_OT_SelectRope(bpy.types.Operator):
    bl_idname = 'ropes.use_selected_rope'
    bl_label = 'Use Selected Rope'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj and obj.get('ropes_owner'):
            obj = next((r for r in context.scene.objects if r.type == 'CURVE' and
                        r.ropes_rope.uid == obj['ropes_owner']), None)
        if not obj or not obj.ropes_rope.enabled:
            self.report({'ERROR'}, 'Select a rope or one of its strands.')
            return {'CANCELLED'}
        settings = context.scene.ropes_settings
        settings.active_rope = obj
        settings.target = obj.ropes_rope.target
        return {'FINISHED'}



class ROPES_UL_Junctions(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        a = item.rope_a.name if item.rope_a else '?'
        b = item.rope_b.name if item.rope_b else '?'
        layout.label(text=f'{a} / {b}', icon='CURVE_DATA' if not item.is_knot else 'LINKED')


class ROPES_OT_SwapCrossing(bpy.types.Operator):
    bl_idname = 'ropes.swap_crossing'
    bl_label = 'Swap Over / Under'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.ropes_settings
        if settings.active_junction >= len(settings.junctions):
            return {'CANCELLED'}
        j = settings.junctions[settings.active_junction]
        if not j.rope_a:
            return {'CANCELLED'}
        j.over_a = not j.over_a
        try:
            rebuild(context.scene, j.rope_a.ropes_rope.target, repath=False)
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


class ROPES_PT_Panel(bpy.types.Panel):
    bl_label = 'Surface Ropes'
    bl_idname = 'ROPES_PT_surface'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Ropes'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.ropes_settings
        layout.prop(settings, 'target', text='Surface')
        layout.operator('ropes.use_selected', icon='EYEDROPPER')
        layout.operator('ropes.draw', text='Draw New Rope', icon='CURVE_DATA').extend = False
        layout.prop(settings, 'active_rope', text='Active Rope')
        layout.operator('ropes.use_selected_rope', icon='EYEDROPPER')
        rope = settings.active_rope
        if rope and rope.ropes_rope.enabled:
            props = rope.ropes_rope
            box = layout.box()
            box.label(text=rope.name)
            box.prop(props, 'radius')
            box.prop(props, 'smoothing', slider=True)
            box.prop(props, 'subdivisions')
            box.prop(props, 'strand_pitch')
            box.prop(props, 'squish', slider=True)
            box.prop(props, 'tension', slider=True)
            box.prop(props, 'falloff')
        layout.operator('ropes.draw', text='Extend / Edit Ropes').extend = True
        layout.operator('ropes.remove_last_point', icon='LOOP_BACK')
        layout.operator('ropes.rebuild', icon='FILE_REFRESH')
        layout.operator('ropes.remove', icon='TRASH')
        if settings.junctions:
            layout.template_list('ROPES_UL_Junctions', '', settings, 'junctions',
                                 settings, 'active_junction', rows=3)
            layout.operator('ropes.swap_crossing', icon='SORT_ASC')
        layout.prop(settings, 'show_defaults', icon='TRIA_DOWN' if settings.show_defaults else 'TRIA_RIGHT')
        if settings.show_defaults:
            box = layout.box()
            for name in COPY_SETTINGS:
                box.prop(settings, name)
        if settings.message:
            layout.label(text=settings.message, icon='ERROR')
        layout.label(text='LMB: add surface point')
        layout.label(text='N: start another rope')
        layout.label(text='RMB rope: knot / junction')
        layout.label(text='Ctrl+Z / Backspace: undo')
        layout.label(text='Ctrl+Shift+Z: redo')
        layout.label(text='Enter / Esc: finish')


CLASSES = (ROPES_PG_Anchor, ROPES_PG_Knot, ROPES_PG_Rope, ROPES_PG_Junction,
           ROPES_PG_Settings, ROPES_OT_Rebuild, ROPES_OT_UseSelected,
           ROPES_OT_Draw, ROPES_OT_Remove, ROPES_OT_RemoveLastPoint,
           ROPES_OT_SelectRope, ROPES_UL_Junctions,
           ROPES_OT_SwapCrossing, ROPES_PT_Panel)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.ropes_rope = PointerProperty(type=ROPES_PG_Rope)
    bpy.types.Scene.ropes_settings = PointerProperty(type=ROPES_PG_Settings)
    bpy.app.handlers.load_post.append(migrate_on_load)
    migrate_on_load(None)


def unregister():
    if migrate_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(migrate_on_load)
    del bpy.types.Scene.ropes_settings
    del bpy.types.Object.ropes_rope
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
