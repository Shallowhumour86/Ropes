"""Regression: install and enable 0.1, then upgrade in the same Blender process."""
import os
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
profile = Path(tempfile.mkdtemp(prefix='ropes-upgrade-'))
for kind in ('CONFIG', 'SCRIPTS', 'EXTENSIONS'):
    path = profile / kind.lower()
    path.mkdir()
    os.environ['BLENDER_USER_' + kind] = str(path)

import bpy
import addon_utils

old = root / 'dist' / 'surface-ropes-0.1.0.zip'
new = root / 'dist' / (sys.argv[1] if len(sys.argv) > 1 else 'surface-ropes-0.2.1.zip')
assert bpy.ops.preferences.addon_install(filepath=str(old)) == {'FINISHED'}
bpy.utils.refresh_script_paths()
module = addon_utils.enable('ropes', default_set=True, persistent=True)
assert module is not None
assert module.bl_info['version'] == (0, 1, 0)
old_geometry = sys.modules['ropes.geometry']
assert not hasattr(old_geometry, 'three_strands')

bpy.ops.mesh.primitive_grid_add(x_subdivisions=15, y_subdivisions=15, size=4)
surface = bpy.context.object
settings = bpy.context.scene.ropes_settings
settings.target = surface
settings.radius = .08
rope = module.new_rope(bpy.context.scene, surface)
for point in ((-1, 0, 0), (1, 0, 0)):
    rope.ropes_rope.anchors.add().position = point
module.rebuild(bpy.context.scene, surface)
settings.squish = .6
uid = rope.ropes_rope.uid

# Blender's actual preferences installer disables, overwrites, reloads, and
# re-enables the enabled legacy add-on. Its child module can remain cached.
assert bpy.ops.preferences.addon_install(filepath=str(new), overwrite=True) == {'FINISHED'}
module = addon_utils.enable('ropes', default_set=True, persistent=True)
assert module is not None, 'Upgraded add-on failed to enable'
assert module.bl_info['version'] >= (0, 2, 1)
# The headless Python-module runner has no UI event loop to execute timers.
assert module.migrate_after_enable() is None
assert hasattr(sys.modules['ropes.geometry'], 'three_strands')
assert module.three_strands is sys.modules['ropes.geometry'].three_strands
assert sys.modules['ropes.geometry'] is old_geometry
assert rope.ropes_rope.uid == uid
assert len(rope.ropes_rope.anchors) == 2
assert abs(rope.ropes_rope.radius-.08) < 1e-6
assert abs(rope.ropes_rope.squish-.6) < 1e-6
module.rebuild(bpy.context.scene, surface)
assert len([o for o in bpy.context.scene.objects if o.get('ropes_owner') == uid]) == 3
addon_utils.disable('ropes', default_set=True)
assert not hasattr(bpy.types.Scene, 'ropes_settings')
print('IN_PROCESS_0_1_UPGRADE_PASSED', bpy.app.version_string)
