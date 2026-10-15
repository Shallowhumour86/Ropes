"""Render the selectable knot styles and doubled rope using the actual add-on."""
from pathlib import Path
import sys
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ropes

ropes.register()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
bpy.ops.mesh.primitive_grid_add(x_subdivisions=91, y_subdivisions=91, size=6)
target = bpy.context.object
target.name = 'Knot Samples Surface'
mat = bpy.data.materials.new('Gallery Surface')
mat.diffuse_color = (.18, .32, .34, 1)
mat.use_nodes = True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.18, .32, .34, 1)
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .85
target.data.materials.append(mat)
settings = scene.ropes_settings
settings.target = target
settings.radius = .075
settings.subdivisions = 0
settings.squish = .65
settings.tension = .7
settings.falloff = 2
for row, label, kind, doubled in [
    (1.5, 'Compact overhand', 'OVERHAND', False),
    (.5, 'Figure eight', 'FIGURE_EIGHT', False),
    (-.5, 'Legacy trefoil', 'TREFOIL', False),
    (-1.5, 'Doubled + overhand', 'OVERHAND', True),
]:
    with ropes.quiet_updates():
        rope = ropes.new_rope(scene, target)
        rope.name = label
        rope.ropes_rope.knot_type = kind
        rope.ropes_rope.doubled = doubled
        for point in ((-1.8, row, 0), (0, row, 0), (1.8, row, 0)):
            rope.ropes_rope.anchors.add().position = point
        rope.ropes_rope.knots.add().distance = 1.8
    bpy.ops.object.text_add(location=(-2.7, row+.35, .015))
    text = bpy.context.object
    text.data.body = label
    text.data.size = .19
ropes.rebuild(scene, target)
bpy.ops.object.camera_add(location=(0, -6, 7))
camera = bpy.context.object
camera.rotation_euler = (Vector((0, 0, 0))-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 6.3
scene.camera = camera
for position, power in [((-3, -4, 6), 1200), ((3, 2, 5), 950)]:
    bpy.ops.object.light_add(type='AREA', location=position)
    light = bpy.context.object
    light.data.energy = power
    light.data.size = 4
    light.rotation_euler = (-light.location).to_track_quat('-Z', 'Y').to_euler()
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.06, .08, .1, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .4
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 32
scene.render.threads_mode = 'FIXED'
scene.render.threads = 4
scene.render.resolution_x = 1200
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(ROOT / 'dist' / 'surface-ropes-0.4.0-knots.png')
bpy.ops.render.render(write_still=True)
print('KNOT_GALLERY_RENDERED')
