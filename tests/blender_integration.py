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
        self.settings.radius = 0.035
        self.settings.subdivisions = 1
        self.settings.squish = 0
        self.settings.tension = 0.5
        self.settings.smoothing = 1
        self.settings.waypoint_xray = False
        self.settings.waypoint_size = 0.6
        self.settings.show_waypoints = False
        self.settings.waypoint_mode = False
        self.settings.placement_kind = 'NORMAL'
        self.settings.knot_type = 'OVERHAND'
        self.settings.knot_size = 1
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

    def test_crossing_clearance_uses_actual_run_radii(self):
        a = self.rope((-1.5, 0, 0), (1.5, 0, 0))
        b = self.rope((0, -1.5, 0), (0, 1.5, 0))
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                with ropes.quiet_updates():
                    a.ropes_rope.radius = 0.025
                    b.ropes_rope.radius = 0.06
                    a.ropes_rope.tension = 1
                    b.ropes_rope.tension = 0
                    self.settings.junctions[0].over_a = not reverse
                ropes.rebuild(bpy.context.scene, self.target)
                pa, pb = (ropes.visible_path(a), ropes.visible_path(b))
                gap = min(((x - y).length for u, v in zip(pa, pa[1:]) for c, d in zip(pb, pb[1:]) for x, y, _, _ in [closest_segments(u, v, c, d)]))
                self.assertLessEqual(gap, 0.0851)
                self.assertGreater(gap, 0.085 * 0.6)
                j = self.settings.junctions[0]
                fibres = [ropes.crossing_strand_segments(r, ropes.visible_path(r), json.loads(r['ropes_stations']), station, 0.7) for r, station in ((a, j.distance_a), (b, j.distance_b))]
                self.assertAlmostEqual(ropes.strand_segment_gap(*fibres), 0.085 * 0.46, delta=5e-05)
                passive = a if reverse else b
                height = ropes.curve_height(passive)
                self.assertLess(max((abs(p.z - height) for p in ropes.visible_path(passive))), 1e-05)

    def test_self_crossing_clearance_after_swap(self):
        r = self.rope((-1.3, -1.3, 0), (1.3, 1.3, 0), (-1.3, 1.3, 0), (1.3, -1.3, 0))
        for over in (False, True):
            with ropes.quiet_updates():
                self.settings.junctions[0].over_a = over
            ropes.rebuild(bpy.context.scene, self.target)
            joint = self.settings.junctions[0]
            points = ropes.visible_path(r)
            stations = json.loads(r['ropes_stations'])
            aa = [i for i in range(len(points) - 1) if abs(stations[i] - joint.distance_a) < 0.3]
            bb = [i for i in range(len(points) - 1) if abs(stations[i] - joint.distance_b) < 0.3]
            gap = min(((x - y).length for i in aa for j in bb for x, y, _, _ in [closest_segments(points[i], points[i + 1], points[j], points[j + 1])]))
            self.assertLessEqual(gap, 2 * r.ropes_rope.radius + 0.0001)
            self.assertGreater(gap, 1.2 * r.ropes_rope.radius)
            parts = [ropes.crossing_strand_segments(r, points, stations, s, 0.4) for s in (joint.distance_a, joint.distance_b)]
            self.assertAlmostEqual(ropes.strand_segment_gap(*parts), 0.92 * r.ropes_rope.radius, delta=5e-05)

    def test_crossing_apex_is_centered_on_passive_curve(self):
        a = self.rope((-1.5, 0, 0), (1.5, 0, 0))
        b = self.rope((0, -1.5, 0), (0, 1.5, 0))
        ropes.rebuild(bpy.context.scene, self.target)
        joint = self.settings.junctions[0]
        self.assertLess(Vector(joint.position).xy.length, 1e-05)
        self.assertAlmostEqual(joint.distance_a, 1.5, places=5)
        points = ropes.visible_path(a)
        peak = max(points, key=lambda p: p.z)
        step = max(((q - p).length for p, q in zip(ropes.rest_path(a), ropes.rest_path(a)[1:])))
        summit = [p.x for p in points if peak.z - p.z < 1e-06]
        self.assertLess(abs(sum(summit) / len(summit)), step)
        bottom = max((p.z for p in ropes.visible_path(b)))
        self.assertLessEqual(peak.z - bottom, 2 * a.ropes_rope.radius + 0.001)
        self.assertGreater(peak.z - bottom, 1.2 * a.ropes_rope.radius)


    def test_crossing_rendered_strands_touch_at_different_twists(self):
        from mathutils.bvhtree import BVHTree
        a = self.rope((-1.5, 0, 0), (1.5, 0, 0))
        b = self.rope((0, -1.5, 0), (0, 1.5, 0))
        for pitch in (7, 17):
            with self.subTest(pitch=pitch):
                with ropes.quiet_updates():
                    a.ropes_rope.strand_pitch = pitch
                ropes.rebuild(bpy.context.scene, self.target)
                vertices = []
                faces = []
                for obj in bpy.context.scene.objects:
                    if obj.get('ropes_owner') != b.ropes_rope.uid or obj.type != 'MESH':
                        continue
                    offset = len(vertices)
                    vertices.extend((obj.matrix_world @ v.co for v in obj.data.vertices))
                    faces.extend(([offset + i for i in f.vertices] for f in obj.data.polygons))
                tree = BVHTree.FromPolygons(vertices, faces)
                gap = float('inf')
                for obj in bpy.context.scene.objects:
                    if obj.get('ropes_owner') != a.ropes_rope.uid or obj.type != 'MESH':
                        continue
                    for vertex in obj.data.vertices:
                        p = obj.matrix_world @ vertex.co
                        if abs(p.x) < 0.2 and abs(p.y) < 0.2:
                            gap = min(gap, tree.find_nearest(p)[3])
                self.assertLess(gap, (a.ropes_rope.radius + b.ropes_rope.radius) * 0.05)

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
        self.assertAlmostEqual(min(p.z for p in ropes.visible_path(r)), self.settings.radius*(1-self.settings.tension), delta=.002)
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
        self.assertLess(near_a.co.z, -.01)
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
        self.assertGreater(pa.z-pb.z, (a.ropes_rope.radius+b.ropes_rope.radius)*.6)

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
        self.assertTrue(all(p.z >= ropes.curve_height(r)-1e-6 for p in ropes.visible_path(r)))

    def test_smoothed_curved_rope_clearance(self):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=2)
        self.target = bpy.context.object
        self.settings.target = self.target
        r = self.rope((2, 0, 0), (0, 0, 2))
        surface = Surface(self.target, 0)
        for a, b in zip(ropes.visible_path(r), ropes.visible_path(r)[1:]):
            for p in (a, a.lerp(b, .5)):
                nearest, normal, _ = surface.project(p)
                self.assertGreater((p-nearest).dot(normal),0)
                self.assertLess((p-nearest).length,ropes.curve_height(r)*1.01)

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
        self.assertGreater(max(field.value(p) for p in off_center), .025)
        changes = [old-p.co.z for old, p, v in zip(before, key.data, self.target.data.vertices)
                   if abs(v.co.y) > .12]
        self.assertGreater(max(changes), .015)
        ropes.knot_at(bpy.context.scene, r, 1.5)
        self.assertLess(max(abs(old-p.co.z) for old,p in zip(before,key.data)), 1e-5)



    def test_waypoint_move_keeps_knot_at_anchor_and_crossing_choice(self):
        r = self.rope((-1, 0, 0), (0, 0.5, 0), (1, 0, 0))
        old_bounds = json.loads(r['ropes_leg_bounds'])
        ropes.knot_at(bpy.context.scene, r, old_bounds[1])
        r.ropes_rope.knots[0].kind = 'OVERHAND'
        state = ropes.capture_state(bpy.context.scene, self.target, r)
        ropes.move_waypoint(bpy.context.scene, r, 1, (0, -0.8, 0))
        new_bounds = json.loads(r['ropes_leg_bounds'])
        self.assertAlmostEqual(r.ropes_rope.knots[0].distance, new_bounds[1], places=5)
        self.assertEqual(r.ropes_rope.knots[0].kind, 'OVERHAND')
        ropes.restore_state(bpy.context.scene, self.target, state)
        self.assertAlmostEqual(r.ropes_rope.knots[0].distance, old_bounds[1], places=5)
        b = self.rope((0, -1.8, 0), (0, 1.8, 0))
        self.settings.junctions[0].over_a = False
        self.settings.junctions[0].is_knot = True
        self.settings.junctions[0].kind = 'OVERHAND'
        ropes.move_waypoint(bpy.context.scene, r, 1, (0, -1.2, 0))
        j = self.settings.junctions[0]
        self.assertFalse(j.over_a)
        self.assertTrue(j.is_knot)
        self.assertEqual(j.kind, 'OVERHAND')

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
        bm = bmesh.new()
        for x in (-1.5, 1.5):
            verts = [bm.verts.new((x + dx, y, 0)) for dx, y in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))]
            bm.faces.new(verts)
        mesh = bpy.data.meshes.new('Gap mesh')
        bm.to_mesh(mesh)
        bm.free()
        self.target = bpy.data.objects.new('Gap surface', mesh)
        bpy.context.scene.collection.objects.link(self.target)
        self.settings.target = self.target
        self.settings.waypoint_mode = True
        r = ropes.new_rope(bpy.context.scene, self.target)
        with ropes.quiet_updates():
            for p in ((-1, 0, 0), (1, 0, 0)):
                a = r.ropes_rope.anchors.add()
                a.position = p
                a.kind = 'SPANNING'
            r.ropes_rope.squish = 1
            r.ropes_rope.tension = 1
        self.assertEqual(bpy.ops.ropes.generate(), {'FINISHED'})
        points = ropes.visible_path(r)
        self.assertAlmostEqual(cumulative(points)[-1], 2, places=4)
        self.assertTrue(all((abs(p.y) < 1e-05 for p in points)))
        self.assertFalse(ropes.PressureField(bpy.context.scene, self.target).contacts)
        self.assertIsNone(self.target.data.shape_keys)
        self.assertFalse(self.settings.message, self.settings.message)
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
        self.assertGreater(field.value(Vector((-1,0,0))),.015)
        self.assertLess(field.value(Vector((0,0,0))),1e-8)
        self.assertGreater(field.value(Vector((1,0,0))),.015)
        # One spanning end alone has ordinary surface behavior.
        r.ropes_rope.anchors[2].kind='NORMAL'
        self.assertEqual(json.loads(r['ropes_span_flags']),[False,False,False])
        self.assertGreater(ropes.PressureField(bpy.context.scene,self.target).value(Vector((0,0,0))),.015)

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



    def test_span_contacts_and_mixed_transition_have_no_height_step(self):
        r = self.rope((-1.5, 0, 0), (-0.5, 0, 0), (0.5, 0, 0), (1.5, 0, 0))
        with ropes.quiet_updates():
            r.ropes_rope.anchors[1].kind = 'SPANNING'
            r.ropes_rope.anchors[2].kind = 'SPANNING'
        ropes.rebuild(bpy.context.scene, self.target)
        self.assertFalse(self.settings.message, self.settings.message)
        points = ropes.visible_path(r)
        self.assertAlmostEqual(points[-1].z, ropes.curve_height(r), places=5)
        self.assertLess(max((abs(b.z - a.z) for a, b in zip(points, points[1:]))), r.ropes_rope.radius * 0.2)
        r.ropes_rope.squish = 1
        r.ropes_rope.tension = 1
        points = ropes.visible_path(r)
        turns = [(b - a).normalized().dot((c - b).normalized()) for a, b, c in zip(points, points[1:], points[2:]) if min(a.x, b.x, c.x) > -0.8]
        self.assertTrue(all((t > 0.95 for t in turns)), min(turns))
        r.ropes_rope.squish = 0
        self.settings.show_waypoints = True
        bpy.context.view_layer.update()
        markers = [o for o in bpy.context.scene.objects if 'ropes_waypoint' in o]
        self.assertEqual(len(markers), 4)
        for marker in markers:
            anchor = r.ropes_rope.anchors[marker['ropes_waypoint']]
            self.assertLess((marker.matrix_world.translation - Vector(anchor.position)).length, 1e-06)


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




    def test_sharp_cube_corner_rounds_at_contact_height(self):
        bpy.ops.mesh.primitive_cube_add(size=2)
        self.target = bpy.context.object
        self.settings.target = self.target
        self.settings.radius = 0.05
        r = self.rope((-0.7, 0, 1), (1, 0, 0.7), (1, 0, -0.7))
        points = ropes.visible_path(r)
        radii = []
        for a, b, c in zip(points, points[1:], points[2:]):
            if b.x < 0.8 or b.z < 0.8:
                continue
            u, v = (b - a, c - b)
            cross = u.cross(v).length
            if cross > 1e-10:
                radii.append(u.length * v.length * (c - a).length / (2 * cross))
        self.assertTrue(radii)
        self.assertGreater(min(radii), ropes.curve_height(r) * 0.5)
        self.assertLess(max(((p - Surface(self.target, 1).project(p)[0]).length for p in points if p.x > 0.8 and p.z > 0.8)), r.ropes_rope.radius * 1.2)
        ropes.knot_at(bpy.context.scene, r, 0.25)
        points = ropes.visible_path(r)
        radii = []
        for a, b, c in zip(points, points[1:], points[2:]):
            if b.x < 0.8 or b.z < 0.8:
                continue
            u, v = (b - a, c - b)
            cross = u.cross(v).length
            if cross > 1e-10:
                radii.append(u.length * v.length * (c - a).length / (2 * cross))
        self.assertGreater(min(radii), ropes.curve_height(r) * 0.5)
        self.assertLess(max(((p - Surface(self.target, 1).project(p)[0]).length for p in points if p.x > 0.8 and p.z > 0.8)), r.ropes_rope.radius * 1.2)


    def test_curved_normal_runs_stay_on_contact_envelope(self):
        self.settings.tension = 0
        for shape in ('SPHERE', 'RIPPLED'):
            if shape == 'SPHERE':
                bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1)
                self.target = bpy.context.object
                anchors = [(1, 0, 0), (0, 0, 1)]
            else:
                bpy.ops.mesh.primitive_grid_add(x_subdivisions=151, y_subdivisions=15, size=4)
                self.target = bpy.context.object
                for v in self.target.data.vertices:
                    v.co.z = 0.11 * math.cos(14 * v.co.x) + 0.05 * v.co.y * v.co.y
                self.target.data.update()
                anchors = [(x, 0, 0.11 * math.cos(14 * x)) for x in (-1.5, 1.5)]
            self.settings.target = self.target
            self.settings.radius = 0.05
            self.settings.subdivisions = 0
            surface = Surface(self.target, 0)
            self.assertFalse(surface.sharp_edges)
            r = self.rope(*(surface.project(Vector(p))[0] for p in anchors))
            with self.subTest(shape=shape):
                points = ropes.visible_path(r)
                if shape == 'RIPPLED':
                    points = [p for p in points if abs(p.x) < 1.2]
                gaps = [(p - surface.project(p)[0]).length / r.ropes_rope.radius for p in points]
                self.assertGreaterEqual(min(gaps), 0.97)
                self.assertLessEqual(max(gaps), 1.2)
                self.assertFalse(self.settings.message, self.settings.message)
            if shape == 'RIPPLED':
                r.ropes_rope.squish = 0.6
                r.ropes_rope.tension = 0.7
                bpy.context.view_layer.update()
                deformed = Surface(self.target.evaluated_get(bpy.context.evaluated_depsgraph_get()), 0)
                gaps = [(p - deformed.project(p)[0]).length / r.ropes_rope.radius for p in ropes.visible_path(r) if abs(p.x) < 1.2]
                self.assertLessEqual(max(gaps), 1.2)

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
        r = self.rope((-1, 0, 0), (0, 0, 0), (0, 1, 0))
        points = ropes.visible_path(r)
        self.assertTrue(all((abs(p.z - ropes.curve_height(r)) < 1e-05 for p in points)))
        radii = []
        for a, b, c in zip(points, points[1:], points[2:]):
            if abs(b.x) > 0.4 or abs(b.y) > 0.4:
                continue
            u, v = (b - a, c - b)
            cross = u.cross(v).length
            if cross > 1e-10:
                radii.append(u.length * v.length * (c - a).length / (2 * cross))
        self.assertTrue(radii)
        self.assertGreater(min(radii), r.ropes_rope.radius * 1.2)

    def test_dense_corner_waypoints_have_contact_and_stable_frames(self):
        from ropes.geometry import uniform_samples
        bpy.ops.mesh.primitive_cube_add(size=2)
        self.target = bpy.context.object
        self.settings.target = self.target
        self.settings.radius = 0.05
        r = self.rope((-0.7, 0, 1), (0.8, 0, 1), (0.95, 0, 1), (1, 0, 1), (1, 0, 0.95), (1, 0, 0.8), (1, 0, -0.7))
        surface = Surface(self.target, 1)
        points = ropes.visible_path(r)
        gaps = [(p - surface.project(p)[0]).length for p in points]
        self.assertLess(max(gaps), 0.05 * 1.2)
        self.assertGreater(min(gaps), ropes.curve_height(r) * 0.8)
        physical = uniform_samples(points, math.ceil(cumulative(points)[-1] / (0.05 * 0.3)))
        for a, b, c in zip(physical, physical[1:], physical[2:]):
            if b.x > 0.8 and b.z > 0.8:
                self.assertGreater((b - a).normalized().dot((c - b).normalized()), 0.5)

    def test_off_center_corner_has_no_sideways_detour(self):
        bpy.ops.mesh.primitive_cube_add(size=2)
        self.target = bpy.context.object
        self.settings.target = self.target
        self.settings.radius = 0.05
        r = None
        for y, dense in ((-0.6, False), (0.37, False), (0.37, True)):
            anchors = [(0.8, y, 1), (0.99, y, 1), (1, y, 0.99), (1, y, 0.8)] if dense else [(0.2, y, 1), (1, y, 0.2)]
            if r is None:
                r = self.rope(*anchors)
            else:
                with ropes.quiet_updates():
                    r.ropes_rope.anchors.clear()
                    for point in anchors:
                        r.ropes_rope.anchors.add().position = point
                ropes.rebuild(bpy.context.scene, self.target)
            self.assertLess(max((abs(p.y - y) for p in ropes.rest_path(r))), 1e-05)
            points = ropes.visible_path(r)
            limit = 1e-05
            self.assertLess(max((abs(p.y - y) for p in points)), limit)
            self.assertLess(abs(sum((p.y - y for p in points)) / len(points)), 0.0001)

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


    def test_tightness_sets_centerline_height_and_squish_deforms_only_mesh(self):
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=40, y_subdivisions=40, size=4)
        self.target = bpy.context.object
        self.settings.target = self.target
        self.settings.radius = 0.04
        a = self.rope((-1, 0, 0), (1, 0, 0))
        b = self.rope((-1, 1, 0), (1, 1, 0))
        before_b = [tuple(p) for p in ropes.visible_path(b)]
        for tightness, height in ((0, 0.04), (0.5, 0.02), (1, 0)):
            a.ropes_rope.tension = tightness
            self.assertTrue(all((abs(p.z - height) < 1e-06 for p in ropes.visible_path(a))))
        self.assertEqual(before_b, [tuple(p) for p in ropes.visible_path(b)])
        a.ropes_rope.tension = 1
        curve = [tuple(p) for p in ropes.visible_path(a)]
        a.ropes_rope.squish = 0.8
        self.assertEqual(curve, [tuple(p) for p in ropes.visible_path(a)])
        key = self.target.data.shape_keys.key_blocks[self.target['ropes_compression_key']]
        self.assertAlmostEqual(min((p.co.z for p in key.data)), -0.04 * 0.8, places=5)
        a.ropes_rope.tension = 0
        self.assertEqual(key.value, 0)

    def test_centerline_routes_through_pinched_valley_without_side_loops(self):
        xs = [-1.5 + i * 0.1 for i in range(31)]
        ys = [-0.3, -0.025, 0, 0.025, 0.3]
        vertices = [(x, y, (0.15 + 0.12 * math.cos(6 * x)) * min(1, abs(y) / 0.025)) for x in xs for y in ys]
        mesh = bpy.data.meshes.new('Pinched centerline valley')
        mesh.from_pydata(vertices, [], [(i * 5 + j, (i + 1) * 5 + j, (i + 1) * 5 + j + 1, i * 5 + j + 1) for i in range(30) for j in range(4)])
        self.target = bpy.data.objects.new('Pinched centerline valley', mesh)
        bpy.context.scene.collection.objects.link(self.target)
        self.settings.target = self.target
        self.settings.subdivisions = 0
        self.settings.radius = 0.05
        a = self.rope((-1.4, 0, 0), (0, 0, 0), (1.4, 0, 0))
        for tightness in (0, 0.5, 1):
            a.ropes_rope.tension = tightness
            points = ropes.visible_path(a)
            self.assertFalse(self.settings.message, self.settings.message)
            centers = points
            self.assertLess(max((abs(p.y) for p in centers)), 0.005)
            self.assertLess(cumulative(centers)[-1], 2.85)
            self.assertLess(max((p.z for p in centers)), a.ropes_rope.radius * 1.01)
            if tightness == 1:
                self.assertLess(max((abs(p.z) for p in centers)), 1e-06)



    def test_spanning_junction_is_not_lowered_toward_target(self):
        a=self.rope((-1.5,0,0),(1.5,0,0))
        b=self.rope((0,-1.5,0),(0,1.5,0))
        with ropes.quiet_updates():
            for owner in (a,b):
                for anchor in owner.ropes_rope.anchors:
                    anchor.kind='SPANNING'
        ropes.rebuild(bpy.context.scene,self.target)
        with patch.object(ropes._geometry,'junction_support_offset',side_effect=AssertionError('Free spans must not be grounded')):
            ropes.knot_at(bpy.context.scene,a,self.settings.junctions[0].distance_a)
        self.assertTrue(self.settings.junctions[0].is_knot)



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
        self.target.rotation_euler.z = 0.4
        bpy.context.view_layer.update()
        r = self.rope((-1, 0, 0), (1, 0, 0))
        expected = self.target.matrix_world @ Vector((-1, 0, 0))
        self.assertLess((ropes.rest_path(r)[0] - expected).length, 0.0001)
        self.assertAlmostEqual(ropes.visible_path(r)[0].z, 1 + self.settings.radius * (1 - self.settings.tension), places=4)
        r.ropes_rope.radius = 0.063
        r.ropes_rope.smoothing = 0.75
        r.ropes_rope.squish = 0.3
        ropes.knot_at(bpy.context.scene, r, 0.8)
        r.ropes_rope.knots[0].kind = 'OVERHAND'
        self.settings.show_waypoints = True
        uid = r.ropes_rope.uid
        self.settings.waypoint_mode = True
        draft = ropes.new_rope(bpy.context.scene, self.target)
        with ropes.quiet_updates():
            for point, kind in [((-1, 1, 0), 'NORMAL'), ((0, 1, 0), 'SPANNING')]:
                anchor = draft.ropes_rope.anchors.add()
                anchor.position, anchor.kind = (point, kind)
        ropes.rebuild(bpy.context.scene, self.target)
        draft_uid = draft.ropes_rope.uid
        output = '/tmp/ropes-integration.blend'
        bpy.ops.wm.save_as_mainfile(filepath=output)
        bpy.ops.wm.open_mainfile(filepath=output)
        r = next((o for o in bpy.context.scene.objects if o.ropes_rope.uid == uid))
        draft = next((o for o in bpy.context.scene.objects if o.ropes_rope.uid == draft_uid))
        self.assertFalse(draft.ropes_rope.generated)
        self.assertEqual([a.kind for a in draft.ropes_rope.anchors], ['NORMAL', 'SPANNING'])
        self.assertFalse(draft.data.splines)
        self.assertTrue(bpy.context.scene.ropes_settings.waypoint_mode)
        self.assertEqual(len(r.ropes_rope.anchors), 2)
        self.assertAlmostEqual(r.ropes_rope.radius, 0.063)
        self.assertAlmostEqual(r.ropes_rope.smoothing, 0.75)
        self.assertAlmostEqual(r.ropes_rope.squish, 0.3)
        self.assertEqual(r.ropes_rope.knots[0].kind, 'OVERHAND')
        self.assertTrue(bpy.context.scene.ropes_settings.show_waypoints)
        ropes.rebuild(bpy.context.scene, r.ropes_rope.target)
        self.assertLess((ropes.rest_path(r)[0] - expected).length, 0.0001)


    def test_shared_overhand_template_opens_eye_smoothly(self):
        from ropes.geometry import knot_points,align_knot_entries,overhand_eye,junction_points
        lead=Vector((1,0,0));up=Vector((0,0,1));axis=Vector((0,1,0));radius=.035
        line=align_knot_entries(knot_points(Vector(),lead,up,radius,count=720),lead,count=72)
        self.assertEqual(knot_determinant(line),3)
        eye=overhand_eye(line,lead,up)
        for passive_radius in (.02,.035,.08):
            tying,passive=[junction_points(Vector(),axis,lead,up,radius,passive_radius,c) for c in (0,1)]
            self.assertEqual(len(tying),len(line))
            deltas=[]
            for original,opened in zip(line,tying):
                original=original-eye
                self.assertAlmostEqual(original.dot(axis),opened.dot(axis),places=6)
                before=original-axis*original.dot(axis);after=opened-axis*opened.dot(axis)
                self.assertLess(before.cross(after).length,1e-6)
                deltas.append(after.length_squared-before.length_squared)
            self.assertLess(max(deltas)-min(deltas),1e-7)
            self.assertAlmostEqual(min(ropes.point_segment_distance(p,passive[0],passive[-1]) for p in tying),
                                   radius+passive_radius-.15*min(radius,passive_radius),places=6)
            dots=[(q-p).normalized().dot((r-q).normalized()) for p,q,r in zip(tying,tying[1:],tying[2:])
                  if min((q-p).length,(r-q).length)>1e-8]
            self.assertGreater(min(dots),.9)
            self.assertTrue(all((p-passive[0]).cross(axis).length<1e-6 for p in passive))

    def test_three_overhand_placements_preserve_the_template(self):
        # Type 1 remains the accepted line knot.
        line=self.rope((-1.5,-.9,0),(1.5,-.9,0))
        ropes.knot_at(bpy.context.scene,line,1.5)
        station=line.ropes_rope.knots[0].distance
        core=[p for p,s in zip(ropes.visible_path(line),json.loads(line['ropes_stations'])) if abs(s-station)<1e-6]
        self.assertEqual(len(core),180)
        self.assertEqual(knot_determinant(core),3)
        # Type 3 uses that same template and leaves its support straight.
        self.setUp()
        a=self.rope((-1.5,.5,0),(1.5,.5,0))
        b=self.rope((0,-.1,0),(0,1.5,0))
        joint=next(j for j in self.settings.junctions if j.rope_a==a and j.rope_b==b)
        ropes.knot_at(bpy.context.scene,a,joint.distance_a)
        self.check_shared_junction(a,b,joint)
        # Type 2 takes exactly the same path through a self-crossing.
        self.setUp()
        r=self.rope((-1.3,-1.3,0),(1.3,1.3,0),(-1.3,1.3,0),(1.3,-1.3,0))
        joint=next(j for j in self.settings.junctions if j.rope_a==r and j.rope_b==r)
        ropes.knot_at(bpy.context.scene,r,joint.distance_a)
        self.check_shared_junction(r,r,joint)

    def check_shared_junction(self,active,passive,joint):
        active_a=ropes.junction_active_a(joint)
        ast=joint.distance_a if active_a else joint.distance_b
        pst=joint.distance_b if active_a else joint.distance_a
        pts=ropes.visible_path(active);ss=json.loads(active['ropes_stations'])
        indices=[i for i,s in enumerate(ss) if abs(s-ast)<1e-6]
        core=[pts[i] for i in indices]
        pp=[p for p,s in zip(ropes.visible_path(passive),json.loads(passive['ropes_stations'])) if abs(s-pst)<1e-6]
        self.assertEqual(len(core),720);self.assertEqual(len(pp),31)
        _,lead=ropes.sample_at(ropes.rest_path(active),cumulative(ropes.rest_path(active)),ast)
        _,axis=ropes.sample_at(ropes.rest_path(passive),cumulative(ropes.rest_path(passive)),pst)
        expected=ropes.junction_points(Vector(),axis,lead,Vector((0,0,1)),active.ropes_rope.radius,
                                      passive.ropes_rope.radius,0,size=active.ropes_rope.knot_size)
        translation=core[0]-expected[0]
        self.assertLess(max((actual-wanted-translation).length for actual,wanted in zip(core,expected)),1e-5)
        self.assertTrue(all((p-pp[0]).cross(axis).length<1e-6 for p in pp))
        self.assertAlmostEqual(min(ropes.point_segment_distance(p,pp[0],pp[-1]) for p in core),
                                   active.ropes_rope.radius+passive.ropes_rope.radius-.15*min(active.ropes_rope.radius,passive.ropes_rope.radius),places=6)
        # Both leads meet the core tangentially, without an elbow at the eye.
        for i,j,k in ((indices[0]-1,indices[0],indices[0]+1),(indices[-1]-1,indices[-1],indices[-1]+1)):
            self.assertGreater((pts[j]-pts[i]).normalized().dot((pts[k]-pts[j]).normalized()),.95)

    def test_expanded_eye_is_smooth_at_oblique_junctions(self):
        for angle in (30,60,90):
            axis=Vector((math.cos(math.radians(angle)),math.sin(math.radians(angle)),0))
            for passive_radius in (.02,.08):
                body,passive=[ropes.junction_points(Vector(),axis,Vector((1,0,0)),Vector((0,0,1)),.035,passive_radius,c)
                              for c in (0,1)]
                gap=min(ropes.point_segment_distance(p,passive[0],passive[-1]) for p in body)
                self.assertAlmostEqual(gap,.035+passive_radius-.15*min(.035,passive_radius),places=6)
                self.assertLess(gap,.035+passive_radius)
                turns=[(b-a).normalized().dot((c-b).normalized()) for a,b,c in zip(body,body[1:],body[2:])
                       if min((b-a).length,(c-b).length)>1e-8]
                self.assertGreater(min(turns),.95)

    def test_shared_knot_seats_on_curved_geometry_without_distortion(self):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,radius=2)
        self.target=bpy.context.object;self.settings.target=self.target
        height=math.sqrt(4-.6**2)
        a=self.rope((-.6,0,height),(.6,0,height))
        b=self.rope((0,-.6,height),(0,.6,height))
        with ropes.quiet_updates():b.ropes_rope.radius=.05
        ropes.rebuild(bpy.context.scene,self.target)
        joint=next(j for j in self.settings.junctions if j.rope_a==a and j.rope_b==b)
        ropes.knot_at(bpy.context.scene,a,joint.distance_a)
        surface=Surface(self.target,0)
        world=self.target.matrix_world@Vector(joint.position)
        normal=surface.project(world)[1]
        _,lead=ropes.sample_at(ropes.rest_path(a),cumulative(ropes.rest_path(a)),joint.distance_a)
        _,axis=ropes.sample_at(ropes.rest_path(b),cumulative(ropes.rest_path(b)),joint.distance_b)
        expected=ropes.junction_points(Vector(),axis,lead,normal,a.ropes_rope.radius,b.ropes_rope.radius,0)
        cores=[]
        for owner,station in ((a,joint.distance_a),(b,joint.distance_b)):
            core=[p for p,s in zip(ropes.visible_path(owner),json.loads(owner['ropes_stations'])) if abs(s-station)<1e-6]
            cores.append(core)
        shift=cores[0][0]-expected[0]
        self.assertLess(max((p-q-shift).length for p,q in zip(cores[0],expected)),1e-5)
        gaps=[(p-surface.project(p)[0]).length/owner.ropes_rope.radius for owner,core in zip((a,b),cores) for p in core]
        self.assertGreater(min(gaps),.99);self.assertLess(min(gaps),1.12)

    def test_centre_curve_view_is_exact_and_reversible(self):
        r=self.rope((-1.5,0,0),(1.5,0,0))
        ropes.knot_at(bpy.context.scene,r,1.5)
        before=[tuple(p) for p in ropes.visible_path(r)]
        helpers=[o for o in bpy.context.scene.objects if o.get('ropes_owner')==r.ropes_rope.uid]
        self.assertEqual(r.data.splines[0].type,'BEZIER')
        self.assertTrue(all(p.handle_left_type=='VECTOR' and p.handle_right_type=='VECTOR' for p in r.data.splines[0].bezier_points))
        self.settings.curve_view='CURVES'
        self.assertTrue(all(o.hide_get() and o.hide_render for o in helpers))
        self.assertGreater(r.data.bevel_depth,0)
        self.assertEqual(before,[tuple(p) for p in ropes.visible_path(r)])
        self.settings.curve_view='BOTH'
        self.assertTrue(all(not o.hide_get() and not o.hide_render for o in helpers))
        self.assertTrue(r.show_in_front)
        self.settings.curve_view='ROPE'
        self.assertEqual(r.data.bevel_depth,0)
        self.assertEqual(before,[tuple(p) for p in ropes.visible_path(r)])

    def test_retired_controls_migrate_to_single_overhand(self):
        r=self.rope((-1.5,0,0),(1.5,0,0))
        ropes.knot_at(bpy.context.scene,r,1.5)
        uid=r.ropes_rope.uid
        r.ropes_rope['doubled']=True;r.ropes_rope['double_spacing']=2
        r.ropes_rope['knot_type']=2;r.ropes_rope.knots[0]['kind']=2
        r['ropes_schema']=11
        ropes.migrate_on_load(None)
        self.assertFalse(hasattr(r.ropes_rope,'doubled'))
        self.assertNotIn('doubled',r.ropes_rope);self.assertNotIn('double_spacing',r.ropes_rope)
        self.assertEqual(r.ropes_rope.knot_type,'OVERHAND')
        self.assertEqual(r.ropes_rope.knots[0].kind,'OVERHAND')
        self.assertEqual(r.ropes_rope.uid,uid)
        self.assertAlmostEqual(r.ropes_rope.knots[0].distance,1.5)
        self.assertAlmostEqual((ropes.visible_path(r)[-1]-ropes.visible_path(r)[0]).length,3,places=5)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(RopesIntegration)
result = unittest.TextTestRunner(verbosity=2).run(suite)
ropes.unregister()
if not result.wasSuccessful():
    raise RuntimeError('Blender integration tests failed')
print(f'ROPES_TESTS_PASSED={result.testsRun}')
