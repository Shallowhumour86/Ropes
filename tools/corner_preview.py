"""Render sparse and dense waypoint runs wrapping around a convex cube edge."""
from pathlib import Path
source=Path(__file__).with_name('knot_gallery.py').read_text()
source=source.replace('bpy.ops.mesh.primitive_grid_add(x_subdivisions=91, y_subdivisions=91, size=6)','bpy.ops.mesh.primitive_cube_add(size=2)')
a=source.index('for row, label, kind, doubled in [')
b=source.index('bpy.ops.object.camera_add',a)
source=source[:a]+"""settings.radius=.05
settings.squish=0
for row,dense in [(-.5,False),(.5,True)]:
    with ropes.quiet_updates():
        rope=ropes.new_rope(scene,target)
        rope.ropes_rope.doubled=True
        points=[(-.7,row,1),(.8,row,1),(.95,row,1),(1,row,1),(1,row,.95),(1,row,.8),(1,row,-.7)] if dense else [(-.7,row,1),(1,row,.7),(1,row,-.7)]
        for point in points:
            rope.ropes_rope.anchors.add().position=point
ropes.rebuild(scene,target)
"""+source[b:]
source=source.replace('location=(0, -6, 7)','location=(4,-6,4)').replace('ortho_scale = 6.3','ortho_scale = 3.6')
source=source.replace('surface-ropes-0.8.0-knots.png','surface-ropes-0.8.0-corners.png')
exec(compile(source,str(Path(__file__).with_name('knot_gallery.py')),'exec'))
