"""Render the surface-contact regression against the preserved 0.6.0 package."""
from pathlib import Path
source=Path(__file__).with_name('knot_gallery.py').read_text()
source=source.replace('x_subdivisions=91, y_subdivisions=91, size=6','x_subdivisions=151, y_subdivisions=31, size=4')
source=source.replace('settings = scene.ropes_settings','''import math
for vertex in target.data.vertices:
    vertex.co.z=.11*math.cos(14*vertex.co.x)+.05*vertex.co.y*vertex.co.y
target.data.update()
settings = scene.ropes_settings''')
a=source.index('for row, label, kind, doubled in [')
b=source.index('bpy.ops.object.camera_add',a)
source=source[:a]+'''import tempfile,zipfile,importlib
reference_root=Path(tempfile.mkdtemp(prefix='ropes-contact-reference-'))
package=reference_root/'ropes_060_reference'
package.mkdir()
with zipfile.ZipFile(ROOT/'dist'/'surface-ropes-0.6.0.zip') as archive:
    for filename in ('__init__.py','geometry.py'):
        (package/filename).write_bytes(archive.read('ropes/'+filename))
sys.path.insert(0,str(reference_root))
old=importlib.import_module('ropes_060_reference')
owners=[]
for row,label in [( .8,'0.6.0'),(-.8,'0.9.2')]:
    with ropes.quiet_updates():
        rope=ropes.new_rope(scene,target)
        rope.name=label
        rope.ropes_rope.doubled=True
        for x in (-1.5,1.5):
            rope.ropes_rope.anchors.add().position=(x,row,.11*math.cos(14*x)+.05*row*row)
    owners.append(rope)
ropes.rebuild(scene,target)
legacy=owners[0]
path,_=old.display_path(scene,legacy,old.Surface(target,0),old.rest_path(legacy))
ropes.set_curve(legacy,path,legacy.ropes_rope.radius)
legacy.data.bevel_depth=0
for index,strand in enumerate(old.three_strands(path,legacy.ropes_rope.radius,legacy.ropes_rope.strand_pitch)):
    helper=next(o for o in scene.objects if o.get('ropes_owner')==legacy.ropes_rope.uid and o.get('ropes_strand')==index)
    ropes.set_strand(helper,strand,legacy.ropes_rope.radius)
for row,label in [( .8,'0.6.0'),(-.8,'0.9.2')]:
    bpy.ops.object.text_add(location=(-1.95,row+.25,.2))
    text=bpy.context.object
    text.data.body=label
    text.data.size=.15
''' +source[b:]
source=source.replace('settings.radius = .075','settings.radius = .05').replace('settings.squish = .65','settings.squish = 0')
source=source.replace('location=(0, -6, 7)','location=(0, -6, 4)').replace('ortho_scale = 6.3','ortho_scale = 4.6')
source=source.replace('surface-ropes-0.9.2-knots.png','surface-ropes-0.9.2-contact.png')
exec(compile(source,str(Path(__file__).with_name('knot_gallery.py')),'exec'))
