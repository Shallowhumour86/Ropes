"""Run with blender --background --factory-startup --python-exit-code 1 --python tests/blender_integration.py."""
import json
import math
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import bpy
from bpy_extras import view3d_utils
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ropes
from ropes.geometry import Surface, closest_segments, cumulative, crossings

print("BLENDER_TEST_VERSION", bpy.app.version_string)
ropes.register()


def knot_determinant(points):
    """Fox coloring matrix determinant after an outside closure of open ports."""
    import bisect
    import numpy as np
    a,b=points[0],points[-1]
    reach=max(p.length for p in points)*10+1
    points=points+[b+Vector((reach,0,0)),b+Vector((reach,-reach,0)),a+Vector((-reach,-reach,0)),a+Vector((-reach,0,0))]
    direction=Vector((.217,.413,.884)).normalized();x=direction.orthogonal().normalized();y=direction.cross(x)
    pts=[Vector((p.dot(x),p.dot(y),p.dot(direction))) for p in points];pts.append(pts[0]);cs=[]
    for i,(a,b) in enumerate(zip(pts,pts[1:])):
        for j in range(i+2,len(pts)-1):
            if i==0 and j==len(pts)-2:continue
            c,d=pts[j:j+2];u=b-a;v=d-c;den=u.x*v.y-u.y*v.x
            if abs(den)<1e-12:continue
            w=c-a;t=(w.x*v.y-w.y*v.x)/den;s=(w.x*u.y-w.y*u.x)/den
            if not(1e-7<t<1-1e-7 and 1e-7<s<1-1e-7):continue
            ai=i+t;bj=j+s
            over,under=(ai,bj) if a.z+t*u.z>c.z+s*v.z else (bj,ai)
            cs.append((over,under))
    under=sorted(c[1] for c in cs);n=len(under)
    if n==0:return 1
    mat=np.zeros((n,n),dtype=int)
    for k,(o,u) in enumerate(cs):
        after=bisect.bisect_right(under,u)%n;before=(after-1)%n;oa=bisect.bisect_right(under,o)%n
        mat[k,oa]+=2;mat[k,after]-=1;mat[k,before]-=1
    return round(abs(np.linalg.det(mat[:-1,:-1])))


class RopesIntegration(unittest.TestCase):
    def setUp(self):
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.context.scene.ropes_settings.junctions.clear()
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=25, y_subdivisions=25, size=4)
        self.target = bpy.context.object
        self.settings = bpy.context.scene.ropes_settings
        self.settings.target = self.target
        self.settings.radius = .035
        self.settings.subdivisions = 1
        self.settings.squish = 0
        self.settings.tension = .5
        self.settings.smoothing = 1
        self.settings.waypoint_xray=False
        self.settings.waypoint_size=.6
        self.settings.show_waypoints = False
        self.settings.waypoint_mode = False
        self.settings.placement_kind = 'NORMAL'
        self.settings.knot_type = 'OVERHAND'
        self.settings.knot_size = 1
        self.settings.doubled = False
        self.settings.double_spacing = 1
        self.settings.falloff = 4

    def rope(self, *anchors):
        obj = ropes.new_rope(bpy.context.scene, self.target)
        for point in anchors:
            obj.ropes_rope.anchors.add().position = point
        ropes.rebuild(bpy.context.scene, self.target)
        return obj

    def test_surface_route_and_extension(self):
        r = self.rope((-1, -.6, 0), (1, -.6, 0))
        p = ropes.rest_path(r)
        self.assertGreater(len(p), 2)
        self.assertLess((p[0]-Vector((-1, -.6, 0))).length, 1e-4)
        self.assertTrue(all(abs(v.z) < 1e-5 for v in p))
        r.ropes_rope.anchors.add().position = (1, 1, 0)
        ropes.rebuild(bpy.context.scene, self.target)
        self.assertLess((ropes.rest_path(r)[-1]-Vector((1, 1, 0))).length, 1e-4)
        self.assertEqual(len(r.ropes_rope.anchors), 3)

    def test_crossing_under_default_swap_and_knot_toggle(self):
        a = self.rope((-1.5, 0, 0), (1.5, 0, 0))
        b = self.rope((0, -1.5, 0), (0, 1.5, 0))
        self.assertEqual(len(self.settings.junctions), 1)
        j = self.settings.junctions[0]
        self.assertTrue(j.over_a)
        self.assertEqual(j.rope_a, a)
        self.assertEqual(j.rope_b, b)
        pa, _ = ropes.sample_at(ropes.visible_path(a), cumulative(ropes.rest_path(a)), j.distance_a)
        pb, _ = ropes.sample_at(ropes.visible_path(b), cumulative(ropes.rest_path(b)), j.distance_b)
        self.assertGreater(pa.z, pb.z+self.settings.radius)
        self.assertEqual(bpy.ops.ropes.swap_crossing(), {'FINISHED'})
        j = self.settings.junctions[0]
        self.assertFalse(j.over_a)
        self.assertGreater(max(p.z for p in ropes.visible_path(b)), max(p.z for p in ropes.visible_path(a)))
        station = j.distance_b
        ropes.knot_at(bpy.context.scene, b, station)
        self.assertTrue(self.settings.junctions[0].is_knot)
        self.assertGreater(len(ropes.visible_path(b)), len(ropes.rest_path(b)))
        ropes.knot_at(bpy.context.scene, b, station)
        self.assertFalse(self.settings.junctions[0].is_knot)
        self.assertEqual(len(ropes.visible_path(b)), len(ropes.rest_path(b)))

    def test_manual_knots_and_extension_preserve_station(self):
        r = self.rope((-1.5, 0, 0), (1, 0, 0))
        ropes.knot_at(bpy.context.scene, r, .65)
        self.assertEqual(len(r.ropes_rope.knots), 1)
        r.ropes_rope.anchors.add().position = (1, 1, 0)
        ropes.rebuild(bpy.context.scene, self.target)
        self.assertAlmostEqual(r.ropes_rope.knots[0].distance, .65, places=5)
        self.assertGreater(len(ropes.visible_path(r)), len(ropes.rest_path(r)))
        self.assertFalse(r.data.splines[0].use_cyclic_u)
        ropes.knot_at(bpy.context.scene, r, .65)
        self.assertEqual(len(r.ropes_rope.knots), 0)

    def test_self_crossing(self):
        r = self.rope((-1.3, -1.3, 0), (1.3, 1.3, 0), (-1.3, 1.3, 0), (1.3, -1.3, 0))
        j = [j for j in self.settings.junctions if j.rope_a == r and j.rope_b == r]
        self.assertEqual(len(j), 1)
        self.assertTrue(j[0].over_a)
        station = j[0].distance_b
        ropes.knot_at(bpy.context.scene, r, station)
        self.assertTrue(self.settings.junctions[0].is_knot)
        junction=self.settings.junctions[0]
        for over_a in (True,False):
            junction.over_a=over_a
            records=ropes.knot_records(bpy.context.scene,r)
            self.assertEqual(next(k['component'] for k in records if abs(k['station']-junction.distance_a)<1e-6),0 if over_a else 1)
            self.assertEqual(next(k['component'] for k in records if abs(k['station']-junction.distance_b)<1e-6),1 if over_a else 0)

    def test_compression_reversible_and_removing_last_rope(self):
        r = self.rope((-1.5, 0, 0), (1.5, 0, 0))
        before = [v.co.copy() for v in self.target.data.vertices]
        r.ropes_rope.squish = .8
        key = self.target.data.shape_keys.key_blocks[self.target['ropes_compression_key']]
        self.assertEqual(key.value, 1)
        self.assertTrue(any(p.co.z < -.005 for p in key.data))
        self.assertEqual([tuple(v.co) for v in self.target.data.vertices], [tuple(v) for v in before])
        self.assertAlmostEqual(min(p.z for p in ropes.visible_path(r)), self.settings.radius*1.05-self.settings.radius*.8, delta=.002)
        r.ropes_rope.squish = 0
        self.assertEqual(key.value, 0)
        r.ropes_rope.squish = .8
        self.settings.active_rope = r
        self.assertEqual(bpy.ops.ropes.remove(), {'FINISHED'})
        self.assertEqual(key.value, 0)
        self.assertEqual(len(ropes.rope_objects(bpy.context.scene, self.target)), 0)

    def test_rename_preserves_order_and_crossing_state(self):
        a = self.rope((-1.5, 0, 0), (1.5, 0, 0))
        b = self.rope((0, -1.5, 0), (0, 1.5, 0))
        a.name, b.name = 'Z first rope', 'A later rope'
        self.settings.junctions[0].over_a = False
        self.settings.junctions[0].is_knot = True
        ropes.rebuild(bpy.context.scene, self.target)
        self.assertEqual(self.settings.junctions[0].rope_a, a)
        self.assertFalse(self.settings.junctions[0].over_a)
        self.assertTrue(self.settings.junctions[0].is_knot)

    def test_existing_shape_keys_preserved(self):
        self.target.shape_key_add(name='Basis')
        existing = self.target.shape_key_add(name='User sculpt')
        existing.data[0].co.z = .3
        existing.value = .4
        before = [tuple(p.co) for p in existing.data]
        r = self.rope((-1.5, 0, 0), (1.5, 0, 0))
        r.ropes_rope.squish = .7
        self.assertEqual([tuple(p.co) for p in existing.data], before)
        self.assertAlmostEqual(existing.value, .4)
        self.assertNotEqual(self.target['ropes_compression_key'], existing.name)

    def test_shared_mesh_compression_reports_error(self):
        r = self.rope((-1.5, 0, 0), (1.5, 0, 0))
        other = bpy.data.objects.new('Shared user', self.target.data)
        bpy.context.scene.collection.objects.link(other)
        r.ropes_rope.squish = .5
        self.assertIn('single-user', self.settings.message)
        self.assertIsNone(self.target.data.shape_keys)

    def test_projected_mouse_clicks_from_sidebar_context(self):
        area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
        region = next(r for r in area.regions if r.type == 'WINDOW')
        ui = next(r for r in area.regions if r.type == 'UI')
        rv3d = area.spaces.active.region_3d
        errors = []
        operator = SimpleNamespace(surface=Surface(self.target, 1), target=self.target,
                                   area=area, region=region, rv3d=rv3d, rope=None,
                                   undo_history=[], redo_history=[],
                                   report=lambda level, message: errors.append(message))
        operator.finish = lambda context: ropes.ROPES_OT_Draw.finish(operator, context)
        # Panel buttons invoke from the sidebar, whose region_data is None.
        context = SimpleNamespace(scene=bpy.context.scene, area=area, region=ui,
                                  region_data=None)

        def click(point, kind='LEFTMOUSE'):
            xy = view3d_utils.location_3d_to_region_2d(region, rv3d, Vector(point))
            event = SimpleNamespace(type=kind, value='PRESS', alt=False,
                                    mouse_x=xy.x+region.x, mouse_y=xy.y+region.y,
                                    mouse_region_x=-1, mouse_region_y=-1)
            return ropes.ROPES_OT_Draw.modal(operator, context, event)

        click((-1, 0, 0))
        click((1, 0, 0))
        self.assertEqual(len(operator.rope.ropes_rope.anchors), 2)
        self.assertFalse(errors, errors)
        self.assertLess((Vector(operator.rope.ropes_rope.anchors[0].position)-Vector((-1, 0, 0))).length, .01)  # Within one screen pixel
        path = ropes.visible_path(operator.rope)
        middle = path[len(path)//2]
        click(middle, 'RIGHTMOUSE')
        self.assertEqual(len(operator.rope.ropes_rope.knots), 1)
        stations = json.loads(operator.rope['ropes_stations'])
        knot_s = operator.rope.ropes_rope.knots[0].distance
        knot_index = next(i for i, s in enumerate(stations) if abs(s-knot_s) < 1e-5)
        click(ropes.visible_path(operator.rope)[knot_index], 'RIGHTMOUSE')
        self.assertEqual(len(operator.rope.ropes_rope.knots), 0)
        self.assertEqual(ropes.ROPES_OT_Draw.modal(operator, context,
                         SimpleNamespace(type='N', value='PRESS')), {'RUNNING_MODAL'})
        self.assertIsNone(operator.rope)
        self.assertEqual(ropes.ROPES_OT_Draw.modal(operator, context,
                         SimpleNamespace(type='ESC', value='PRESS')), {'FINISHED'})

    def test_independent_settings_and_live_width(self):
        a = self.rope((-1.5, -.8, 0), (1.5, -.8, 0))
        b = self.rope((-1.5, .8, 0), (1.5, .8, 0))
        before_b = [tuple(p) for p in ropes.visible_path(b)]
        props_b = {name: getattr(b.ropes_rope, name) for name in ropes.COPY_SETTINGS}
        a.ropes_rope.squish = .8
        a.ropes_rope.tension = .9
        a.ropes_rope.falloff = 2
        a.ropes_rope.radius = .06
        self.assertFalse(self.settings.message, self.settings.message)
        self.assertEqual({name: getattr(b.ropes_rope, name) for name in ropes.COPY_SETTINGS}, props_b)
        self.assertEqual([tuple(p) for p in ropes.visible_path(b)], before_b)
        helpers = [o for o in bpy.context.scene.objects if o.get('ropes_owner') == a.ropes_rope.uid]
        self.assertEqual(len(helpers), 3)
        self.assertTrue(all(abs(o['ropes_tube_radius']-.06*.46) < 1e-6 for o in helpers))
        key = self.target.data.shape_keys.key_blocks[self.target['ropes_compression_key']]
        near_a = min(key.data, key=lambda p: abs(p.co.x)+abs(p.co.y+.8))
        near_b = min(key.data, key=lambda p: abs(p.co.x)+abs(p.co.y-.8))
        self.assertLess(near_a.co.z, -.02)
        self.assertAlmostEqual(near_b.co.z, 0, places=6)
        a.ropes_rope.squish = 0
        self.assertEqual(key.value, 0)
        # Defaults affect future ropes only.
        self.settings.radius = .1
        self.settings.squish = .3
        self.assertAlmostEqual(a.ropes_rope.radius, .06)
        self.assertAlmostEqual(b.ropes_rope.squish, 0)
        c = self.rope((-1, 1.6, 0), (1, 1.6, 0))
        self.assertAlmostEqual(c.ropes_rope.radius, .1)
        self.assertAlmostEqual(c.ropes_rope.squish, .3)

    def test_width_update_preserves_strand_selection_and_unequal_crossing(self):
        a = self.rope((-1.5, 0, 0), (1.5, 0, 0))
        b = self.rope((0, -1.5, 0), (0, 1.5, 0))
        helper = next(o for o in bpy.context.scene.objects if o.get('ropes_owner') == b.ropes_rope.uid)
        bpy.context.view_layer.objects.active = helper
        b.ropes_rope.radius = .1
        a.ropes_rope.radius = .015
        self.assertEqual(bpy.context.active_object, helper)
        self.assertEqual(bpy.ops.ropes.use_selected_rope(), {'FINISHED'})
        self.assertEqual(self.settings.active_rope, b)
        j = self.settings.junctions[0]
        pa, _ = ropes.sample_at(ropes.visible_path(a), cumulative(ropes.rest_path(a)), j.distance_a)
        pb, _ = ropes.sample_at(ropes.visible_path(b), cumulative(ropes.rest_path(b)), j.distance_b)
        self.assertGreater(pa.z-pb.z, a.ropes_rope.radius+b.ropes_rope.radius)

    def test_smoothing_zero_to_exact_straight_line(self):
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=5, y_subdivisions=8, size=4)
        grid = bpy.context.object
        self.target = grid
        self.settings.target = grid
        self.settings.subdivisions = 0
        self.settings.smoothing = 0
        start, end = Vector((-1.7, -1.25, 0)), Vector((1.5, 1.4, 0))
        r = self.rope(start, end)
        raw = ropes.rest_path(r)
        direct_length = (end-start).length
        self.assertGreater(cumulative(raw)[-1], direct_length*1.01)
        r.ropes_rope.smoothing = .5
        middle_length = cumulative(ropes.rest_path(r))[-1]
        r.ropes_rope.smoothing = 1
        smooth = ropes.rest_path(r)
        self.assertAlmostEqual(cumulative(smooth)[-1], direct_length, places=5)
        self.assertLess(middle_length, cumulative(raw)[-1])
        self.assertGreater(middle_length, direct_length)
        for p in smooth:
            self.assertLess(ropes.point_segment_distance(p, start, end), 1e-5)
        self.assertTrue(all(p.z >= r.ropes_rope.radius for p in ropes.visible_path(r)))

    def test_smoothed_curved_rope_clearance(self):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=2)
        self.target = bpy.context.object
        self.settings.target = self.target
        r = self.rope((2, 0, 0), (0, 0, 2))
        surface = Surface(self.target, 0)
        for a, b in zip(ropes.visible_path(r), ropes.visible_path(r)[1:]):
            for p in (a, a.lerp(b, .5)):
                nearest, normal, _ = surface.project(p)
                self.assertGreater((p-nearest).dot(normal), r.ropes_rope.radius*.9)

    def test_undo_redo_multiple_placements_and_new_rope(self):
        scene = bpy.context.scene
        first = self.rope((-1.3, 0, 0), (0, 0, 0))
        uid = first.ropes_rope.uid
        state = ropes.capture_state(scene, self.target, first)
        first.ropes_rope.anchors.add().position = (1.3, 0, 0)
        ropes.rebuild(scene, self.target)
        area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
        operator = SimpleNamespace(target=self.target, rope=first, area=area,
                                   undo_history=[state], redo_history=[], report=lambda *args: None)
        context = SimpleNamespace(scene=scene)
        undo = SimpleNamespace(type='Z', value='PRESS', ctrl=True, shift=False)
        redo = SimpleNamespace(type='Z', value='PRESS', ctrl=True, shift=True)
        ropes.ROPES_OT_Draw.modal(operator, context, undo)
        self.assertEqual(operator.rope.ropes_rope.uid, uid)
        self.assertEqual(len(operator.rope.ropes_rope.anchors), 2)
        ropes.ROPES_OT_Draw.modal(operator, context, redo)
        self.assertEqual(len(operator.rope.ropes_rope.anchors), 3)
        before_new = ropes.capture_state(scene, self.target, None)
        operator.rope = self.rope((0, -.9, 0), (0, .9, 0))
        operator.undo_history.append(before_new)
        ropes.ROPES_OT_Draw.modal(operator, context, SimpleNamespace(type='BACK_SPACE', value='PRESS'))
        self.assertEqual(len(ropes.rope_objects(scene, self.target)), 1)
        self.assertIsNone(operator.rope)
        ropes.ROPES_OT_Draw.modal(operator, context, redo)
        self.assertEqual(len(ropes.rope_objects(scene, self.target)), 2)
        self.assertEqual(len(scene.ropes_settings.junctions), 1)

    def test_remove_last_point_operator_and_strand_material(self):
        r = self.rope((-1.5, 0, 0), (0, 0, 0), (1.5, .8, 0))
        self.assertEqual(bpy.ops.ropes.remove_last_point(), {'FINISHED'})
        self.assertEqual(len(r.ropes_rope.anchors), 2)
        self.assertLess((ropes.rest_path(r)[-1]-Vector((0, 0, 0))).length, 1e-5)
        helpers = [o for o in bpy.context.scene.objects if o.get('ropes_owner') == r.ropes_rope.uid]
        self.assertEqual(len(helpers), 3)
        self.assertTrue(all(o.data.materials[0].use_nodes for o in helpers))
        self.assertTrue(any(n.type == 'BUMP' for n in helpers[0].data.materials[0].node_tree.nodes))
        vertices = helpers[0].data.vertices
        strand = [helpers[0].matrix_world @ (sum((v.co for v in vertices[i:i+10]), Vector())/10)
                  for i in range(0, len(vertices), 10)]
        self.assertIsNotNone(helpers[0].data.uv_layers.get('FiberUV'))
        self.assertGreater(max(p.uv.x for p in helpers[0].data.uv_layers.active.data), 1)
        self.assertGreater(cumulative(strand)[-1], cumulative(ropes.visible_path(r))[-1]*1.01)
        uid = r.ropes_rope.uid
        self.assertEqual(bpy.ops.ropes.remove(), {'FINISHED'})
        self.assertFalse(any(o.get('ropes_owner') == uid for o in bpy.context.scene.objects))

    def test_legacy_settings_migration(self):
        r = self.rope((-1, 0, 0), (1, 0, 0))
        self.settings.radius = .08
        self.settings.squish = .6
        self.settings.tension = .7
        with ropes.quiet_updates():
            r.ropes_rope.initialized = False
        ropes.migrate_on_load(None)
        self.assertTrue(r.ropes_rope.initialized)
        self.assertAlmostEqual(r.ropes_rope.radius, .08)
        self.assertAlmostEqual(r.ropes_rope.squish, .6)
        self.assertAlmostEqual(r.ropes_rope.tension, .7)
        self.assertEqual(r.ropes_rope.smoothing, 0)
        r.ropes_rope.squish = .2
        ropes.migrate_on_load(None)
        self.assertAlmostEqual(r.ropes_rope.squish, .2)

    def test_waypoint_markers_toggle_and_relocation(self):
        r = self.rope((-1, 0, 0), (0, .5, 0), (1, 0, 0))
        self.settings.show_waypoints = True
        markers = [o for o in bpy.context.scene.objects if 'ropes_waypoint' in o]
        self.assertEqual(len(markers), 3)
        self.assertTrue(all(o.hide_render and not o.show_in_front for o in markers))
        original = ropes.capture_state(bpy.context.scene, self.target, r)
        ropes.move_waypoint(bpy.context.scene, r, 1, (0, -.7, .8))
        self.assertLess((Vector(r.ropes_rope.anchors[1].position)-Vector((0, -.7, 0))).length, 1e-5)
        self.assertEqual(tuple(r.ropes_rope.anchors[0].position), (-1, 0, 0))
        self.assertEqual(tuple(r.ropes_rope.anchors[2].position), (1, 0, 0))
        self.assertTrue(any((p-Vector((0, -.7, 0))).length < 1e-5 for p in ropes.rest_path(r)))
        ropes.restore_state(bpy.context.scene, self.target, original)
        self.assertAlmostEqual(r.ropes_rope.anchors[1].position[1], .5)
        self.settings.show_waypoints = False
        self.assertFalse(any('ropes_waypoint' in o for o in bpy.context.scene.objects))
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.get('ropes_helper')]), 3)

    def test_projected_waypoint_select_move_undo_and_redo(self):
        self.settings.waypoint_xray = True
        r = self.rope((-1, 0, 0), (0, .6, 0), (1, 0, 0))
        self.settings.show_waypoints = True
        area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
        region = next(x for x in area.regions if x.type == 'WINDOW')
        rv3d = area.spaces.active.region_3d
        operator = SimpleNamespace(target=self.target, rope=r, surface=Surface(self.target, 0),
                                   area=area, region=region, rv3d=rv3d, moving_waypoint=None,
                                   undo_history=[], redo_history=[], report=lambda *args: None)
        context = SimpleNamespace(scene=bpy.context.scene, area=area)
        def click(point):
            xy = view3d_utils.location_3d_to_region_2d(region, rv3d, Vector(point))
            event = SimpleNamespace(type='LEFTMOUSE', value='PRESS', alt=False,
                                    mouse_x=xy.x+region.x, mouse_y=xy.y+region.y)
            ropes.ROPES_OT_Draw.modal(operator, context, event)
        marker = next(o for o in bpy.context.scene.objects if o.get('ropes_waypoint') == 1)
        click(marker.matrix_world.translation)
        self.assertEqual(operator.moving_waypoint, (r.ropes_rope.uid, 1))
        click((0, -.6, 0))
        self.assertIsNone(operator.moving_waypoint)
        self.assertEqual(len(r.ropes_rope.anchors), 3)
        self.assertAlmostEqual(r.ropes_rope.anchors[1].position[1], -.6, delta=.01)
        ropes.ROPES_OT_Draw.modal(operator, context, SimpleNamespace(type='Z', value='PRESS', ctrl=True, shift=False))
        self.assertAlmostEqual(r.ropes_rope.anchors[1].position[1], .6)
        ropes.ROPES_OT_Draw.modal(operator, context, SimpleNamespace(type='Z', value='PRESS', ctrl=True, shift=True))
        self.assertAlmostEqual(r.ropes_rope.anchors[1].position[1], -.6, delta=.01)

    def test_knot_footprint_compresses_off_original_path(self):
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=61, y_subdivisions=61, size=4)
        self.target = bpy.context.object
        self.settings.target = self.target
        self.settings.radius = .08
        r = self.rope((-1.5, 0, 0), (1.5, 0, 0))
        r.ropes_rope.falloff = 1
        r.ropes_rope.squish = .8
        key = self.target.data.shape_keys.key_blocks[self.target['ropes_compression_key']]
        before = [p.co.z for p in key.data]
        ropes.knot_at(bpy.context.scene, r, 1.5)
        surface = Surface(self.target, 0)
        physical, _ = ropes.display_path(bpy.context.scene, r, surface, ropes.rest_path(r))
        off_center = [surface.project(p)[0] for p in physical if abs(p.y) > .14]
        self.assertTrue(off_center)
        field = ropes.PressureField(bpy.context.scene, self.target)
        self.assertGreater(max(field.value(p) for p in off_center), .05)
        changes = [old-p.co.z for old, p, v in zip(before, key.data, self.target.data.vertices)
                   if abs(v.co.y) > .12]
        self.assertGreater(max(changes), .015)
        ropes.knot_at(bpy.context.scene, r, 1.5)
        self.assertLess(max(abs(old-p.co.z) for old,p in zip(before,key.data)), 1e-5)

    def test_knot_styles_overrides_and_junction_preservation(self):
        r = self.rope((-1.5, 0, 0), (1.5, 0, 0))
        ropes.knot_at(bpy.context.scene, r, 1.2)
        overhand = [tuple(p) for p in ropes.visible_path(r)]
        r.ropes_rope.knot_type = 'FIGURE_EIGHT'
        eight = [tuple(p) for p in ropes.visible_path(r)]
        self.assertNotEqual(overhand, eight)
        r.ropes_rope.knots[0].kind = 'OVERHAND'
        self.assertEqual(overhand, [tuple(p) for p in ropes.visible_path(r)])
        r.ropes_rope.knots[0].kind = 'TREFOIL'
        self.assertGreater(max(abs(p.y) for p in ropes.visible_path(r)),
                           max(abs(p[1]) for p in overhand))
        b = self.rope((0, -1.5, 0), (0, 1.5, 0))
        j = self.settings.junctions[0]
        j.is_knot = True
        j.kind = 'FIGURE_EIGHT'
        ropes.rebuild(bpy.context.scene, self.target)
        self.assertEqual(self.settings.junctions[0].kind, 'FIGURE_EIGHT')

    def test_doubled_rope_fold_runs_and_compression(self):
        r = self.rope((-1, 0, 0), (1, 0, 0))
        original = cumulative(ropes.visible_path(r))[-1]
        r.ropes_rope.doubled = True
        path = ropes.visible_path(r)
        self.assertGreater(cumulative(path)[-1], original*2)
        separation = r.ropes_rope.radius*2.02*r.ropes_rope.double_spacing
        self.assertAlmostEqual((path[0]-path[-1]).length, separation, places=5)
        self.assertAlmostEqual(path[0].x, 1, places=5)
        self.assertAlmostEqual(path[-1].x, 1, places=5)
        self.assertLess(min(p.x for p in path), -1)
        mapping = json.loads(r['ropes_stations'])
        self.assertEqual(len(mapping), len(path))
        self.assertAlmostEqual(mapping[0], 2, places=5)
        self.assertAlmostEqual(min(mapping), 0, places=5)
        self.assertAlmostEqual(mapping[-1], 2, places=5)
        r.ropes_rope.double_spacing = 4
        r.ropes_rope.falloff = 1
        r.ropes_rope.squish = .8
        field = ropes.PressureField(bpy.context.scene, self.target)
        half = r.ropes_rope.radius*4.04
        self.assertGreater(field.value(Vector((0, half, 0))), field.value(Vector((0, 0, 0)))*3)
        self.assertGreater(field.value(Vector((0, -half, 0))), field.value(Vector((0, 0, 0)))*3)
        ropes.knot_at(bpy.context.scene, r, 1)
        self.assertTrue(all(math.isfinite(v) for p in ropes.visible_path(r) for v in p))
        r.ropes_rope.doubled = False
        self.assertGreater(len(ropes.visible_path(r)), len(ropes.rest_path(r)))
        self.assertFalse(self.settings.message, self.settings.message)

    def test_waypoint_move_keeps_knot_at_anchor_and_crossing_choice(self):
        r = self.rope((-1, 0, 0), (0, .5, 0), (1, 0, 0))
        old_bounds = json.loads(r['ropes_leg_bounds'])
        ropes.knot_at(bpy.context.scene, r, old_bounds[1])
        r.ropes_rope.knots[0].kind = 'FIGURE_EIGHT'
        state = ropes.capture_state(bpy.context.scene, self.target, r)
        ropes.move_waypoint(bpy.context.scene, r, 1, (0, -.8, 0))
        new_bounds = json.loads(r['ropes_leg_bounds'])
        self.assertAlmostEqual(r.ropes_rope.knots[0].distance, new_bounds[1], places=5)
        self.assertEqual(r.ropes_rope.knots[0].kind, 'FIGURE_EIGHT')
        ropes.restore_state(bpy.context.scene, self.target, state)
        self.assertAlmostEqual(r.ropes_rope.knots[0].distance, old_bounds[1], places=5)
        # A lone junction between a pair retains its choices when it moves.
        b = self.rope((0, -1.8, 0), (0, 1.8, 0))
        self.settings.junctions[0].over_a = False
        self.settings.junctions[0].is_knot = True
        self.settings.junctions[0].kind = 'FIGURE_EIGHT'
        ropes.move_waypoint(bpy.context.scene, r, 1, (0, -1.2, 0))
        j = self.settings.junctions[0]
        self.assertFalse(j.over_a)
        self.assertTrue(j.is_knot)
        self.assertEqual(j.kind, 'FIGURE_EIGHT')

    def test_draft_waypoints_generate_only_on_request(self):
        self.settings.waypoint_mode=True
        self.settings.squish=.8
        r=self.rope((-1,0,0),(0,.6,0),(1,0,0))
        self.assertFalse(r.ropes_rope.generated)
        self.assertFalse(r.data.splines)
        self.assertFalse(any(o.get('ropes_helper') for o in bpy.context.scene.objects))
        self.assertIsNone(self.target.data.shape_keys)
        self.assertEqual(len([o for o in bpy.context.scene.objects if 'ropes_waypoint' in o]),3)
        ropes.move_waypoint(bpy.context.scene,r,1,(0,-.5,0))
        self.assertFalse(r.data.splines)
        self.assertEqual(bpy.ops.ropes.generate(),{'FINISHED'})
        self.assertTrue(r.ropes_rope.generated)
        self.assertTrue(r.data.splines)
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.get('ropes_helper')]),3)
        self.assertIsNotNone(self.target.data.shape_keys)

    def test_failed_draft_generation_preserves_plan(self):
        self.settings.waypoint_mode=True
        r=ropes.new_rope(bpy.context.scene,self.target)
        r.ropes_rope.anchors.add().position=(0,0,0)
        with self.assertRaisesRegex(RuntimeError, 'at least two waypoints'):
            bpy.ops.ropes.generate()
        self.assertFalse(r.ropes_rope.generated)
        self.assertEqual(len(r.ropes_rope.anchors),1)

    def test_spanning_direct_gap_and_zero_deformation(self):
        bm=bmesh.new()
        for x in (-1.5,1.5):
            verts=[bm.verts.new((x+dx,y,0)) for dx,y in ((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5))]
            bm.faces.new(verts)
        mesh=bpy.data.meshes.new('Gap mesh')
        bm.to_mesh(mesh)
        bm.free()
        self.target=bpy.data.objects.new('Gap surface',mesh)
        bpy.context.scene.collection.objects.link(self.target)
        self.settings.target=self.target
        self.settings.waypoint_mode=True
        r=ropes.new_rope(bpy.context.scene,self.target)
        with ropes.quiet_updates():
            for p in ((-1,0,0),(1,0,0)):
                a=r.ropes_rope.anchors.add()
                a.position=p
                a.kind='SPANNING'
            r.ropes_rope.squish=1
            r.ropes_rope.tension=1
        self.assertEqual(bpy.ops.ropes.generate(),{'FINISHED'})
        points=ropes.visible_path(r)
        self.assertAlmostEqual(cumulative(points)[-1],2,places=4)
        self.assertTrue(all(abs(p.y)<1e-5 for p in points))
        self.assertFalse(ropes.PressureField(bpy.context.scene,self.target).contacts)
        self.assertIsNone(self.target.data.shape_keys)
        r.ropes_rope.doubled=True
        self.assertFalse(self.settings.message,self.settings.message)
        self.assertGreater(cumulative(ropes.visible_path(r))[-1],4)
        self.assertIsNone(self.target.data.shape_keys)

    def test_spanning_obstacle_clearance(self):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,radius=1)
        self.target=bpy.context.object
        self.settings.target=self.target
        self.settings.waypoint_mode=True
        r=ropes.new_rope(bpy.context.scene,self.target)
        with ropes.quiet_updates():
            for p in ((-1,0,0),(1,0,0)):
                a=r.ropes_rope.anchors.add()
                a.position=p
                a.kind='SPANNING'
        self.assertEqual(bpy.ops.ropes.generate(),{'FINISHED'})
        path=ropes.visible_path(r)
        surface=Surface(self.target,0)
        from ropes.geometry import segment_clear
        self.assertGreater(cumulative(path)[-1],2.5)
        self.assertTrue(all(segment_clear(surface,a,b,r.ropes_rope.radius*1.01) for a,b in zip(path,path[1:])))

    def test_mixed_waypoint_rules_and_contact_mask(self):
        r=self.rope((-1.5,0,0),(-.5,0,0),(.5,0,0),(1.5,0,0))
        with ropes.quiet_updates():
            r.ropes_rope.anchors[1].kind='SPANNING'
            r.ropes_rope.anchors[2].kind='SPANNING'
            r.ropes_rope.squish=1
            r.ropes_rope.falloff=1
        ropes.rebuild(bpy.context.scene,self.target)
        self.assertEqual(json.loads(r['ropes_span_flags']),[False,True,False])
        field=ropes.PressureField(bpy.context.scene,self.target)
        self.assertGreater(field.value(Vector((-1,0,0))),.03)
        self.assertLess(field.value(Vector((0,0,0))),1e-8)
        self.assertGreater(field.value(Vector((1,0,0))),.03)
        # One spanning end alone has ordinary surface behavior.
        r.ropes_rope.anchors[2].kind='NORMAL'
        self.assertEqual(json.loads(r['ropes_span_flags']),[False,False,False])
        self.assertGreater(ropes.PressureField(bpy.context.scene,self.target).value(Vector((0,0,0))),.03)

    def test_clicked_rope_knots_around_straight_passive_and_toggles_back(self):
        a=self.rope((-1.5,0,0),(1.5,0,0))
        b=self.rope((0,-1.5,0),(0,1.5,0))
        before_a=[tuple(p) for p in ropes.visible_path(a)]
        before_b=[tuple(p) for p in ropes.visible_path(b)]
        j=self.settings.junctions[0]
        for active in (a,b):
            distance=j.distance_a if active==a else j.distance_b
            ropes.knot_at(bpy.context.scene,active,distance)
            self.assertTrue(j.is_knot)
            self.assertEqual(ropes.junction_active_a(j),active==a)
            passive=b if active==a else a
            active_record=ropes.knot_records(bpy.context.scene,active)[0]
            passive_record=ropes.knot_records(bpy.context.scene,passive)[0]
            self.assertEqual(active_record['component'],0)
            self.assertEqual(passive_record['component'],1)
            points=ropes.visible_path(passive)
            stations=json.loads(passive['ropes_stations'])
            core=[p for p,st in zip(points,stations) if abs(st-passive_record['station'])<1e-6]
            axis=Vector((0,1,0)) if passive==b else Vector((1,0,0))
            for p in core:
                self.assertLess((p-core[0]).cross(axis).length,1e-6)
            ropes.knot_at(bpy.context.scene,active,distance)
            self.assertEqual(before_a,[tuple(p) for p in ropes.visible_path(a)])
            self.assertEqual(before_b,[tuple(p) for p in ropes.visible_path(b)])

    def test_doubled_overhand_minimum_is_tighter(self):
        r=self.rope((-1.5,0,0),(1.5,0,0))
        r.ropes_rope.doubled=True
        ropes.knot_at(bpy.context.scene,r,1.5)
        points=ropes.visible_path(r)
        width=max(p.y for p in points)-min(p.y for p in points)
        # 0.3 used 2.1 radii for the core plus a 1.1-radius lane offset;
        # require a substantially narrower minimum-size knot footprint.
        previous_width=2*(2.55*2.1+1.1)*r.ropes_rope.radius
        self.assertLess(width,previous_width*.85)
        r.ropes_rope.knot_size=1.5
        larger=ropes.visible_path(r)
        self.assertGreater(max(p.y for p in larger)-min(p.y for p in larger),width)

    def test_valley_centerline_stays_straight_without_false_crossings(self):
        # Dense channel with a hard concave crease and alternating triangles.
        verts=[(-1.2+i*.06, -.4+j*.1, abs(-.4+j*.1)) for i in range(41) for j in range(9)]
        faces=[(i*9+j,(i+1)*9+j,(i+1)*9+j+1,i*9+j+1) for i in range(40) for j in range(8)]
        mesh=bpy.data.meshes.new('Creased valley')
        mesh.from_pydata(verts,[],faces)
        self.target=bpy.data.objects.new('Creased valley',mesh)
        bpy.context.scene.collection.objects.link(self.target)
        self.settings.target=self.target
        r=self.rope((-1,0,0),(1,0,0))
        points=ropes.visible_path(r)
        self.assertEqual(len(self.settings.junctions),0)
        self.assertLess(max(abs(p.y) for p in points),r.ropes_rope.radius*.15)
        self.assertLess(cumulative(points)[-1],2.01)
        surface=Surface(self.target,0)
        self.assertTrue(all((p-surface.project(p)[0]).length>=r.ropes_rope.radius for p in points))
        r.ropes_rope.doubled=True
        self.assertFalse(self.settings.message,self.settings.message)
        points=ropes.visible_path(r)
        # Ignore the intentional folded end; both long runs remain straight.
        tangents=[(b-a).normalized() for a,b in zip(points,points[1:]) if a.x>-.9 and b.x>-.9]
        self.assertTrue(all(abs(t.x)>.99 for t in tangents))
        # Contact resolution must not squeeze the two runs into the same groove.
        self.assertAlmostEqual((points[0]-points[-1]).length/r.ropes_rope.radius,2.02,places=4)
        for p in points:
            if p.x>-.9:
                self.assertGreaterEqual((p-surface.project(p)[0]).length,r.ropes_rope.radius*.99)
        r.ropes_rope.squish=.7
        self.assertFalse(self.settings.message,self.settings.message)
        self.assertEqual(len(self.settings.junctions),0)
        points=ropes.visible_path(r)
        tangents=[(b-a).normalized() for a,b in zip(points,points[1:]) if abs(a.x)<.8 and abs(b.x)<.8]
        self.assertTrue(all(abs(t.x)>.99 for t in tangents))

    def test_span_contacts_and_mixed_transition_have_no_height_step(self):
        r=self.rope((-1.5,0,0),(-.5,0,0),(.5,0,0),(1.5,0,0))
        with ropes.quiet_updates():
            r.ropes_rope.anchors[1].kind='SPANNING'
            r.ropes_rope.anchors[2].kind='SPANNING'
        ropes.rebuild(bpy.context.scene,self.target)
        for doubled in (False,True):
            r.ropes_rope.doubled=doubled
            self.assertFalse(self.settings.message,self.settings.message)
            points=ropes.visible_path(r)
            self.assertLess(max(p.z for p in points)-min(p.z for p in points),1e-5)
            self.assertAlmostEqual(points[-1].z,r.ropes_rope.radius*1.05,places=5)
        r.ropes_rope.squish=1
        r.ropes_rope.tension=1
        points=ropes.visible_path(r)
        turns=[(b-a).normalized().dot((c-b).normalized()) for a,b,c in zip(points,points[1:],points[2:]) if min(a.x,b.x,c.x)>-.8]
        self.assertTrue(all(t>.95 for t in turns),min(turns))
        # Inspection markers remain at contact locations when compression is off.
        r.ropes_rope.squish=0
        self.settings.show_waypoints=True
        bpy.context.view_layer.update()
        markers=[o for o in bpy.context.scene.objects if 'ropes_waypoint' in o]
        self.assertEqual(len(markers),4)
        for marker in markers:
            anchor=r.ropes_rope.anchors[marker['ropes_waypoint']]
            self.assertLess((marker.matrix_world.translation-Vector(anchor.position)).length,1e-6)

    def test_minimum_run_spacing_is_one_and_nearly_touching(self):
        r=self.rope((-1,0,0),(1,0,0))
        r.ropes_rope.doubled=True
        r.ropes_rope.double_spacing=1
        points=ropes.visible_path(r)
        self.assertEqual(r.ropes_rope.double_spacing,1)
        self.assertAlmostEqual((points[0]-points[-1]).length/r.ropes_rope.radius,2.02,places=5)
        r.ropes_rope.double_spacing=0
        self.assertEqual(r.ropes_rope.double_spacing,1)

    def test_draft_clicks_moves_and_undo_skip_existing_geometry(self):
        existing=self.rope((-1,-1,0),(1,-1,0))
        before=[tuple(p) for p in ropes.visible_path(existing)]
        self.settings.waypoint_mode=True
        area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
        region=next(r for r in area.regions if r.type=='WINDOW')
        rv3d=area.spaces.active.region_3d
        operator=SimpleNamespace(target=self.target,rope=None,surface=Surface(self.target,0,routing=False),
                                 area=area,region=region,rv3d=rv3d,moving_waypoint=None,
                                 undo_history=[],redo_history=[],report=lambda *args: None)
        context=SimpleNamespace(scene=bpy.context.scene,area=area)
        def click(point):
            bpy.context.view_layer.update()
            xy=view3d_utils.location_3d_to_region_2d(region,rv3d,Vector(point))
            event=SimpleNamespace(type='LEFTMOUSE',value='PRESS',alt=False,mouse_x=xy.x+region.x,mouse_y=xy.y+region.y)
            ropes.ROPES_OT_Draw.modal(operator,context,event)
        with patch.object(ropes,'rebuild',side_effect=AssertionError('Draft rebuilt ropes')), \
             patch.object(ropes,'Surface',side_effect=AssertionError('Draft rebuilt surface')), \
             patch.object(ropes,'PressureField',side_effect=AssertionError('Draft calculated compression')):
            click((-1,0,0))
            click((0,0,0))
            click((1,0,0))
            draft=operator.rope
            self.assertEqual(len(draft.ropes_rope.anchors),3)
            self.assertFalse(draft.data.splines)
            ropes.ROPES_OT_Draw.modal(operator,context,SimpleNamespace(type='Z',value='PRESS',ctrl=True,shift=False))
            self.assertEqual(len(operator.rope.ropes_rope.anchors),2)
            ropes.ROPES_OT_Draw.modal(operator,context,SimpleNamespace(type='Z',value='PRESS',ctrl=True,shift=True))
            self.assertEqual(len(operator.rope.ropes_rope.anchors),3)
            ropes.move_waypoint(bpy.context.scene,operator.rope,1,Vector((0,.5,0)))
            self.assertEqual(len([o for o in bpy.context.scene.objects if 'ropes_waypoint' in o]),3)
        self.assertEqual(before,[tuple(p) for p in ropes.visible_path(existing)])

    def test_waypoint_size_pick_radius_and_solid_occlusion(self):
        r=self.rope((-1,0,0),(0,0,0),(1,0,0))
        self.settings.show_waypoints=True
        marker=next(o for o in bpy.context.scene.objects if o.get('ropes_waypoint')==1)
        previous=marker.empty_display_size
        self.settings.waypoint_size=.05
        self.assertLess(marker.empty_display_size,previous/5)
        area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
        region=next(r for r in area.regions if r.type=='WINDOW')
        rv3d=area.spaces.active.region_3d
        pixel=view3d_utils.location_3d_to_region_2d(region,rv3d,marker.matrix_world.translation)
        event=SimpleNamespace(mouse_x=pixel.x+region.x+12,mouse_y=pixel.y+region.y)
        self.assertIsNone(ropes.pick_waypoint(bpy.context,event,self.target,region,rv3d))
        origin=view3d_utils.region_2d_to_origin_3d(region,rv3d,pixel)
        position=origin.lerp(marker.matrix_world.translation,.75)
        bpy.ops.mesh.primitive_cube_add(size=.4,location=position)
        bpy.context.view_layer.update()
        event.mouse_x=pixel.x+region.x
        self.assertIsNone(ropes.pick_waypoint(bpy.context,event,self.target,region,rv3d))
        self.settings.waypoint_xray=True
        self.assertTrue(marker.show_in_front)
        self.assertEqual(ropes.pick_waypoint(bpy.context,event,self.target,region,rv3d),(r.ropes_rope.uid,1))

    def test_generated_rope_returns_to_draft_and_regenerates_choices(self):
        a=self.rope((-1.5,0,0),(0,0,0),(1.5,0,0))
        ropes.knot_at(bpy.context.scene,a,.6)
        b=self.rope((0,-1.5,0),(0,1.5,0))
        j=self.settings.junctions[0]
        j.is_knot=True
        j.over_a=False
        self.settings.active_rope=a
        self.assertEqual(bpy.ops.ropes.edit_waypoints(),{'FINISHED'})
        self.assertFalse(a.ropes_rope.generated)
        self.assertFalse(a.data.splines)
        self.assertTrue(self.settings.waypoint_mode)
        uid=a.ropes_rope.uid
        bpy.ops.wm.save_as_mainfile(filepath='/tmp/ropes-draft-edit.blend')
        bpy.ops.wm.open_mainfile(filepath='/tmp/ropes-draft-edit.blend')
        self.settings=bpy.context.scene.ropes_settings
        a=next(o for o in bpy.context.scene.objects if o.ropes_rope.uid==uid)
        self.assertTrue(a.get('ropes_draft_source'))
        with patch.object(ropes,'rebuild',side_effect=AssertionError('Draft rebuilt')), \
             patch.object(ropes,'Surface',side_effect=AssertionError('Draft routed')):
            ropes.move_waypoint(bpy.context.scene,a,1,(0,.2,0))
            anchor=a.ropes_rope.anchors.add()
            anchor.position=(1.7,.4,0)
            ropes.refresh_draft_markers(bpy.context.scene,a)
        self.assertEqual(bpy.ops.ropes.generate(),{'FINISHED'})
        self.assertTrue(a.ropes_rope.generated)
        self.assertEqual(len(a.ropes_rope.anchors),4)
        self.assertEqual(len(a.ropes_rope.knots),1)
        self.assertAlmostEqual(a.ropes_rope.knots[0].distance,.6*math.sqrt(1.5**2+.2**2)/1.5,delta=.005)
        self.assertEqual(len(self.settings.junctions),1)
        self.assertTrue(self.settings.junctions[0].is_knot)
        self.assertFalse(self.settings.junctions[0].over_a)

    def test_doubled_variable_width_coarse_valley_has_no_spikes(self):
        xs=[-1.5+i*.1 for i in range(31)]
        ys=[-.5,-.12,0,.12,.5]
        vertices=[(x,y,(.25+.18*math.cos(x*6))*min(1,abs(y)/.12)) for x in xs for y in ys]
        faces=[(i*5+j,(i+1)*5+j,(i+1)*5+j+1,i*5+j+1) for i in range(30) for j in range(4)]
        mesh=bpy.data.meshes.new('Variable groove')
        mesh.from_pydata(vertices,[],faces)
        self.target=bpy.data.objects.new('Variable groove',mesh)
        bpy.context.scene.collection.objects.link(self.target)
        self.settings.target=self.target
        self.settings.subdivisions=0
        r=self.rope((-1.4,0,0),(1.4,0,0))
        r.ropes_rope.doubled=True
        points=ropes.visible_path(r)
        self.assertFalse(self.settings.message,self.settings.message)
        self.assertLess(max(p.z for p in points),.32)
        self.assertLess(cumulative(points)[-1],7)
        self.assertEqual(len(self.settings.junctions),0)
        # No local vertical excursions larger than one rope diameter.
        self.assertLess(max(abs(a.z-b.z) for a,b in zip(points,points[1:])),r.ropes_rope.radius*2)

    def test_knot_entry_tangents_and_compact_shared_core(self):
        from ropes.geometry import knot_points,align_knot_entries,junction_points
        tangent=Vector((1,0,0))
        normal=Vector((0,0,1))
        for kind in ('OVERHAND','FIGURE_EIGHT'):
            core=align_knot_entries(knot_points(Vector(),tangent,normal,.05,kind),tangent)
            self.assertGreater((core[1]-core[0]).normalized().dot(tangent),.98)
            self.assertGreater((core[-1]-core[-2]).normalized().dot(tangent),.98)
        from ropes.geometry import point_segment_distance
        for bundle in (1,2.01):
            radius=.05*bundle
            cores=[junction_points(Vector(),Vector((0,1,0)),tangent,normal,radius,radius,c,'OVERHAND') for c in (0,1)]
            gap=min(point_segment_distance(p,a,b) for p in cores[0] for a,b in zip(cores[1],cores[1][1:]))
            self.assertGreater(gap,radius*2)
            for p in cores[1]:
                self.assertAlmostEqual(p.x,0,places=6)
                self.assertAlmostEqual(p.z,cores[1][0].z,places=6)

    def test_junction_entries_clear_other_core_single_and_doubled(self):
        from ropes.geometry import point_segment_distance
        a=self.rope((-1.5,0,0),(1.5,0,0))
        b=self.rope((0,-1.5,0),(0,1.5,0))
        for doubled in (False,True):
            with ropes.quiet_updates():
                a.ropes_rope.doubled=b.ropes_rope.doubled=doubled
            ropes.rebuild(bpy.context.scene,self.target)
            self.settings.junctions[0].is_knot=True
            ropes.rebuild(bpy.context.scene,self.target,repath=False)
            for lead,other in ((a,b),(b,a)):
                points=ropes.visible_path(lead)
                stations=json.loads(lead['ropes_stations'])
                body=ropes.visible_path(other)
                body_stations=json.loads(other['ropes_stations'])
                ca=ropes.knot_records(bpy.context.scene,lead)[0]['station']
                cb=ropes.knot_records(bpy.context.scene,other)[0]['station']
                segments=[(p,q) for i,(p,q) in enumerate(zip(body,body[1:])) if abs(body_stations[i]-cb)<1e-6 and abs(body_stations[i+1]-cb)<1e-6]
                for point,station in zip(points,stations):
                    if 1e-5<abs(station-ca)<lead.ropes_rope.radius*10:
                        gap=min(point_segment_distance(point,p,q) for p,q in segments)
                        self.assertGreaterEqual(gap,lead.ropes_rope.radius*1.95)

    def test_sharp_cube_corner_rounds_at_contact_height(self):
        bpy.ops.mesh.primitive_cube_add(size=2)
        self.target=bpy.context.object
        self.settings.target=self.target
        self.settings.radius=.05
        r=self.rope((-.7,0,1),(1,0,.7),(1,0,-.7))
        for doubled in (False,True):
            r.ropes_rope.doubled=doubled
            points=ropes.visible_path(r)
            radii=[]
            for a,b,c in zip(points,points[1:],points[2:]):
                if b.x<.8 or b.z<.8:
                    continue
                u,v=b-a,c-b
                cross=u.cross(v).length
                if cross>1e-10:
                    radii.append(u.length*v.length*(c-a).length/(2*cross))
            self.assertTrue(radii)
            self.assertGreater(min(radii),r.ropes_rope.radius)
        self.assertLess(max((p-Surface(self.target,1).project(p)[0]).length for p in points if p.x>.8 and p.z>.8),r.ropes_rope.radius*1.2)

        # A distant knot must not disable corner rounding on the rest of a rope.
        ropes.knot_at(bpy.context.scene,r,.25)
        points=ropes.visible_path(r)
        radii=[]
        for a,b,c in zip(points,points[1:],points[2:]):
            if b.x<.8 or b.z<.8:
                continue
            u,v=b-a,c-b
            cross=u.cross(v).length
            if cross>1e-10:
                radii.append(u.length*v.length*(c-a).length/(2*cross))
        self.assertGreater(min(radii),r.ropes_rope.radius)
        self.assertLess(max((p-Surface(self.target,1).project(p)[0]).length for p in points if p.x>.8 and p.z>.8),r.ropes_rope.radius*1.2)

    def test_coarse_monkey_doubled_route_has_no_large_excursions(self):
        bpy.ops.mesh.primitive_monkey_add()
        self.target=bpy.context.object
        self.settings.target=self.target
        self.settings.subdivisions=0
        surface=Surface(self.target,0)
        r=self.rope(surface.project(Vector((-.85,0,.8)))[0],surface.project(Vector((.85,0,.8)))[0])
        r.ropes_rope.doubled=True
        points=ropes.visible_path(r)
        self.assertFalse(self.settings.message,self.settings.message)
        self.assertLess(max(p.z for p in points),1.15)
        self.assertLess(cumulative(points)[-1],5)

    def test_curved_normal_runs_stay_on_contact_envelope(self):
        for shape in ('SPHERE','RIPPLED'):
            if shape=='SPHERE':
                bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,radius=1)
                self.target=bpy.context.object
                anchors=[(1,0,0),(0,0,1)]
            else:
                bpy.ops.mesh.primitive_grid_add(x_subdivisions=151,y_subdivisions=15,size=4)
                self.target=bpy.context.object
                for v in self.target.data.vertices:
                    v.co.z=.11*math.cos(14*v.co.x)+.05*v.co.y*v.co.y
                self.target.data.update()
                anchors=[(x,0,.11*math.cos(14*x)) for x in (-1.5,1.5)]
            self.settings.target=self.target
            self.settings.radius=.05
            self.settings.subdivisions=0
            surface=Surface(self.target,0)
            self.assertFalse(surface.sharp_edges)
            r=self.rope(*(surface.project(Vector(p))[0] for p in anchors))
            for doubled in (False,True):
                with self.subTest(shape=shape,doubled=doubled):
                    r.ropes_rope.doubled=doubled
                    points=ropes.visible_path(r)
                    if shape=='RIPPLED':
                        points=[p for p in points if abs(p.x)<1.2]
                    gaps=[(p-surface.project(p)[0]).length/r.ropes_rope.radius for p in points]
                    self.assertGreaterEqual(min(gaps),.99)
                    # 0.6 lifted these runs to 3.7 and 5 radii on the ripple.
                    self.assertLessEqual(max(gaps),1.2)
                    self.assertFalse(self.settings.message,self.settings.message)

            if shape=='RIPPLED':
                r.ropes_rope.squish=.6
                r.ropes_rope.tension=.7
                bpy.context.view_layer.update()
                deformed=Surface(self.target.evaluated_get(bpy.context.evaluated_depsgraph_get()),0)
                gaps=[(p-deformed.project(p)[0]).length/r.ropes_rope.radius for p in ropes.visible_path(r) if abs(p.x)<1.2]
                self.assertLessEqual(max(gaps),1.2)

    def test_knot_body_ports_align_before_entry_fairing(self):
        from ropes.geometry import knot_points
        center=Vector((.4,-.2,.3))
        tangent=Vector((.6,.8,0))
        normal=Vector((0,0,1))
        body=knot_points(center,tangent,normal,.05,'OVERHAND')
        self.assertGreater((body[-1]-body[0]).normalized().dot(tangent),.9999)
        self.assertAlmostEqual((body[-1]-body[0]).dot(normal),0,places=6)
        # Check the actual body before the short Hermite end corrections. The
        # old body tangents were almost perpendicular despite aligned end caps.
        self.assertGreater((body[1]-body[0]).normalized().dot(tangent),.75)
        self.assertGreater((body[-1]-body[-2]).normalized().dot(tangent),.75)

    def test_waypoint_turn_rounds_at_surface_height(self):
        r=self.rope((-1,0,0),(0,0,0),(0,1,0))
        for doubled in (False,True):
            r.ropes_rope.doubled=doubled
            points=ropes.visible_path(r)
            self.assertTrue(all(abs(p.z-r.ropes_rope.radius*1.05)<1e-5 for p in points))
            radii=[]
            for a,b,c in zip(points,points[1:],points[2:]):
                if abs(b.x)>.4 or abs(b.y)>.4:
                    continue
                u,v=b-a,c-b
                cross=u.cross(v).length
                if cross>1e-10:
                    radii.append(u.length*v.length*(c-a).length/(2*cross))
            self.assertTrue(radii)
            self.assertGreater(min(radii),r.ropes_rope.radius*1.2)

    def test_dense_corner_waypoints_have_contact_and_stable_frames(self):
        from ropes.geometry import uniform_samples
        bpy.ops.mesh.primitive_cube_add(size=2)
        self.target=bpy.context.object
        self.settings.target=self.target
        self.settings.radius=.05
        r=self.rope((-.7,0,1),(.8,0,1),(.95,0,1),(1,0,1),(1,0,.95),(1,0,.8),(1,0,-.7))
        surface=Surface(self.target,1)
        for doubled in (False,True):
            r.ropes_rope.doubled=doubled
            points=ropes.visible_path(r)
            gaps=[(p-surface.project(p)[0]).length for p in points]
            self.assertLess(max(gaps),.05*1.2)
            self.assertGreater(min(gaps),.05)
            # Check the physical curve at strand sampling resolution; duplicate
            # waypoint stations must not reverse the transported strand frame.
            physical=uniform_samples(points,math.ceil(cumulative(points)[-1]/(.05*.3)))
            for a,b,c in zip(physical,physical[1:],physical[2:]):
                if b.x>.8 and b.z>.8:
                    self.assertGreater((b-a).normalized().dot((c-b).normalized()),.75)

    def test_off_center_corner_has_no_sideways_detour(self):
        bpy.ops.mesh.primitive_cube_add(size=2)
        self.target=bpy.context.object
        self.settings.target=self.target
        self.settings.radius=.05
        r=None
        for y,dense in ((-.6,False),(.37,False),(.37,True)):
            anchors=[(.8,y,1),(.99,y,1),(1,y,.99),(1,y,.8)] if dense else [(.2,y,1),(1,y,.2)]
            if r is None:
                r=self.rope(*anchors)
            else:
                with ropes.quiet_updates():
                    r.ropes_rope.anchors.clear()
                    for point in anchors:
                        r.ropes_rope.anchors.add().position=point
                ropes.rebuild(bpy.context.scene,self.target)
            self.assertLess(max(abs(p.y-y) for p in ropes.rest_path(r)),1e-5)
            for doubled in (False,True):
                r.ropes_rope.doubled=doubled
                points=ropes.visible_path(r)
                limit=.05*1.04 if doubled else 1e-5
                self.assertLess(max(abs(p.y-y) for p in points),limit)
                self.assertLess(abs(sum(p.y-y for p in points)/len(points)),1e-4)

    def test_diagonal_corner_route_matches_unfolded_faces(self):
        bpy.ops.mesh.primitive_cube_add(size=2)
        surface=Surface(bpy.context.object,2)
        start,end=Vector((.2,-.4,1)),Vector((1,.3,.4))
        path=surface.route(start,end,1)
        expected=math.hypot(.8+.6,.7)
        self.assertAlmostEqual(cumulative(path)[-1],expected,places=3)
        for p in path:
            developed=(p.x-.2) if abs(p.z-1)<1e-5 else (.8+1-p.z)
            self.assertAlmostEqual(p.y,-.4+.7*developed/1.4,places=5)
        # An anchor exactly on the fold must not introduce zero-length samples
        # that could reverse a doubled rope's transported frame.
        for a,b in ((Vector((1,-.2,1)),Vector((.3,-.2,1))),
                    (Vector((.3,-.2,1)),Vector((1,-.2,1)))):
            folded=surface.route(a,b,1)
            self.assertLess((folded[0]-a).length,1e-6)
            self.assertLess((folded[-1]-b).length,1e-6)
            self.assertGreater(min((q-p).length for p,q in zip(folded,folded[1:])),1e-7)


    def test_clicked_junction_owner_persists_repath_and_state_restore(self):
        a=self.rope((-1.5,0,0),(1.5,0,0))
        b=self.rope((0,-1.5,0),(0,1.5,0))
        j=self.settings.junctions[0]
        # Click the default under rope: selection, not crossing order, owns it.
        ropes.knot_at(bpy.context.scene,b,j.distance_b)
        self.assertTrue(j.over_a)
        self.assertFalse(ropes.junction_active_a(j))
        snapshot=ropes.capture_state(bpy.context.scene,self.target,b)
        ropes.rebuild(bpy.context.scene,self.target)
        self.assertFalse(ropes.junction_active_a(self.settings.junctions[0]))
        self.settings.junctions[0].knot_a=True
        ropes.restore_state(bpy.context.scene,self.target,snapshot)
        self.assertFalse(ropes.junction_active_a(self.settings.junctions[0]))
        self.assertTrue(self.settings.junctions[0].knot_owner_set)

    def test_junction_active_knot_encircles_passive_axis(self):
        from ropes.geometry import junction_points,point_segment_distance
        for kind,expected in (('OVERHAND',3),('FIGURE_EIGHT',5)):
            for bundle in (1,2.01):
                radius=.05*bundle
                active=junction_points(Vector(),Vector((0,1,0)),Vector((1,0,0)),Vector((0,0,1)),radius,radius,0,kind)
                passive=junction_points(Vector(),Vector((0,1,0)),Vector((1,0,0)),Vector((0,0,1)),radius,radius,1,kind)
                self.assertEqual(knot_determinant(active),expected,(kind,bundle))
                self.assertEqual(knot_determinant(passive),1)
                # The active loop actually winds around the passive axis. Its
                # eye is not just placed next to a straight rope.
                center=(passive[0]+passive[-1])/2
                angles=[math.atan2(p.z-center.z,p.x-center.x) for p in active]
                winding=sum(math.atan2(math.sin(b-a),math.cos(b-a)) for a,b in zip(angles,angles[1:]))
                self.assertGreater(abs(winding),math.pi*2)
                self.assertGreater(min(point_segment_distance(p,passive[0],passive[-1]) for p in active),radius*2)

    def test_shared_knot_core_survives_collision_resolution(self):
        from ropes.geometry import point_segment_distance
        a=self.rope((-1.5,0,0),(1.5,0,0))
        b=self.rope((0,-1.5,0),(0,1.5,0))
        for doubled in (False,True):
            with ropes.quiet_updates():
                a.ropes_rope.doubled=b.ropes_rope.doubled=doubled
            ropes.rebuild(bpy.context.scene,self.target)
            self.settings.junctions[0].is_knot=True
            surface=Surface(self.target,1)
            displays={r.name:ropes.display_path(bpy.context.scene,r,surface,ropes.rest_path(r)) for r in (a,b)}
            before={name:[p.copy() for p in data[0]] for name,data in displays.items()}
            ropes.separate_knot_leads(bpy.context.scene,self.target,surface,displays)
            cores={}
            for r in (a,b):
                station=ropes.knot_records(bpy.context.scene,r)[0]['station']
                points,stations=displays[r.name]
                indices=[i for i,s in enumerate(stations) if abs(s-station)<1e-6]
                self.assertGreaterEqual(len(indices),31)
                for i in indices:
                    self.assertEqual(tuple(points[i]),tuple(before[r.name][i]))
                cores[r.name]=[(points[i],points[i+1]) for i in indices if i+1 in indices]
            for p,q in cores[a.name]:
                self.assertGreaterEqual(min(point_segment_distance(p,x,y) for x,y in cores[b.name]),a.ropes_rope.radius*1.95)

    def test_disconnected_surface_rejected(self):
        bm = bmesh.new()
        for offset in (0, 5):
            verts = [bm.verts.new((offset+x, y, 0)) for x, y in [(0, 0), (1, 0), (0, 1)]]
            bm.faces.new(verts)
        mesh = bpy.data.meshes.new('Islands')
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new('Islands', mesh)
        bpy.context.scene.collection.objects.link(obj)
        with self.assertRaisesRegex(ValueError, 'disconnected'):
            Surface(obj, 0).route((.1, .1, 0), (5.1, .1, 0))

    def test_curved_surface_stays_outside_sphere(self):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=2)
        sphere = bpy.context.object
        surface = Surface(sphere, 1)
        path = surface.route((2, 0, 0), (0, 0, 2))
        self.assertGreater(len(path), 5)
        self.assertTrue(all(v.length > 1.96 for v in path), min(v.length for v in path))
        self.assertTrue(all(surface.project(v)[0].__sub__(v).length < 1e-4 for v in path))

    def test_transformed_surface_and_save_reload(self):
        self.target.location = (3, 2, 1)
        self.target.rotation_euler.z = .4
        bpy.context.view_layer.update()
        r = self.rope((-1, 0, 0), (1, 0, 0))
        expected = self.target.matrix_world @ Vector((-1, 0, 0))
        self.assertLess((ropes.rest_path(r)[0]-expected).length, 1e-4)
        self.assertAlmostEqual(ropes.visible_path(r)[0].z, 1+self.settings.radius*1.05, places=4)
        r.ropes_rope.radius = .063
        r.ropes_rope.smoothing = .75
        r.ropes_rope.squish = .3
        r.ropes_rope.doubled = True
        ropes.knot_at(bpy.context.scene, r, .8)
        r.ropes_rope.knots[0].kind = 'FIGURE_EIGHT'
        self.settings.show_waypoints = True
        uid = r.ropes_rope.uid
        self.settings.waypoint_mode = True
        draft = ropes.new_rope(bpy.context.scene, self.target)
        with ropes.quiet_updates():
            for point, kind in [((-1, 1, 0), 'NORMAL'), ((0, 1, 0), 'SPANNING')]:
                anchor = draft.ropes_rope.anchors.add()
                anchor.position, anchor.kind = point, kind
        ropes.rebuild(bpy.context.scene, self.target)
        draft_uid = draft.ropes_rope.uid
        output = '/tmp/ropes-integration.blend'
        bpy.ops.wm.save_as_mainfile(filepath=output)
        bpy.ops.wm.open_mainfile(filepath=output)
        r = next(o for o in bpy.context.scene.objects if o.ropes_rope.uid == uid)
        draft = next(o for o in bpy.context.scene.objects if o.ropes_rope.uid == draft_uid)
        self.assertFalse(draft.ropes_rope.generated)
        self.assertEqual([a.kind for a in draft.ropes_rope.anchors], ['NORMAL', 'SPANNING'])
        self.assertFalse(draft.data.splines)
        self.assertTrue(bpy.context.scene.ropes_settings.waypoint_mode)
        self.assertEqual(len(r.ropes_rope.anchors), 2)
        self.assertAlmostEqual(r.ropes_rope.radius, .063)
        self.assertAlmostEqual(r.ropes_rope.smoothing, .75)
        self.assertAlmostEqual(r.ropes_rope.squish, .3)
        self.assertTrue(r.ropes_rope.doubled)
        self.assertEqual(r.ropes_rope.knots[0].kind, 'FIGURE_EIGHT')
        self.assertTrue(bpy.context.scene.ropes_settings.show_waypoints)
        ropes.rebuild(bpy.context.scene, r.ropes_rope.target)
        self.assertLess((ropes.rest_path(r)[0]-expected).length, 1e-4)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(RopesIntegration)
result = unittest.TextTestRunner(verbosity=2).run(suite)
ropes.unregister()
if not result.wasSuccessful():
    raise RuntimeError('Blender integration tests failed')
print(f'ROPES_TESTS_PASSED={result.testsRun}')
