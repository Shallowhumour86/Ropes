"""Generate an editable demonstration blend and a render using the actual add-on."""
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ropes
from ropes.geometry import cumulative

ropes.register()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=48, radius=2)
target = bpy.context.object
target.name = 'Soft Surface'
for polygon in target.data.polygons:
    polygon.use_smooth = True
mat = bpy.data.materials.new('Soft blue surface')
mat.diffuse_color = (.1, .27, .33, 1)
mat.use_nodes = True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.1, .27, .33, 1)
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .65
target.data.materials.append(mat)
settings = scene.ropes_settings
settings.target = target
settings.radius = .06
settings.subdivisions = 1


def add(points):
    r = ropes.new_rope(scene, target)
    for p in points:
        r.ropes_rope.anchors.add().position = p
    ropes.rebuild(scene, target)
    return r


horizontal = add([(-1.6, -1.2, 0), (1.6, -1.2, 0), (1.4, -1, 1)])
vertical = add([(0, -1.2, -1.6), (0, -1.2, 1.6)])
ropes.knot_at(scene, horizontal, 1.1)
for rope in (horizontal, vertical):
    rope.ropes_rope.squish = .65
    rope.ropes_rope.tension = .7
    rope.ropes_rope.falloff = 4
assert len(settings.junctions) == 1
bpy.ops.object.camera_add(location=(4.5, -10, 3.2))
camera = bpy.context.object
camera.rotation_euler = (Vector((0, 0, 0))-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 5.7
scene.camera = camera
for name, location, energy, size in [
    ('Key', (-3, -6, 6), 1100, 5),
    ('Fill', (5, -3, 2), 700, 4),
    ('Rim', (1, 3, 4), 1300, 3),
]:
    bpy.ops.object.light_add(type='AREA', location=location)
    light = bpy.context.object
    light.name = name
    light.data.energy = energy
    light.data.shape = 'DISK'
    light.data.size = size
    light.rotation_euler = (-light.location).to_track_quat('-Z', 'Y').to_euler()
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.025, .035, .045, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .35
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 32
scene.render.threads_mode = 'FIXED'
scene.render.threads = 4
scene.render.resolution_x = 1000
scene.render.resolution_y = 850
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
output = ROOT / 'dist'
output.mkdir(exist_ok=True)
scene.render.filepath = str(output / 'surface-ropes-0.2.0-preview.png')
bpy.ops.object.select_all(action='DESELECT')
target.select_set(True)
bpy.context.view_layer.objects.active = target
# A useful view when the sample is opened in desktop Blender.
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
        area.spaces.active.region_3d.view_distance = 7
        area.spaces.active.region_3d.view_location = (0, 0, 0)
        area.spaces.active.show_region_ui = True
bpy.ops.wm.save_as_mainfile(filepath=str(output / 'surface-ropes-0.2.0-demo.blend'))
bpy.ops.render.render(write_still=True)
print('DEMO_COMPLETE', output)
