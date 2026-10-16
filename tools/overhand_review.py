"""Build and render the three supported cases, including their exact centre curves."""
from pathlib import Path
import sys
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import ropes
ropes.register()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
bpy.ops.mesh.primitive_grid_add(x_subdivisions=31,y_subdivisions=31,size=12)
target=bpy.context.object;target.name='Overhand review surface'
s=scene.ropes_settings;s.target=target;s.radius=.06;s.squish=0;s.subdivisions=0;s.tension=0
owners=[]
def rope(name,anchors):
    r=ropes.new_rope(scene,target);r.name=name
    for p in anchors:r.ropes_rope.anchors.add().position=p
    owners.append(r);return r
line=rope('1 · Knot on a line',[(-4.9,0,0),(-2.1,0,0)])
self_rope=rope('2 · Self-crossing',[(-1.3,0,0),(1.3,0,0),(1.3,1.3,0),(0,1.3,0),(0,-1.3,0)])
a=rope('3 · Tying rope',[(2.1,0,0),(4.9,0,0)])
b=rope('3 · Passive rope',[(3.5,-1.3,0),(3.5,1.3,0)])
ropes.rebuild(scene,target)
ropes.knot_at(scene,line,1.4)
self_joint=next(j for j in s.junctions if j.rope_a==self_rope and j.rope_b==self_rope)
ropes.knot_at(scene,self_rope,self_joint.distance_a)
joint=next(j for j in s.junctions if {j.rope_a,j.rope_b}=={a,b})
ropes.knot_at(scene,a,joint.distance_a if joint.rope_a==a else joint.distance_b)
# Colour the passive support separately in the two-rope case.
for obj in scene.objects:
    if obj.get('ropes_owner')==b.ropes_rope.uid:
        mat=obj.data.materials[0].copy()
        for node in mat.node_tree.nodes:
            if node.type=='VALTORGB':
                for element in node.color_ramp.elements:
                    strength=sum(element.color[:3])/3
                    element.color=(strength*.65,strength*.18,strength*.15,1)
        obj.data.materials[0]=mat
bpy.ops.object.camera_add(location=(0,-13,6))
camera=bpy.context.object;camera.rotation_euler=(Vector((0,0,.15))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=11.2;scene.camera=camera
for x,label in [(-4.8,'1 · On a line'),(-1.2,'2 · Self-crossing'),(2.2,'3 · Two ropes')]:
    bpy.ops.object.text_add(location=(x,-1.8,.25));text=bpy.context.object
    text.rotation_euler=camera.rotation_euler;text.data.body=label;text.data.size=.2
    text.data.materials.append(ropes.centre_material())
for position,power in [((-4,-5,8),1500),((4,3,6),1000)]:
    bpy.ops.object.light_add(type='AREA',location=position);light=bpy.context.object
    light.data.energy=power;light.data.size=6
    light.rotation_euler=(-light.location).to_track_quat('-Z','Y').to_euler()
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.8,.8,.8,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
scene.render.engine='CYCLES';scene.cycles.samples=32
scene.render.threads_mode='FIXED';scene.render.threads=4
scene.render.resolution_x=1800;scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
out=ROOT/'dist';out.mkdir(exist_ok=True)
for mode,suffix in [('ROPE','overhands'),('CURVES','curves')]:
    s.curve_view=mode;target.hide_render=mode=='CURVES'
    scene.render.filepath=str(out/f'surface-ropes-0.12.0-{suffix}.png')
    bpy.ops.render.render(write_still=True)
target.hide_render=False;target.display_type='WIRE'
s.active_rope=a
bpy.ops.object.select_all(action='DESELECT');a.select_set(True);bpy.context.view_layer.objects.active=a
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.region_3d.view_rotation=camera.rotation_euler.to_quaternion()
            space.region_3d.view_distance=9
            space.region_3d.view_location=Vector((0,0,.15))
            space.region_3d.view_perspective='ORTHO'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'surface-ropes-0.12.0-review.blend'),compress=True)
print('OVERHAND_REVIEW_READY')
