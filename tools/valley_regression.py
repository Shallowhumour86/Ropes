"""Render single and doubled ropes through a coarse variable-width groove."""
from pathlib import Path
source=Path(__file__).with_name('knot_gallery.py').read_text()
a=source.index('bpy.ops.mesh.primitive_grid_add')
b=source.index("target.name =",a)
source=source[:a]+'''import math
xs=[-2+i*.1 for i in range(41)]
ys=[-1.3,-.9,-.78,-.65,-.52,-.4,0,.4,.52,.65,.78,.9,1.3]
vertices=[(x,y,(.3+.2*math.cos(x*4))*min(1,min(abs(y-.65),abs(y+.65))/.13)) for x in xs for y in ys]
n=len(ys)
faces=[(i*n+j,(i+1)*n+j,(i+1)*n+j+1,i*n+j+1) for i in range(40) for j in range(n-1)]
mesh=bpy.data.meshes.new('Coarse varying valleys')
mesh.from_pydata(vertices,[],faces)
target=bpy.data.objects.new('Coarse varying valleys',mesh)
scene.collection.objects.link(target)
''' +source[b:]
a=source.index('for row, label, kind, doubled in [')
b=source.index('bpy.ops.object.camera_add',a)
source=source[:a]+'''for row,doubled in [(.65,False),(-.65,True)]:
    with ropes.quiet_updates():
        rope=ropes.new_rope(scene,target)
        rope.ropes_rope.doubled=doubled
        for x in (-1.8,1.8):
            rope.ropes_rope.anchors.add().position=(x,row,0)
ropes.rebuild(scene,target)
''' +source[b:]
source=source.replace('settings.radius = .075','settings.radius = .04').replace('settings.squish = .65','settings.squish = 0')
source=source.replace('location=(0, -6, 7)','location=(2, -6, 6)').replace('ortho_scale = 6.3','ortho_scale = 5')
source=source.replace('surface-ropes-0.9.1-knots.png','surface-ropes-0.9.1-valley-regression.png')
exec(compile(source,str(Path(__file__).with_name('knot_gallery.py')),'exec'))
