"""Render both participants of a doubled junction in contrasting colors."""
from pathlib import Path
source = Path(__file__).with_name('knot_gallery.py').read_text()
start = source.index('for row, label, kind, doubled in [')
end = source.index('bpy.ops.object.camera_add', start)
source = source[:start] + '''owners=[]
settings.radius=.05
settings.squish=0
for row,doubled,label in [(1.3,False,'Single junction'),(-1.3,True,'Doubled junction')]:
    for name,points in [('Rope A',[(-1.8,row,0),(1.8,row,0)]),('Rope B',[(0,row-1.1,0),(0,row+1.1,0)])]:
        with ropes.quiet_updates():
            rope=ropes.new_rope(scene,target)
            rope.name=label+' '+name
            rope.ropes_rope.doubled=doubled
            for point in points:
                rope.ropes_rope.anchors.add().position=point
        owners.append(rope)
    bpy.ops.object.text_add(location=(-2.7,row+.8,.015))
    text=bpy.context.object
    text.data.body=label
    text.data.size=.18
ropes.rebuild(scene,target)
for junction in settings.junctions:
    junction.is_knot=True
ropes.rebuild(scene,target,repath=False)
for owner,color in zip(owners,[(.65,.28,.08,1),(.12,.42,.65,1)]*2):
    for obj in scene.objects:
        if obj.get('ropes_owner')==owner.ropes_rope.uid and obj.type=='MESH':
            mat=obj.data.materials[0].copy()
            for node in mat.node_tree.nodes:
                if node.type=='VALTORGB':
                    for element in node.color_ramp.elements:
                        strength=sum(element.color[:3])/3
                        element.color=tuple(c*strength for c in color[:3])+(1,)
            obj.data.materials[0]=mat
''' + source[end:]
source=source.replace("surface-ropes-0.8.0-knots.png","surface-ropes-0.8.0-junction.png")
exec(compile(source, str(Path(__file__).with_name('knot_gallery.py')), 'exec'))
