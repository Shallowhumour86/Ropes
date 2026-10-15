"""Render single and doubled runs along concave creases using actual add-on geometry."""
from pathlib import Path
source=Path(__file__).with_name('knot_gallery.py').read_text()
source=source.replace("settings = scene.ropes_settings", """for vertex in target.data.vertices:
    vertex.co.z=.8*min(abs(vertex.co.y-.65),abs(vertex.co.y+.65))
target.data.update()
settings = scene.ropes_settings""")
a=source.index('for row, label, kind, doubled in [')
b=source.index('bpy.ops.object.camera_add',a)
source=source[:a]+'''for row,doubled in [(.65,False),(-.65,True)]:
    with ropes.quiet_updates():
        rope=ropes.new_rope(scene,target)
        rope.ropes_rope.doubled=doubled
        for x in (-1.8,-.6,.6,1.8):
            anchor=rope.ropes_rope.anchors.add()
            anchor.position=(x,row,0)
            anchor.kind='SPANNING' if abs(x)<1 else 'NORMAL'
ropes.rebuild(scene,target)
''' +source[b:]
source=source.replace('surface-ropes-0.5.0-knots.png','surface-ropes-0.5.0-valleys.png')
exec(compile(source,str(Path(__file__).with_name('knot_gallery.py')),'exec'))
