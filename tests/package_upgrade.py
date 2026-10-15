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

old_name = sys.argv[2] if len(sys.argv) > 2 else 'surface-ropes-0.1.0.zip'
old = root / 'dist' / old_name
new = root / 'dist' / (sys.argv[1] if len(sys.argv) > 1 else 'surface-ropes-0.9.0.zip')
assert bpy.ops.preferences.addon_install(filepath=str(old)) == {'FINISHED'}
bpy.utils.refresh_script_paths()
module = addon_utils.enable('ropes', default_set=True, persistent=True)
assert module is not None
expected_old = tuple(map(int, old_name.removeprefix('surface-ropes-').removesuffix('.zip').split('.')))
assert module.bl_info['version'] == expected_old
old_geometry = sys.modules['ropes.geometry']
assert hasattr(old_geometry, 'three_strands') == (expected_old >= (0, 2, 0))

bpy.ops.mesh.primitive_grid_add(x_subdivisions=15, y_subdivisions=15, size=4)
surface = bpy.context.object
settings = bpy.context.scene.ropes_settings
settings.target = surface
settings.radius = .08
if expected_old >= (0, 3, 0):
    settings.double_spacing = 1.1 if expected_old >= (0, 5, 0) else 2.2
rope = module.new_rope(bpy.context.scene, surface)
for point in ((-1, 0, 0), (1, 0, 0)):
    rope.ropes_rope.anchors.add().position = point
module.rebuild(bpy.context.scene, surface)
if expected_old >= (0, 2, 0):
    rope.ropes_rope.squish = .6
else:
    settings.squish = .6
module.knot_at(bpy.context.scene, rope, 1.0)
uid = rope.ropes_rope.uid
if expected_old >= (0, 3, 0):
    rope.ropes_rope.doubled = True

# Blender's actual preferences installer disables, overwrites, reloads, and
# re-enables the enabled legacy add-on. Its child module can remain cached.
assert bpy.ops.preferences.addon_install(filepath=str(new), overwrite=True) == {'FINISHED'}
module = addon_utils.enable('ropes', default_set=True, persistent=True)
assert module is not None, 'Upgraded add-on failed to enable'
assert module.bl_info['version'] == (0, 9, 0)
# The headless Python-module runner has no UI event loop to execute timers.
assert module.migrate_after_enable() is None
settings = bpy.context.scene.ropes_settings
assert hasattr(sys.modules['ropes.geometry'], 'three_strands')
assert module.three_strands is sys.modules['ropes.geometry'].three_strands
assert sys.modules['ropes.geometry'] is old_geometry
assert rope.ropes_rope.uid == uid
assert len(rope.ropes_rope.anchors) == 2
assert len(rope.ropes_rope.knots) == 1
assert abs(rope.ropes_rope.radius-.08) < 1e-6
assert abs(rope.ropes_rope.squish-.6) < 1e-6
module.rebuild(bpy.context.scene, surface)
assert len([o for o in bpy.context.scene.objects if o.get('ropes_owner') == uid]) == 3
if expected_old >= (0, 3, 0):
    expected_spacing=1.1 if expected_old >= (0, 5, 0) else 2.2/2.02
    assert abs(rope.ropes_rope.double_spacing-expected_spacing)<1e-6
    assert abs(settings.double_spacing-expected_spacing)<1e-6
    points=module.visible_path(rope)
    assert abs((points[0]-points[-1]).length-.08*2.02*expected_spacing)<1e-5
    # Migration is idempotent on subsequent load/enable callbacks.
    module.migrate_after_enable()
    assert abs(rope.ropes_rope.double_spacing-expected_spacing)<1e-6
addon_utils.disable('ropes', default_set=True)
assert not hasattr(bpy.types.Scene, 'ropes_settings')
print('IN_PROCESS_UPGRADE_PASSED', expected_old, 'to', module.bl_info['version'], bpy.app.version_string)
