"""Render both participants of a doubled junction in contrasting colors."""
from pathlib import Path
source = Path(__file__).with_name('knot_gallery.py').read_text()
start = source.index('for row, label, kind, doubled in [')
end = source.index('bpy.ops.object.camera_add', start)
source = source[:start] + '''owners=[]
for name,points in [('Rope A',[(-2,0,0),(2,0,0)]),('Rope B',[(0,-2,0),(0,2,0)])]:
    with ropes.quiet_updates():
        rope=ropes.new_rope(scene,target)
        rope.name=name
        rope.ropes_rope.doubled=True
        for point in points:
            rope.ropes_rope.anchors.add().position=point
    owners.append(rope)
ropes.rebuild(scene,target)
settings.junctions[0].is_knot=True
ropes.rebuild(scene,target,repath=False)
for owner,color in zip(owners,[(.65,.28,.08,1),(.12,.42,.65,1)]):
    for obj in scene.objects:
        if obj.get('ropes_owner')==owner.ropes_rope.uid and obj.type=='MESH':
            mat=obj.data.materials[0].copy()
            mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=color
            # Keep the rope fiber shader, tint its ramp instead.
            for node in mat.node_tree.nodes:
                if node.type=='VALTORGB':
                    for element in node.color_ramp.elements:
                        strength=sum(element.color[:3])/3
                        element.color=tuple(c*strength for c in color[:3])+(1,)
            obj.data.materials[0]=mat
''' + source[end:]
source=source.replace("surface-ropes-0.6.0-knots.png","surface-ropes-0.6.0-junction.png")
exec(compile(source, str(Path(__file__).with_name('knot_gallery.py')), 'exec'))
