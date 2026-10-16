bl_info = {
    'name': 'Surface Ropes',
    'author': 'Ropes contributors',
    'version': (0, 12, 2),
    'blender': (4, 4, 0),
    'location': '3D View > Sidebar > Ropes',
    'description': 'Draw single ropes with editable waypoints, snug overhand junction knots and surface compression',
    'category': 'Object',
}

import importlib
import json
import bisect
import math
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import bpy
from bpy.app.handlers import persistent
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, PointerProperty, StringProperty)
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree
from bpy_extras import view3d_utils

# Blender reloads a legacy add-on's entry module during an in-place install,
# but can retain its old child modules. Geometry is pure code with no registered
# Blender state, so it is safe to refresh before importing this version's helpers.
from . import geometry as _geometry
importlib.invalidate_caches()
if hasattr(_geometry,'doubled_path'):delattr(_geometry,'doubled_path')
importlib.reload(_geometry)
for _retired_name in ('fit_junction_runs','snug_junction_curves','separate_knot_leads'):
    globals().pop(_retired_name,None)

from .geometry import (Surface, cumulative, crossings, knot_points,
                       point_segment_distance, sample_at, resample, three_strands, strand_tube, bezier_join, spanning_route, segment_clear, junction_points, fair_contact_path, contact_correction, round_bends, align_knot_entries)


_UPDATING = 0
SCHEMA_VERSION = 12


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
    if not self.generated:
        refresh_draft_markers(scene, self.id_data)
        return
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
    update_rope(self, context, route=any(a.kind=='SPANNING' for a in self.anchors), crossing=True)


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


def centre_material():
    mat=bpy.data.materials.get('Surface Ropes · Centre Curve')
    if mat is None:
        mat=bpy.data.materials.new('Surface Ropes · Centre Curve')
        mat.diffuse_color=(.015,.015,.015,1)
    return mat


def curve_view_update(self,context):
    if context is None:return
    mode=self.curve_view
    for obj in context.scene.objects:
        if obj.get('ropes_helper'):
            obj.hide_set(mode=='CURVES');obj.hide_render=mode=='CURVES'
        elif obj.type=='CURVE' and obj.ropes_rope.enabled:
            scale=max(abs(sum(obj.matrix_world.to_scale())/3),1e-6)
            obj.data.bevel_depth=obj.ropes_rope.radius*(.06 if mode=='CURVES' else .025)/scale if mode!='ROPE' else 0
            obj.show_in_front=mode!='ROPE'


KNOT_TYPES = (('OVERHAND','Overhand','One shared overhand template'),)
KNOT_CHOICES = KNOT_TYPES


def knot_style_update(self, context):
    if _UPDATING or context is None:
        return
    scene = context.scene
    rope = scene.ropes_settings.active_rope
    owner = self.id_data
    target = owner.ropes_rope.target if isinstance(owner, bpy.types.Object) else \
             self.rope_a.ropes_rope.target if hasattr(self, 'rope_a') and self.rope_a else \
             rope.ropes_rope.target if rope else None
    if target:
        try:
            refresh_render(scene, target)
        except (ValueError, RuntimeError) as exc:
            scene.ropes_settings.message = str(exc)


def waypoint_visibility_update(self, context):
    if _UPDATING or context is None:
        return
    targets = {o.ropes_rope.target for o in context.scene.objects if
               o.type == 'CURVE' and o.ropes_rope.enabled and o.ropes_rope.target}
    for target in targets:
        try:
            refresh_markers(context.scene, target)
        except (ValueError, RuntimeError) as exc:
            context.scene.ropes_settings.message = str(exc)


def waypoint_display_update(self,context):
    if _UPDATING or context is None:
        return
    owners={r.ropes_rope.uid:r for r in context.scene.objects if r.type=='CURVE' and r.ropes_rope.enabled and r.ropes_rope.target}
    for marker in context.scene.objects:
        if 'ropes_waypoint' not in marker:
            continue
        rope=owners.get(marker.get('ropes_owner'))
        if rope is None:
            continue
        scale=max(abs(sum(rope.ropes_rope.target.matrix_world.to_scale())/3),1e-6)
        marker.empty_display_size=max(rope.ropes_rope.radius*.85,.015)*self.waypoint_size/scale
        marker.show_in_front=self.waypoint_xray


WAYPOINT_TYPES = (
    ('NORMAL', 'Normal', 'Follow the surface to neighboring points'),
    ('SPANNING', 'Spanning', 'Bridge only when both endpoints are spanning points'),
)


def anchor_kind_update(self, context):
    if _UPDATING or context is None:
        return
    owner=self.id_data
    if isinstance(owner,bpy.types.Object) and owner.ropes_rope.enabled:
        update_rope(owner.ropes_rope,context,route=True)


class ROPES_PG_Anchor(bpy.types.PropertyGroup):
    position: FloatVectorProperty(size=3)
    kind: EnumProperty(name='Waypoint Type', items=WAYPOINT_TYPES, default='NORMAL', update=anchor_kind_update)


class ROPES_PG_Knot(bpy.types.PropertyGroup):
    # Arc length from the start, so extension does not move existing knots.
    distance: FloatProperty(min=0)
    kind: EnumProperty(name='Knot Type', items=KNOT_CHOICES, default='OVERHAND', update=knot_style_update)


class ROPES_PG_Rope(bpy.types.PropertyGroup):
    enabled: BoolProperty(default=False)
    target: PointerProperty(type=bpy.types.Object)
    anchors: CollectionProperty(type=ROPES_PG_Anchor)
    knots: CollectionProperty(type=ROPES_PG_Knot)
    uid: StringProperty()
    order: IntProperty(default=0)
    initialized: BoolProperty(default=False)
    generated: BoolProperty(default=True)
    active_anchor: IntProperty(default=0,min=0)
    knot_type: EnumProperty(name='Default Knot Type', items=KNOT_TYPES, default='OVERHAND', update=rope_render_update)
    knot_size: FloatProperty(name='Knot Size', default=1, min=1, max=2, update=rope_render_update)
    active_knot: IntProperty(default=0, min=0)
    radius: FloatProperty(name='Width (Radius)', default=.025, min=.001, soft_max=.2,
                          subtype='DISTANCE', update=rope_width_update)
    subdivisions: IntProperty(name='Routing Detail', default=2, min=0, max=6,
                             update=rope_path_update)
    smoothing: FloatProperty(name='Path Smoothing', default=1, min=0, max=1,
                            update=rope_path_update,
                            description='0 follows mesh edges; 1 relaxes toward a straight surface path')
    squish: FloatProperty(name='Squishiness', default=0, min=0, max=1, update=rope_render_update)
    tension: FloatProperty(name='Tightness', default=.5, min=0, max=1, update=rope_render_update,
                           description='Normal centerline clearance: 0 is one rope radius, 1 is on the surface; independent of Squishiness')
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
    kind: EnumProperty(name='Junction Knot Type', items=KNOT_CHOICES, default='OVERHAND', update=knot_style_update)
    over_a: BoolProperty(default=True)
    knot_a: BoolProperty(default=True)
    knot_owner_set: BoolProperty(default=False)
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
    waypoint_mode: BoolProperty(name='Waypoint Mode', default=False, description='Place a draft first, then use Generate Rope')
    curve_view: EnumProperty(name='Display',items=(('ROPE','Rope','Braided rope'),
                            ('CURVES','Centre Curves','Hide strands and inspect the generated Bezier centre curves'),
                            ('BOTH','Rope + Curves','Overlay centre curves on the rope')),default='ROPE',update=curve_view_update)
    placement_kind: EnumProperty(name='New Waypoint Type', items=WAYPOINT_TYPES, default='NORMAL')
    show_waypoints: BoolProperty(name='Show Waypoints', default=False, update=waypoint_visibility_update)
    waypoint_size: FloatProperty(name='Waypoint Size',default=.6,min=.05,max=4,update=waypoint_display_update)
    waypoint_xray: BoolProperty(name='Waypoints Through Objects',default=False,update=waypoint_display_update)
    knot_type: EnumProperty(name='Default Knot Type', items=KNOT_TYPES, default='OVERHAND')
    knot_size: FloatProperty(name='Knot Size', default=1, min=1, max=2)
    squish: FloatProperty(name='Squishiness', default=0, min=0, max=1)
    tension: FloatProperty(name='Tightness', default=.5, min=0, max=1)
    falloff: FloatProperty(name='Indent Width', default=4, min=1, max=20)
    junctions: CollectionProperty(type=ROPES_PG_Junction)
    message: StringProperty()
    active_junction: IntProperty(default=0, min=0)


COPY_SETTINGS = ('radius', 'subdivisions', 'squish', 'tension', 'falloff', 'smoothing', 'strand_pitch',
                 'knot_size')


def migrate_rope(scene,rope):
    props=rope.ropes_rope
    with quiet_updates():
        if not props.initialized:
            for name in COPY_SETTINGS:setattr(props,name,getattr(scene.ropes_settings,name))
            props.smoothing=0
            props.initialized=True
        # Retire saved controls as well as their visible UI. Anchors and knot
        # stations are retained when old folded ropes become single ropes.
        for name in ('doubled','double_spacing'):
            if name in props:del props[name]
        props.knot_type='OVERHAND'
        for knot in props.knots:knot.kind='OVERHAND'
        rope['ropes_schema']=SCHEMA_VERSION


@persistent
def migrate_on_load(_):
    pending=[]
    with quiet_updates():
        for scene in bpy.data.scenes:
            for name in ('doubled','double_spacing'):
                if name in scene.ropes_settings:del scene.ropes_settings[name]
            scene.ropes_settings.knot_type='OVERHAND'
            for joint in scene.ropes_settings.junctions:joint.kind='OVERHAND'
            for obj in scene.objects:
                if obj.type=='CURVE' and obj.ropes_rope.enabled:
                    if obj.get('ropes_schema',0)<SCHEMA_VERSION and obj.ropes_rope.target:
                        pair=(scene,obj.ropes_rope.target)
                        if pair not in pending:pending.append(pair)
                    migrate_rope(scene,obj)
    for scene,target in pending:rebuild(scene,target)
    for scene in bpy.data.scenes:
        waypoint_display_update(scene.ropes_settings,SimpleNamespace(scene=scene))
        curve_view_update(scene.ropes_settings,SimpleNamespace(scene=scene))



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
    data.materials.append(centre_material())
    obj = bpy.data.objects.new(name, data)
    generated_collection(scene).objects.link(obj)
    obj['ropes_generated'] = True
    obj.parent = target
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = Matrix.Identity(4)
    return obj


def set_curve(obj, points, radius, cyclic=False):
    obj.data.splines.clear()
    obj.data.materials.clear()
    obj.data.materials.append(centre_material())
    if len(points) < 2:
        return
    inverse = obj.parent.matrix_world.inverted_safe()
    spline = obj.data.splines.new('BEZIER')
    spline.bezier_points.add(len(points)-1)
    for p, world in zip(spline.bezier_points, points):
        p.co = inverse @ world
        p.handle_left_type = p.handle_right_type = 'VECTOR'
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
    obj['ropes_schema'] = SCHEMA_VERSION
    obj.ropes_rope.generated = not scene.ropes_settings.waypoint_mode
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
    spline=rope.data.splines[0]
    points=spline.bezier_points if spline.type=='BEZIER' else spline.points
    return [rope.matrix_world @ Vector(p.co[:3]) for p in points]


def rebuild(scene, target, repath=True):
    settings = scene.ropes_settings
    surfaces = {}
    surface = Surface(target, 0)
    ropes = rope_objects(scene, target)
    paths = {}
    inverse = target.matrix_world.inverted_safe()
    for rope in ropes:
        migrate_rope(scene, rope)
        if not rope.ropes_rope.generated:
            rope['ropes_path']='[]'
            rope['ropes_leg_bounds']='[0]'
            rope['ropes_span_flags']='[]'
            rope['ropes_span_centers']='[]'
            continue
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
        leg_bounds = [0.0]
        span_flags=[]
        overrides=[]
        for index,(a,b) in enumerate(zip(anchors,anchors[1:])):
            span=all(x.kind == 'SPANNING' for x in rope.ropes_rope.anchors[index:index+2])
            leg=spanning_route(routing,a,b,rope.ropes_rope.radius) if span else routing.route(a,b,rope.ropes_rope.smoothing)
            span_flags.append(span)
            extra=[list(inverse @ p) if span else None for p in leg]
            if path:
                if span:
                    overrides[-1]=extra[0]
                path.extend(leg[1:])
                overrides.extend(extra[1:])
            else:
                path.extend(leg)
                overrides.extend(extra)
            leg_bounds.append(cumulative(path)[-1])
        rope['ropes_span_flags']=json.dumps(span_flags)
        rope['ropes_span_centers']=json.dumps(overrides)
        rope['ropes_path'] = json.dumps([list(inverse @ p) for p in path])
        rope['ropes_leg_bounds'] = json.dumps(leg_bounds)
        if len(path) > 1:
            paths[rope.name] = path
    active_uid = (settings.junctions[settings.active_junction].uid
                  if settings.active_junction < len(settings.junctions) else None)
    old = [dict(a=j.rope_a, b=j.rope_b, p=Vector(j.position), knot=j.is_knot,
                over_a=j.over_a, uid=j.uid, kind=j.kind, knot_a=j.knot_a, knot_owner_set=j.knot_owner_set)
           for j in settings.junctions if j.rope_a and j.rope_a.ropes_rope.target == target]
    for index in reversed(range(len(settings.junctions))):
        j = settings.junctions[index]
        if j.rope_a is None or j.rope_a.ropes_rope.target == target:
            settings.junctions.remove(index)
    radii = {r.name: envelope_radius(r) for r in ropes}
    detection={r.name: baseline_path(r,surface,paths[r.name]) for r in ropes if r.name in paths}
    detected = crossings(detection, radii)
    for crossing in detected:
        j = settings.junctions.add()
        j.rope_a = scene.objects[crossing['a']]
        j.rope_b = scene.objects[crossing['b']]
        j.position = inverse @ crossing['center']
        la,lb=cumulative(paths[crossing['a']]),cumulative(paths[crossing['b']])
        ia,ib=crossing['ia'],crossing['ib']
        j.distance_a=la[ia]+crossing['ta']*(la[ia+1]-la[ia])
        j.distance_b=lb[ib]+crossing['tb']*(lb[ib+1]-lb[ib])
        j.uid = uuid.uuid4().hex
        matches = [o for o in old if o['a'] == j.rope_a and o['b'] == j.rope_b and
                   (target.matrix_world @ o['p']-crossing['center']).length <
                   max(radii[j.rope_a.name], radii[j.rope_b.name])*8]
        if not matches:
            pair = [o for o in old if o['a'] == j.rope_a and o['b'] == j.rope_b]
            count = sum(c['a'] == crossing['a'] and c['b'] == crossing['b'] for c in detected)
            if len(pair) == 1 and count == 1:
                matches = pair
        if matches:
            match = min(matches, key=lambda o: (target.matrix_world @ o['p']-crossing['center']).length)
            with quiet_updates():
                j.is_knot, j.uid, j.over_a = match['knot'], match['uid'], match['over_a']
                j.kind = 'OVERHAND'
                j.knot_a,j.knot_owner_set=match['knot_a'],match['knot_owner_set']
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


def envelope_radius(rope):
    props = rope.ropes_rope
    return props.radius



def span_at(rope, station):
    bounds=json.loads(rope.get('ropes_leg_bounds','[]'))
    flags=json.loads(rope.get('ropes_span_flags','[]'))
    if not flags or len(bounds)<2:
        return False
    index=max(0,min(len(flags)-1,bisect.bisect_right(bounds,station+1e-7)-1))
    return flags[index]


def contact_weight(rope, station):
    """Ease indentation to zero where a surface section meets a free span."""
    if span_at(rope,station):
        return 0.0
    bounds=json.loads(rope.get('ropes_leg_bounds','[]'))
    flags=json.loads(rope.get('ropes_span_flags','[]'))
    transitions=[bounds[i] for i in range(1,len(flags)) if flags[i]!=flags[i-1]]
    if not transitions:
        return 1.0
    t=min(1,min(abs(station-b) for b in transitions)/(rope.ropes_rope.radius*8))
    return t*t*t*(10-15*t+6*t*t)


def curve_height(rope):
    return rope.ropes_rope.radius*(1-rope.ropes_rope.tension)


def baseline_path(rope,surface,path):
    overrides=json.loads(rope.get('ropes_span_centers','[]'))
    bounds=json.loads(rope.get('ropes_leg_bounds','[]'))
    flags=json.loads(rope.get('ropes_span_flags','[]'))
    transitions=[bounds[i] for i in range(1,len(bounds)-1) if flags[i-1]!=flags[i]]
    lengths=cumulative(path)
    result=[]
    radius=rope.ropes_rope.radius
    for i,point in enumerate(path):
        if i<len(overrides) and overrides[i] is not None:
            result.append(rope.ropes_rope.target.matrix_world @ Vector(overrides[i]))
        else:
            height=curve_height(rope)
            if transitions:
                blend=max(0,1-min((surface.project(point)[0]-surface.project(sample_at(path,lengths,s)[0])[0]).length for s in transitions)/(radius*5))
                height+=(radius*1.05-height)*blend*blend*(3-2*blend)
            co=surface.project(point)[0]
            result.append(co+surface.normal_at(co)*height)
    return result


def junction_active_a(junction):
    if junction.rope_a==junction.rope_b:
        return junction.over_a
    return junction.knot_a if junction.knot_owner_set else junction.over_a


def knot_extent(record,rope):
    j=record['junction']
    if j:
        active=j.rope_a if junction_active_a(j) else j.rope_b
        return max(envelope_radius(j.rope_a),envelope_radius(j.rope_b))*16*active.ropes_rope.knot_size
    return rope.ropes_rope.radius*14


def knot_records(scene, rope):
    props=rope.ropes_rope
    records=[dict(station=k.distance,kind='OVERHAND',junction=None,component=0)
             for k in props.knots]
    for j in scene.ropes_settings.junctions:
        if not j.is_knot or not j.rope_a or not j.rope_b:
            continue
        active_a=junction_active_a(j)
        owner=j.rope_a if active_a else j.rope_b
        kind='OVERHAND'
        if j.rope_a==rope:
            records.append(dict(station=j.distance_a,kind=kind,junction=j,component=0 if active_a else 1))
        if j.rope_b==rope:
            records.append(dict(station=j.distance_b,kind=kind,junction=j,component=1 if active_a else 0))
    return sorted(records,key=lambda r:r['station'])


def rigid_knot_offset(surface,normal,supports,settle=True):
    """Seat both components with a common translation, never deform the eye."""
    normal=normal.normalized();offset=Vector()
    radius=max(r for curve,r in supports)
    for _ in range(160):
        shift=0.0
        for curve,r in supports:
            for p in curve:
                point=p+offset;co,n,_=surface.project(point)
                signed=(point-co).dot(n)
                if signed<r*1.05:
                    shift=max(shift,min(radius*2,(r*1.05-signed)/max(.2,n.dot(normal))))
        if shift<radius*1e-5:break
        offset+=normal*shift
    else:raise ValueError('Knot cannot seat on this surface; move its waypoint into a clearer area')
    if not settle:return offset
    translated=[([p+offset for p in curve],r) for curve,r in supports]
    return offset+_geometry.junction_support_offset(surface,normal,translated,radius*30)


def insert_knots(scene, surface, path, lengths, rendered, records, rope):
    if not records:
        return rendered, lengths
    props=rope.ropes_rope
    compact=props.radius
    body_radius=compact*props.knot_size
    radius = rope.ropes_rope.radius
    result, stations = [], []
    i = 0
    for record_index,record in enumerate(records):
        station,kind=record['station'],record['kind']
        joint=record['junction']
        body_radius=compact*props.knot_size
        if joint:
            active=joint.rope_a if junction_active_a(joint) else joint.rope_b
            passive=joint.rope_b if junction_active_a(joint) else joint.rope_a
            body_radius=(active.ropes_rope.radius+passive.ropes_rope.radius)*active.ropes_rope.knot_size
        station = max(0, min(lengths[-1], station))
        lead_span=body_radius*(10 if joint else 6)
        low, high = max(0, station-lead_span), min(lengths[-1], station+lead_span)
        if record_index:low=max(low,(station+records[record_index-1]['station'])/2)
        if record_index+1<len(records):high=min(high,(station+records[record_index+1]['station'])/2)
        while i < len(lengths) and lengths[i] < low:
            result.append(rendered[i])
            stations.append(lengths[i])
            i += 1
        center, tangent = sample_at(path, lengths, station)
        _, normal, _ = surface.project(center)
        p, _ = sample_at(path, lengths, low)
        _, n, _ = surface.project(p)
        start_lead=sample_at(baseline_path(rope,surface,path),lengths,low)[0]
        result.append(start_lead)
        stations.append(low)
        if span_at(rope,station):
            center=sample_at(baseline_path(rope,surface,path),lengths,station)[0]-normal*radius*1.05
        if joint:
            world=joint.rope_a.ropes_rope.target.matrix_world @ Vector(joint.position)
            nearest,normal,_=surface.project(world)
            floating=span_at(joint.rope_a,joint.distance_a) or span_at(joint.rope_b,joint.distance_b)
            center=world if floating else nearest
            passive_station=joint.distance_b if junction_active_a(joint) else joint.distance_a
            passive_path=rest_path(passive)
            frame=sample_at(passive_path,cumulative(passive_path),passive_station)[1]
            active_station=joint.distance_a if junction_active_a(joint) else joint.distance_b
            active_path=rest_path(active)
            active_tangent=sample_at(active_path,cumulative(active_path),active_station)[1]
            curves=[junction_points(center,frame,active_tangent,normal,active.ropes_rope.radius,
                                    passive.ropes_rope.radius,component,size=active.ropes_rope.knot_size)
                    for component in (0,1)]
            supports=[(curve,owner.ropes_rope.radius) for owner,curve in zip((active,passive),curves)]
            offset=rigid_knot_offset(surface,normal,supports,settle=not floating)
            loop=[p+offset for p in curves[record['component']]]
        else:
            loop=knot_points(center,tangent,normal,body_radius)
        if not joint:
            loop=align_knot_entries(loop,tangent)
        incoming = bezier_join(result[-1], sample_at(path, lengths, low)[1],
                                loop[0], loop[1]-loop[0])
        result.extend(incoming)
        stations.extend([low+(station-low)*(i+1)/(len(incoming)+1) for i in range(len(incoming))])
        result.extend(loop)
        stations.extend([station]*len(loop))
        p, _ = sample_at(path, lengths, high)
        _, n, _ = surface.project(p)
        end_lead=sample_at(baseline_path(rope,surface,path),lengths,high)[0]
        outgoing = bezier_join(loop[-1], loop[-1]-loop[-2], end_lead,
                                sample_at(path, lengths, high)[1])
        result.extend(outgoing)
        stations.extend([station+(high-station)*(i+1)/(len(outgoing)+1) for i in range(len(outgoing))])
        result.append(end_lead)
        stations.append(high)
        while i < len(lengths) and lengths[i] <= high:
            i += 1
    result.extend(rendered[i:])
    stations.extend(lengths[i:])
    return result, stations


def clearance(surface, points, radius, free=None):
    return [point+contact_correction(surface,point,radius) for point in points]


def support_normals(rope,surface,path,lengths,stations):
    normals=[]
    bounds=json.loads(rope.get('ropes_leg_bounds','[]'))
    anchors=rope.ropes_rope.anchors
    for station in stations:
        if span_at(rope,station) and len(bounds)>1:
            leg=max(0,min(len(bounds)-2,bisect.bisect_right(bounds,station+1e-7)-1))
            a=rope.ropes_rope.target.matrix_world @ Vector(anchors[leg].position)
            b=rope.ropes_rope.target.matrix_world @ Vector(anchors[leg+1].position)
            fraction=max(0,min(1,(station-bounds[leg])/max(bounds[leg+1]-bounds[leg],1e-9)))
            n=surface.normal_at(a).lerp(surface.normal_at(b),fraction)
            normals.append(n.normalized() if n.length>1e-6 else surface.normal_at(a))
        else:
            normals.append(surface.normal_at(sample_at(path,lengths,station)[0]))
    return normals


def fillet_surface_waypoints(rope,surface,points,stations,protected):
    """Round a deliberate waypoint turn along a smooth surface, at contact height."""
    result=list(points)
    references={}
    if rope.ropes_rope.smoothing<=0:
        return result,references
    bounds=json.loads(rope.get('ropes_leg_bounds','[]'))
    flags=json.loads(rope.get('ropes_span_flags','[]'))
    radius=rope.ropes_rope.radius
    reach=radius*4
    for leg,station in enumerate(bounds[1:-1],1):
        if flags[leg-1] or flags[leg]:
            continue
        index=min(len(points)-2,bisect.bisect_left(stations,station))
        if index<1 or protected[index]:
            continue
        incoming=points[index]-points[index-1]
        outgoing=points[index+1]-points[index]
        if incoming.length<1e-8 or outgoing.length<1e-8 or incoming.normalized().dot(outgoing.normalized())>math.cos(math.radians(30)):
            continue
        if any(point_segment_distance(points[index],a,b)<radius*3 for a,b in surface.sharp_edges):
            continue
        lo=max(0,bisect.bisect_left(stations,station-reach))
        hi=min(len(points)-1,bisect.bisect_right(stations,station+reach))
        if hi-lo<3 or any(protected[lo:hi+1]):
            continue
        curve=[points[lo]]+bezier_join(points[lo],points[lo+1]-points[lo],points[hi],points[hi]-points[hi-1],hi-lo)+[points[hi]]
        for i,p in enumerate(curve,lo):
            co=surface.project(p)[0]
            references[i]=co
            result[i]=co+surface.normal_at(co)*curve_height(rope)
    return result,references


def display_path(scene, rope, surface, path):
    radius = rope.ropes_rope.radius
    lengths = cumulative(path)
    rendered=baseline_path(rope,surface,path)
    rendered, stations = insert_knots(scene, surface, path, lengths, rendered,
                                      knot_records(scene, rope), rope)
    records=knot_records(scene,rope)
    constrained=[span_at(rope,s) for s in stations]
    rendered=[p+contact_correction(surface,p,radius) if constrained[i] else p for i,p in enumerate(rendered)]
    protected=[any(abs(station-record['station'])<knot_extent(record,rope) for record in records) for station in stations]
    rendered,fillet_refs=fillet_surface_waypoints(rope,surface,rendered,stations,protected)
    unrounded=rendered
    # Normal routes are curves: thickness is allowed to intersect the surface.
    # Spans and knot bodies retain physical clearance.
    for i,(a,b) in enumerate(zip(rendered,rendered[1:])):
        if span_at(rope,(stations[i]+stations[i+1])/2) and not segment_clear(surface,a,b,radius*1.01):
            raise ValueError('Spanning rope cannot clear the surface at this width. Move its waypoints or reduce width.')
    return rendered, stations


def crossing_strand_segments(owner,points,stations,station,extent):
    """Actual braided axes, retaining their phase from the complete rope."""
    arc=cumulative(points)
    strands=three_strands(points,owner.ropes_rope.radius,owner.ropes_rope.strand_pitch)
    count=len(strands[0])-1
    selected=[]
    for i in range(count):
        distance=arc[-1]*(i+.5)/count
        k=min(len(arc)-2,max(0,bisect.bisect_right(arc,distance)-1))
        t=(distance-arc[k])/max(arc[k+1]-arc[k],1e-12)
        if abs(stations[k]*(1-t)+stations[k+1]*t-station)<extent:
            selected.extend((strand[i],strand[i+1]) for strand in strands)
    return selected


def strand_segment_gap(segments,other):
    """Closest finite fibre axes; KD bounds include each segment's extent."""
    if not segments or not other:return float('inf')
    tree=KDTree(len(other))
    half=max((b-a).length/2 for a,b in other)
    for i,(a,b) in enumerate(other):tree.insert((a+b)/2,i)
    tree.balance()
    best=float('inf')
    for a,b in segments:
        middle=(a+b)/2
        _,nearest,_=tree.find(middle)
        c,d=other[nearest]
        x,y,_,_=_geometry.closest_segments(a,b,c,d)
        best=min(best,(x-y).length)
        for _,i,_ in tree.find_range(middle,best+half+(b-a).length/2):
            c,d=other[i];x,y,_,_=_geometry.closest_segments(a,b,c,d)
            best=min(best,(x-y).length)
    return best


def seat_crossing_strands(scene,surface,displays,paths):
    """Close scalloped braid gaps after circular-envelope crossing placement."""
    for joint in scene.ropes_settings.junctions:
        if joint.is_knot:continue
        upper,lower=(joint.rope_a,joint.rope_b) if joint.over_a else (joint.rope_b,joint.rope_a)
        if upper.name not in displays or lower.name not in displays:continue
        us,ls=(joint.distance_a,joint.distance_b) if joint.over_a else (joint.distance_b,joint.distance_a)
        points,stations=displays[upper.name];below,ss=displays[lower.name]
        radius=upper.ropes_rope.radius+lower.ropes_rope.radius
        span=max(envelope_radius(upper),envelope_radius(lower))*6
        crossing=sample_at(paths[upper.name],cumulative(paths[upper.name]),us)[0]
        normal=surface.normal_at(crossing)
        # A level centre keeps the established apex aligned during seating.
        plateau=max(envelope_radius(upper),envelope_radius(lower))
        weights=[.5*(1+math.cos(math.pi*max(0,abs(s-us)-plateau)/(span-plateau)))
                 if abs(s-us)<span else 0 for s in stations]
        support=crossing_strand_segments(lower,below,ss,ls,span)
        goal=radius*.46
        def gap(drop):
            candidate=[p-normal*(drop*w) for p,w in zip(points,weights)]
            passive=(crossing_strand_segments(lower,candidate,ss,ls,span) if upper==lower else support)
            return strand_segment_gap(crossing_strand_segments(upper,candidate,stations,us,span),passive)
        if gap(0)<=goal*(1+1e-4):continue
        lo=0.0;hi=radius*.45
        if gap(hi)>goal:continue
        for _ in range(14):
            mid=(lo+hi)/2
            if gap(mid)>goal:lo=mid
            else:hi=mid
        displays[upper.name]=([p-normal*(lo*w) for p,w in zip(points,weights)],stations)


def fit_crossing_curves(scene, surface, displays, paths):
    """Fit overpasses to physical run curves, independent of bundle width/height."""
    for joint in scene.ropes_settings.junctions:
        if joint.is_knot:
            continue
        upper,lower=(joint.rope_a,joint.rope_b) if joint.over_a else (joint.rope_b,joint.rope_a)
        if upper.name not in displays or lower.name not in displays:
            continue
        us,ls=(joint.distance_a,joint.distance_b) if joint.over_a else (joint.distance_b,joint.distance_a)
        points,stations=displays[upper.name]
        below,lower_stations=displays[lower.name]
        goal=upper.ropes_rope.radius+lower.ropes_rope.radius
        # Width determines the transition footprint, never vertical clearance.
        span=max(envelope_radius(upper),envelope_radius(lower))*6
        crossing,ut=sample_at(paths[upper.name],cumulative(paths[upper.name]),us)
        _,lt=sample_at(paths[lower.name],cumulative(paths[lower.name]),ls)
        normal=surface.normal_at(crossing)
        plateau=0.0
        weights=[.5*(1+math.cos(math.pi*max(0,abs(s-us)-plateau)/(span-plateau)))
                 if abs(s-us)<span else 0 for s in stations]
        upper_segments=[i for i in range(len(points)-1) if weights[i]>0 or weights[i+1]>0]
        lower_segments=[i for i in range(len(below)-1)
                        if min(abs(lower_stations[i]-ls),abs(lower_stations[i+1]-ls))<span]
        pairs=[(i,j) for i in upper_segments for j in lower_segments]
        if not pairs:
            continue
        def clear(height):
            lifted={i:points[i]+normal*(height*weights[i]) for i in set(k for a,b in pairs for k in (a,a+1))}
            for i,j in pairs:
                a,b,_,_=_geometry.closest_segments(lifted[i],lifted[i+1],below[j],below[j+1])
                if (a-b).length<goal*(1+1e-5):
                    return False
            return True
        if clear(0):
            continue
        lo,hi=0.0,goal
        for _ in range(12):
            if clear(hi):
                break
            hi*=2
        else:
            raise ValueError('Crossing cannot clear adjacent waypoints. Move the crossing farther from the rope end.')
        for _ in range(20):
            mid=(lo+hi)*.5
            if clear(mid): hi=mid
            else: lo=mid
        displays[upper.name]=([p+normal*(hi*w) for p,w in zip(points,weights)],stations)


def render_ropes(scene, target, surface, ropes, paths):
    settings = scene.ropes_settings
    displays = {rope.name: display_path(scene, rope, surface, paths[rope.name])
                for rope in ropes if rope.name in paths}
    fit_crossing_curves(scene,surface,displays,paths)
    for _ in range(2):
        seat_crossing_strands(scene,surface,displays,paths)
    pressure = PressureField(scene, target, surface, displays)
    helpers = {(o.get('ropes_owner'), o.get('ropes_strand')): o for o in scene.objects
               if o.get('ropes_helper') and o.parent == target}
    used_helpers = set()
    for rope in ropes:
        radius = rope.ropes_rope.radius
        if rope.name not in displays:
            set_curve(rope, [], radius)
            rope['ropes_contact_path']='[]'
            continue
        physical, stations = displays[rope.name]
        inverse=target.matrix_world.inverted_safe()
        rope['ropes_contact_path']=json.dumps([list(inverse @ p) for p in physical])
        rendered = []
        route=paths[rope.name]
        normals=support_normals(rope,surface,route,cumulative(route),stations)
        for point,guide in zip(physical,normals):
            nearest, normal, _ = surface.project(point)
            station=stations[len(rendered)]
            weight=0.0
            if not span_at(rope,station):
                for record in knot_records(scene,rope):
                    extent=knot_extent(record,rope)
                    distance=abs(station-record['station'])
                    weight=max(weight,max(0,1-distance/extent)**2)
            rendered.append(point-guide*pressure.value(nearest)*weight)
        set_curve(rope, rendered, radius)
        rope['ropes_stations'] = json.dumps(stations)
        rope.data.bevel_depth = 0
        for index, strand in enumerate(three_strands(rendered, radius, rope.ropes_rope.strand_pitch)):
            helper = helpers.get((rope.ropes_rope.uid, index))
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
    curve_view_update(scene.ropes_settings,SimpleNamespace(scene=scene))
    deform(scene, target, pressure)
    refresh_markers(scene, target, surface, pressure)
    bpy.context.view_layer.update()
    settings.message = ''


class PressureField:
    """Per-rope masks cover the actual runs, folded end and knot footprints."""
    def __init__(self, scene, target, surface=None, displays=None):
        self.contacts = []
        surface = surface or Surface(target, 0)
        for rope in rope_objects(scene, target):
            props = rope.ropes_rope
            depth = props.radius*props.squish
            path = rest_path(rope)
            if depth <= 0 or len(path) < 2 or not props.generated:
                continue
            if displays is not None:
                physical,stations=displays[rope.name]
            elif rope.get('ropes_contact_path') and json.loads(rope['ropes_contact_path']):
                physical=[target.matrix_world @ Vector(p) for p in json.loads(rope['ropes_contact_path'])]
                stations=json.loads(rope['ropes_stations'])
            else:
                physical,stations=display_path(scene,rope,surface,path)
            width=props.radius*props.falloff
            segments=[]
            mappings=[]
            for i,(a,b) in enumerate(zip(physical,physical[1:])):
                if not span_at(rope,(stations[i]+stations[i+1])/2):
                    segments.append((surface.project(a)[0],surface.project(b)[0]))
                    mappings.append((stations[i],stations[i+1]))
            if not segments:
                continue
            samples = [(point, i) for i, (a, b) in enumerate(segments)
                       for point in resample([a, b], width/2)]
            tree = KDTree(len(samples))
            for i, (point, _) in enumerate(samples):
                tree.insert(point, i)
            tree.balance()
            self.contacts.append((tree, samples, segments, width, depth, rope, mappings))

    def value(self, point):
        result = 0.0
        for tree, samples, segments, width, depth, rope, mappings in self.contacts:
            candidates = {samples[i][1] for _, i, _ in tree.find_n(point, min(8, len(samples)))}
            index=min(candidates,key=lambda i:point_segment_distance(point,*segments[i]))
            a,b=segments[index]
            delta=b-a
            t=max(0,min(1,(point-a).dot(delta)/delta.length_squared)) if delta.length_squared else 0
            station=mappings[index][0]*(1-t)+mappings[index][1]*t
            distance=point_segment_distance(point,a,b)
            if distance < width*3:
                result = max(result, depth*contact_weight(rope,station)*math.exp(-2*(distance/width)**2))
        return result


def refresh_draft_markers(scene, rope, index=None):
    """Update only this draft's markers, without inspecting mesh or other ropes."""
    props=rope.ropes_rope
    indices=range(len(props.anchors)) if index is None else (index,)
    scale=max(abs(sum(props.target.matrix_world.to_scale())/3),1e-6)
    for i in indices:
        anchor=props.anchors[i]
        key=f'Ropes WP {props.uid} {i}'
        marker=scene.objects.get(key)
        if marker is None:
            marker=bpy.data.objects.new(key,None)
            generated_collection(scene).objects.link(marker)
            marker.parent=props.target
            marker.matrix_parent_inverse=Matrix.Identity(4)
        marker.location=anchor.position
        marker.empty_display_type='CUBE' if anchor.kind=='SPANNING' else 'SPHERE'
        marker.empty_display_size=max(props.radius*.85,.015)*scene.ropes_settings.waypoint_size/scale
        marker.show_in_front=scene.ropes_settings.waypoint_xray
        marker.hide_render=True
        marker['ropes_generated']=True
        marker['ropes_owner']=props.uid
        marker['ropes_waypoint']=i


def refresh_markers(scene, target, surface=None, pressure=None):
    markers = {(o.get('ropes_owner'), o.get('ropes_waypoint')): o for o in scene.objects
               if 'ropes_waypoint' in o and o.parent == target}
    used = set()
    if scene.ropes_settings.show_waypoints or any(not r.ropes_rope.generated for r in rope_objects(scene,target)):
        surface = surface or Surface(target, 0)
        pressure = pressure or PressureField(scene, target, surface)
        inverse = target.matrix_world.inverted_safe()
        scale = max(abs(sum(target.matrix_world.to_scale())/3), 1e-6)
        for rope in rope_objects(scene, target):
            if not scene.ropes_settings.show_waypoints and rope.ropes_rope.generated:
                continue
            radius = rope.ropes_rope.radius
            for index, anchor in enumerate(rope.ropes_rope.anchors):
                key = (rope.ropes_rope.uid, index)
                marker = markers.get(key)
                if marker is None:
                    marker = bpy.data.objects.new(f'{rope.name} · Waypoint {index+1}', None)
                    generated_collection(scene).objects.link(marker)
                    marker.parent = target
                    marker.matrix_parent_inverse = Matrix.Identity(4)
                point = target.matrix_world @ Vector(anchor.position)
                normal=surface.normal_at(point)
                marker.location = inverse @ (point-normal*(pressure.value(point) if rope.ropes_rope.generated else 0))
                marker.empty_display_type = 'CUBE' if anchor.kind=='SPANNING' else 'SPHERE'
                marker.name=f'Ropes WP {rope.ropes_rope.uid} {index}'
                marker.empty_display_size = max(radius*.85, .015)*scene.ropes_settings.waypoint_size/scale
                marker.show_in_front = scene.ropes_settings.waypoint_xray
                marker.show_name = False
                marker.hide_render = True
                marker['ropes_generated'] = True
                marker['ropes_owner'] = rope.ropes_rope.uid
                marker['ropes_waypoint'] = index
                used.add(marker)
    for marker in markers.values():
        if marker not in used:
            bpy.data.objects.remove(marker, do_unlink=True)
    bpy.context.view_layer.update()


def waypoint_visible(context,region,rv3d,marker,pixel):
    origin=view3d_utils.region_2d_to_origin_3d(region,rv3d,pixel)
    delta=marker.matrix_world.translation-origin
    if delta.length<1e-8:
        return True
    tolerance=max(marker.empty_display_size*.2,1e-4)
    hit,position,_,_,_,_=context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(),origin,delta.normalized(),distance=max(0,delta.length-tolerance))
    return not hit


def pick_waypoint(context, event, target, region, rv3d):
    mouse = Vector((event.mouse_x-region.x, event.mouse_y-region.y))
    best, distance = None, float("inf")
    for marker in context.scene.objects:
        if 'ropes_waypoint' not in marker or marker.parent != target:
            continue
        pixel = view3d_utils.location_3d_to_region_2d(region, rv3d, marker.matrix_world.translation)
        if pixel is None:
            continue
        world_radius = marker.empty_display_size*max(marker.matrix_world.to_scale())
        edge = view3d_utils.location_3d_to_region_2d(region, rv3d,
               marker.matrix_world.translation+rv3d.view_rotation @ Vector((world_radius, 0, 0)))
        threshold = max(2, (edge-pixel).length+2) if edge is not None else 2
        if (pixel-mouse).length < min(distance, threshold):
            if not context.scene.ropes_settings.waypoint_xray and not waypoint_visible(context,region,rv3d,marker,pixel):
                continue
            distance = (pixel-mouse).length
            best = marker['ropes_owner'], marker['ropes_waypoint']
    return best


def surface_point(target, world_position):
    return Surface(target,0).project(world_position)[0]


def move_waypoint(scene, rope, index, world_position):
    target = rope.ropes_rope.target
    if not rope.ropes_rope.generated:
        rope.ropes_rope.anchors[index].position=target.matrix_world.inverted_safe() @ Vector(world_position)
        refresh_draft_markers(scene,rope)
        return
    if not rope.get('ropes_leg_bounds'):
        rebuild(scene, target)
    before = capture_state(scene, target, rope)
    old_bounds = json.loads(rope['ropes_leg_bounds'])
    knots = []
    for knot in rope.ropes_rope.knots:
        leg = max(0, min(len(old_bounds)-2, bisect.bisect_right(old_bounds, knot.distance)-1))
        span = old_bounds[leg+1]-old_bounds[leg]
        fraction = max(0, min(1, (knot.distance-old_bounds[leg])/span)) if span else 0
        knots.append((leg, fraction))
    surface = Surface(target, 0)
    point, _, _ = surface.project(world_position)
    rope.ropes_rope.anchors[index].position = target.matrix_world.inverted_safe() @ point
    try:
        rebuild(scene, target)
        bounds = json.loads(rope['ropes_leg_bounds'])
        for knot, (leg, fraction) in zip(rope.ropes_rope.knots, knots):
            knot.distance = bounds[leg]+fraction*(bounds[leg+1]-bounds[leg])
        if knots:
            refresh_render(scene, target)
    except (ValueError, RuntimeError):
        restore_state(scene, target, before)
        raise


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
        if not j.is_knot:
            j.knot_a=rope==j.rope_a if j.rope_a!=j.rope_b else j.over_a
            j.knot_owner_set=True
        j.is_knot = not j.is_knot
        settings.active_junction = list(settings.junctions).index(j)
    else:
        knots = rope.ropes_rope.knots
        closest = next((i for i, k in enumerate(knots) if abs(k.distance-distance) < radius*5), None)
        if closest is not None:
            knots.remove(closest)
        else:
            knots.add().distance = distance
            rope.ropes_rope.active_knot = len(knots)-1
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


def capture_state(scene, target, current_rope=None, drafts_only=False):
    states = []
    for rope in rope_objects(scene, target):
        if drafts_only and rope.ropes_rope.generated:
            continue
        states.append(dict(uid=rope.ropes_rope.uid, name=rope.name,
                           order=rope.ropes_rope.order,
                           anchors=[dict(position=tuple(a.position),kind=a.kind) for a in rope.ropes_rope.anchors],
                           generated=rope.ropes_rope.generated,
                           draft_source=rope.get('ropes_draft_source',''),
                           knots=[dict(distance=k.distance, kind=k.kind) for k in rope.ropes_rope.knots],
                           props={name: getattr(rope.ropes_rope, name) for name in COPY_SETTINGS},
                           path=rope.get('ropes_path', '[]'), legs=rope.get('ropes_leg_bounds', '[]'), spans=rope.get('ropes_span_flags','[]'), centers=rope.get('ropes_span_centers','[]')))
    junctions = [dict(a=j.rope_a.ropes_rope.uid, b=j.rope_b.ropes_rope.uid,
                      position=tuple(j.position), sa=j.distance_a, sb=j.distance_b,
                      knot=j.is_knot, over_a=j.over_a, uid=j.uid, kind=j.kind, knot_a=j.knot_a, knot_owner_set=j.knot_owner_set)
                 for j in scene.ropes_settings.junctions if
                 not drafts_only and j.rope_a and j.rope_b and j.rope_a.ropes_rope.target == target]
    active = scene.ropes_settings.active_rope
    return dict(drafts_only=drafts_only, ropes=states, junctions=junctions,
                active=active.ropes_rope.uid if active else None,
                current=current_rope.ropes_rope.uid if current_rope else None)


def delete_rope(rope):
    data = rope.data
    bpy.data.objects.remove(rope, do_unlink=True)
    if data is not None and data.users == 0:
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        else:
            bpy.data.curves.remove(data)


def restore_state(scene, target, state):
    with quiet_updates():
        existing = {r.ropes_rope.uid: r for r in rope_objects(scene, target)
                    if not state.get('drafts_only') or not r.ropes_rope.generated}
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
            props.generated=record['generated']
            rope['ropes_draft_source']=record.get('draft_source','')
            for point in record['anchors']:
                anchor=props.anchors.add()
                anchor.position,anchor.kind=point['position'],point['kind']
            for knot in record['knots']:
                item = props.knots.add()
                item.distance, item.kind = knot['distance'], 'OVERHAND'
            rope['ropes_path'] = record['path']
            rope['ropes_leg_bounds'] = record['legs']
            rope['ropes_span_flags']=record['spans']
            rope['ropes_span_centers']=record['centers']
        settings = scene.ropes_settings
        for i in reversed(range(len(settings.junctions)) if not state.get('drafts_only') else []):
            j = settings.junctions[i]
            if not j.rope_a or j.rope_a.ropes_rope.target == target:
                settings.junctions.remove(i)
        for record in state['junctions']:
            j = settings.junctions.add()
            j.rope_a, j.rope_b = existing[record['a']], existing[record['b']]
            j.position = record['position']
            j.distance_a, j.distance_b = record['sa'], record['sb']
            j.is_knot, j.over_a, j.uid = record['knot'], record['over_a'], record['uid']
            j.kind = 'OVERHAND'
            j.knot_a,j.knot_owner_set=record.get('knot_a',j.over_a),record.get('knot_owner_set',False)
        settings.active_rope = next((r for r in rope_objects(scene,target) if r.ropes_rope.uid==state['active']),None)
    if state.get('drafts_only'):
        wanted={(r.ropes_rope.uid,i) for r in existing.values() for i in range(len(r.ropes_rope.anchors))}
        for marker in list(scene.objects):
            if 'ropes_waypoint' in marker and marker.parent==target:
                uid=marker.get('ropes_owner')
                owner=next((r for r in rope_objects(scene,target) if r.ropes_rope.uid==uid),None)
                if (owner is None or not owner.ropes_rope.generated) and (uid,marker['ropes_waypoint']) not in wanted:
                    bpy.data.objects.remove(marker,do_unlink=True)
        for rope in existing.values():
            refresh_draft_markers(scene,rope)
    else:
        rebuild(scene, target, repath=False)
    return existing.get(state['current'])


def modal_history(operator, context, redo=False):
    source = operator.redo_history if redo else operator.undo_history
    destination = operator.undo_history if redo else operator.redo_history
    if not source:
        operator.report({'INFO'}, 'No more edits to redo.' if redo else 'No more edits to undo in this session.')
        return
    current = capture_state(context.scene, operator.target, operator.rope, drafts_only=source[-1].get('drafts_only',False))
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
            self.surface = Surface(target, 0, routing=False)
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.area = context.area
        self.region = next(r for r in self.area.regions if r.type == 'WINDOW')
        self.rv3d = context.space_data.region_3d
        self.target = target
        self.moving_waypoint = None
        self.undo_history = []
        self.redo_history = []
        self.rope = settings.active_rope if self.extend else None
        if self.rope and (not self.rope.ropes_rope.enabled or self.rope.ropes_rope.target != target):
            self.rope = None
        if self.rope and self.rope.ropes_rope.generated and settings.waypoint_mode:
            before=capture_state(context.scene,target,self.rope)
            try:
                begin_waypoint_draft(context.scene,self.rope)
            except (ValueError,RuntimeError) as exc:
                self.report({'ERROR'},str(exc))
                return {'CANCELLED'}
            self.undo_history.append(before)
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set('Ropes: LMB add point · N new rope · W waypoints · T point type · RMB on rope knot/crossing · Enter/Esc finish · Ctrl+Z / Backspace undo · Ctrl+Shift+Z redo')
        return {'RUNNING_MODAL'}

    def finish(self, context):
        self.area.header_text_set(None)
        self.area.tag_redraw()
        return {'FINISHED'}

    def modal(self, context, event):
        if event.value == 'PRESS' and ((event.type == 'Z' and getattr(event, 'ctrl', False)) or
                                     event.type == 'BACK_SPACE'):
            try:
                self.moving_waypoint = None
                modal_history(self, context, redo=getattr(event, 'shift', False))
            except (ValueError, RuntimeError) as exc:
                self.report({'ERROR'}, str(exc))
            return {'RUNNING_MODAL'}
        if event.type == 'T' and event.value == 'PRESS':
            settings=context.scene.ropes_settings
            settings.placement_kind='SPANNING' if settings.placement_kind=='NORMAL' else 'NORMAL'
            self.report({'INFO'},'New waypoint type: '+settings.placement_kind.title())
            return {'RUNNING_MODAL'}
        if event.type == 'W' and event.value == 'PRESS':
            settings = context.scene.ropes_settings
            settings.show_waypoints = not settings.show_waypoints
            self.moving_waypoint = None
            return {'RUNNING_MODAL'}
        if event.type in {'ESC', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            if getattr(self, 'moving_waypoint', None) and event.type == 'ESC':
                self.moving_waypoint = None
                self.report({'INFO'}, 'Waypoint move cancelled.')
                return {'RUNNING_MODAL'}
            return self.finish(context)
        if event.type == 'N' and event.value == 'PRESS':
            self.moving_waypoint = None
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
                if getattr(self, 'moving_waypoint', None):
                    self.moving_waypoint = None
                    return {'RUNNING_MODAL'}
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
                pending = getattr(self, 'moving_waypoint', None)
                if not pending and (context.scene.ropes_settings.show_waypoints or context.scene.ropes_settings.waypoint_mode):
                    picked = pick_waypoint(context, event, self.target, self.region, self.rv3d)
                    if picked:
                        self.moving_waypoint = picked
                        for marker in context.scene.objects:
                            if 'ropes_waypoint' in marker and marker.parent == self.target:
                                marker.select_set(marker.get('ropes_owner') == picked[0] and marker.get('ropes_waypoint') == picked[1])
                        self.rope = next(r for r in rope_objects(context.scene, self.target) if r.ropes_rope.uid == picked[0])
                        self.rope.ropes_rope.active_anchor=picked[1]
                        context.scene.ropes_settings.active_rope = self.rope
                        self.report({'INFO'}, f'Waypoint {picked[1]+1} selected. Click a new surface location.')
                        return {'RUNNING_MODAL'}
                origin = view3d_utils.region_2d_to_origin_3d(self.region, self.rv3d,
                                                          (event.mouse_x-self.region.x, event.mouse_y-self.region.y))
                direction = view3d_utils.region_2d_to_vector_3d(self.region, self.rv3d,
                                                             (event.mouse_x-self.region.x, event.mouse_y-self.region.y))
                point, _, _, _ = self.surface.bvh.ray_cast(origin, direction)
                if point is None:
                    self.report({'INFO'}, 'Click on the chosen surface.')
                    return {'RUNNING_MODAL'}
                before = capture_state(context.scene, self.target, self.rope,
                                       drafts_only=(not self.rope.ropes_rope.generated if self.rope else context.scene.ropes_settings.waypoint_mode))
                if pending:
                    rope = next(r for r in rope_objects(context.scene, self.target) if r.ropes_rope.uid == pending[0])
                    move_waypoint(context.scene, rope, pending[1], point)
                    self.rope = rope
                    self.moving_waypoint = None
                    self.undo_history.append(before)
                    self.redo_history.clear()
                    self.area.tag_redraw()
                    return {'RUNNING_MODAL'}
                if self.rope is None:
                    self.rope = new_rope(context.scene, self.target)
                anchors = self.rope.ropes_rope.anchors
                if anchors and (self.target.matrix_world @ Vector(anchors[-1].position)-point).length < 1e-5:
                    return {'RUNNING_MODAL'}
                with quiet_updates():
                    anchor=anchors.add()
                    anchor.position=self.target.matrix_world.inverted_safe() @ point
                    anchor.kind=context.scene.ropes_settings.placement_kind
                try:
                    if self.rope.ropes_rope.generated:
                        rebuild(context.scene, self.target)
                    else:
                        refresh_draft_markers(context.scene,self.rope,index=len(anchors)-1)
                except (ValueError, RuntimeError):
                    anchors.remove(len(anchors)-1)
                    rebuild(context.scene, self.target)
                    raise
                self.undo_history.append(before)
                self.redo_history.clear()
                self.rope.ropes_rope.active_anchor=len(anchors)-1
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



def begin_waypoint_draft(scene,rope):
    if not rope.ropes_rope.generated:
        return
    target=rope.ropes_rope.target
    source=capture_state(scene,target,rope)
    uid=rope.ropes_rope.uid
    pending=dict(ropes=[r for r in source['ropes'] if r['uid']==uid],junctions=[j for j in source['junctions'] if uid in (j['a'],j['b'])])
    rope['ropes_draft_source']=json.dumps(pending)
    rope.ropes_rope.generated=False
    try:
        rebuild(scene,target,repath=False)
    except (ValueError,RuntimeError):
        restore_state(scene,target,source)
        raise


def restore_draft_junctions(scene,rope,source):
    owners={r.ropes_rope.uid:r for r in rope_objects(scene,rope.ropes_rope.target)}
    present={j.uid for j in scene.ropes_settings.junctions}
    with quiet_updates():
        for record in source.get('junctions',[]):
            if record['uid'] in present or record['a'] not in owners or record['b'] not in owners:
                continue
            if rope.ropes_rope.uid not in (record['a'],record['b']):
                continue
            j=scene.ropes_settings.junctions.add()
            j.rope_a,j.rope_b=owners[record['a']],owners[record['b']]
            j.position=record['position']
            j.distance_a,j.distance_b=record['sa'],record['sb']
            j.is_knot,j.over_a,j.uid,j.kind=record['knot'],record['over_a'],record['uid'],'OVERHAND'
            j.knot_a,j.knot_owner_set=record.get('knot_a',j.over_a),record.get('knot_owner_set',False)


class ROPES_OT_EditWaypoints(bpy.types.Operator):
    bl_idname='ropes.edit_waypoints'
    bl_label='Edit Waypoint Draft'
    bl_description='Return this rope to editable waypoints; Generate Rope applies the new plan'
    bl_options={'REGISTER','UNDO'}

    def execute(self,context):
        rope=context.scene.ropes_settings.active_rope
        if not rope:
            return {'CANCELLED'}
        try:
            begin_waypoint_draft(context.scene,rope)
        except (ValueError,RuntimeError) as exc:
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}
        context.scene.ropes_settings.waypoint_mode=True
        return {'FINISHED'}


class ROPES_OT_Generate(bpy.types.Operator):
    bl_idname='ropes.generate'
    bl_label='Generate Rope'
    bl_description='Generate the active draft after all waypoints have been placed'
    bl_options={'REGISTER','UNDO'}

    def execute(self,context):
        rope=context.scene.ropes_settings.active_rope
        if not rope or len(rope.ropes_rope.anchors)<2:
            self.report({'ERROR'},'Place at least two waypoints first.')
            return {'CANCELLED'}
        target=rope.ropes_rope.target
        state=capture_state(context.scene,target,rope)
        rope.ropes_rope.generated=True
        source=json.loads(rope.get('ropes_draft_source') or '{}')
        try:
            restore_draft_junctions(context.scene,rope,source)
            rebuild(context.scene,target)
            old=next((r for r in source.get('ropes',[]) if r['uid']==rope.ropes_rope.uid),None)
            if old and old['knots']:
                previous=json.loads(old['legs'])
                current=json.loads(rope['ropes_leg_bounds'])
                for knot,record in zip(rope.ropes_rope.knots,old['knots']):
                    leg=max(0,min(len(previous)-2,bisect.bisect_right(previous,record['distance'])-1))
                    fraction=(record['distance']-previous[leg])/max(1e-9,previous[leg+1]-previous[leg])
                    leg=min(leg,len(current)-2)
                    knot.distance=current[leg]+fraction*(current[leg+1]-current[leg])
                refresh_render(context.scene,target)
            if 'ropes_draft_source' in rope:
                del rope['ropes_draft_source']
        except (ValueError,RuntimeError) as exc:
            restore_state(context.scene,target,state)
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


class ROPES_UL_Waypoints(bpy.types.UIList):
    def draw_item(self,context,layout,data,item,icon,active_data,active_propname,index):
        layout.label(text=f'{index+1} · {item.kind.title()}',icon='CUBE' if item.kind=='SPANNING' else 'SPHERE')


class ROPES_UL_Knots(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=f'Knot {index+1} · {item.distance:.2f}', icon='LINKED')



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
        layout.prop(settings, 'curve_view', text='Display')
        layout.operator('ropes.use_selected', icon='EYEDROPPER')
        layout.prop(settings, 'show_waypoints')
        layout.prop(settings, 'waypoint_size')
        layout.prop(settings, 'waypoint_xray')
        layout.prop(settings, 'waypoint_mode')
        layout.prop(settings, 'placement_kind')
        layout.operator('ropes.draw', text='Draw New Rope', icon='CURVE_DATA').extend = False
        layout.prop(settings, 'active_rope', text='Active Rope')
        layout.operator('ropes.use_selected_rope', icon='EYEDROPPER')
        rope = settings.active_rope
        if rope and rope.ropes_rope.enabled:
            props = rope.ropes_rope
            box = layout.box()
            box.label(text=rope.name+(' · Draft' if not props.generated else ''))
            box.template_list('ROPES_UL_Waypoints','',props,'anchors',props,'active_anchor',rows=3)
            if props.active_anchor<len(props.anchors):
                box.prop(props.anchors[props.active_anchor],'kind')
            if not props.generated:
                box.operator('ropes.generate',icon='CURVE_DATA')
            else:
                box.operator('ropes.edit_waypoints',icon='EDITMODE_HLT')
            box.prop(props, 'radius')
            box.prop(props, 'smoothing', slider=True)
            box.prop(props, 'subdivisions')
            box.prop(props, 'strand_pitch')
            box.prop(props, 'knot_size')
            if props.knots:
                box.template_list('ROPES_UL_Knots', '', props, 'knots', props, 'active_knot', rows=2)
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
        layout.label(text='W: toggle waypoint markers')
        layout.label(text='T: normal / spanning point')
        layout.label(text='RMB rope: knot / junction')
        layout.label(text='Ctrl+Z / Backspace: undo')
        layout.label(text='Ctrl+Shift+Z: redo')
        layout.label(text='Enter / Esc: finish')


CLASSES = (ROPES_PG_Anchor, ROPES_PG_Knot, ROPES_PG_Rope, ROPES_PG_Junction,
           ROPES_PG_Settings, ROPES_OT_Rebuild, ROPES_OT_UseSelected,
           ROPES_OT_Draw, ROPES_OT_Remove, ROPES_OT_RemoveLastPoint,
           ROPES_OT_SelectRope, ROPES_OT_EditWaypoints, ROPES_OT_Generate, ROPES_UL_Waypoints, ROPES_UL_Knots, ROPES_UL_Junctions,
           ROPES_OT_SwapCrossing, ROPES_PT_Panel)



def migrate_after_enable():
    # Enabling an add-on runs under Blender's restricted data/context wrapper.
    # A timer runs after that wrapper has been released, on the main thread.
    if not hasattr(bpy.data, 'scenes'):
        return .1
    migrate_on_load(None)
    return None


def registered_classes():
    result = []
    for cls in CLASSES:
        base = cls.__bases__[0]
        if issubclass(cls, bpy.types.Operator):
            prefix, suffix = cls.bl_idname.split('.')
            identifier = prefix.upper()+'_OT_'+suffix
        else:
            identifier = getattr(cls, 'bl_idname', None) or cls.__name__
        found = base.bl_rna_get_subclass_py(identifier, None)
        if found and found.__module__ == __name__:
            result.append(found)
    return result


def clear_registration():
    # A failed 0.2 registration can leave classes and pointers behind even though
    # Blender has removed the module from its enabled-add-on list. Clean up only
    # this add-on's RNA registrations before retrying, preserving scene ID data.
    if bpy.app.timers.is_registered(migrate_after_enable):
        bpy.app.timers.unregister(migrate_after_enable)
    for handler in list(bpy.app.handlers.load_post):
        if handler.__module__ == __name__ and handler.__name__ == 'migrate_on_load':
            bpy.app.handlers.load_post.remove(handler)
    classes = registered_classes()
    if classes:
        if hasattr(bpy.types.Scene, 'ropes_settings'):
            del bpy.types.Scene.ropes_settings
        if hasattr(bpy.types.Object, 'ropes_rope'):
            del bpy.types.Object.ropes_rope
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)


def register():
    clear_registration()
    try:
        for cls in CLASSES:
            bpy.utils.register_class(cls)
        bpy.types.Object.ropes_rope = PointerProperty(type=ROPES_PG_Rope)
        bpy.types.Scene.ropes_settings = PointerProperty(type=ROPES_PG_Settings)
        bpy.app.handlers.load_post.append(migrate_on_load)
        bpy.app.timers.register(migrate_after_enable, first_interval=0.0)
    except Exception:
        clear_registration()
        raise


def unregister():
    clear_registration()
