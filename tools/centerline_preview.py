"""Render centreline clearance controls in three narrow, varying grooves."""
from pathlib import Path
source=Path(__file__).with_name('knot_gallery.py').read_text()
source=source.replace('x_subdivisions=91, y_subdivisions=91, size=6','x_subdivisions=121, y_subdivisions=121, size=6')
source=source.replace('settings = scene.ropes_settings',"""import math
for vertex in target.data.vertices:
    x,y=vertex.co.x,vertex.co.y
    distance=min(abs(y-row) for row in (-1.5,0,1.5))
    vertex.co.z=(.18+.12*math.cos(5*x))*min(1,distance/.05)
target.data.update()
settings = scene.ropes_settings""")
a=source.index('for row, label, kind, doubled in [')
b=source.index('bpy.ops.object.camera_add',a)
source=source[:a]+"""wire=target.modifiers.new('Preview surface wire','WIREFRAME')
wire.thickness=.002
wire.use_replace=True
settings.radius=.07
settings.subdivisions=0
for row,tightness,doubled in [(1.5,0,False),(0,.5,True),(-1.5,1,False)]:
    with ropes.quiet_updates():
        rope=ropes.new_rope(scene,target)
        rope.ropes_rope.tension=tightness
        rope.ropes_rope.squish=1
        rope.ropes_rope.doubled=doubled
        for x in (-1.8,0,1.8):
            rope.ropes_rope.anchors.add().position=(x,row,0)
    bpy.ops.object.text_add(location=(-2.7,row+.45,.4))
    text=bpy.context.object
    text.data.body='Tightness '+str(tightness)+(' / doubled' if doubled else '')
    text.data.size=.17
ropes.rebuild(scene,target)
"""+source[b:]
source=source.replace('surface-ropes-0.10.0-knots.png','surface-ropes-0.10.0-centerlines.png')
exec(compile(source,str(Path(__file__).with_name('knot_gallery.py')),'exec'))
