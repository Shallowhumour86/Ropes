"""Verify the distributable ZIP through Blender's real add-on installation API."""
import os
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parents[1]
# Use a temporary user profile; never modify a real Blender user's configuration.
profile = tempfile.mkdtemp(prefix='ropes-package-')
os.environ['BLENDER_USER_CONFIG'] = str(Path(profile) / 'config')
os.environ['BLENDER_USER_SCRIPTS'] = str(Path(profile) / 'scripts')
os.environ['BLENDER_USER_EXTENSIONS'] = str(Path(profile) / 'extensions')
Path(os.environ['BLENDER_USER_CONFIG']).mkdir(parents=True)
Path(os.environ['BLENDER_USER_SCRIPTS']).mkdir(parents=True)
Path(os.environ['BLENDER_USER_EXTENSIONS']).mkdir(parents=True)
import bpy
import addon_utils

archive = root / 'dist' / 'surface-ropes-0.12.0.zip'
result = bpy.ops.preferences.addon_install(filepath=str(archive))
assert result == {'FINISHED'}, result
bpy.utils.refresh_script_paths()
module = addon_utils.enable('ropes', default_set=True, persistent=True)
assert module is not None, 'Installed module did not enable'
assert Path(module.__file__).resolve().is_relative_to(Path(profile))
assert module.bl_info['blender'] == (4, 4, 0)
assert module.bl_info['version'] == (0, 12, 0)
assert hasattr(bpy.types.Scene, 'ropes_settings')
assert hasattr(bpy.types.Object, 'ropes_rope')
addon_utils.disable('ropes', default_set=True)
assert not hasattr(bpy.types.Scene, 'ropes_settings')
module = addon_utils.enable('ropes', default_set=True, persistent=True)
assert module is not None
addon_utils.disable('ropes', default_set=True)
print('PACKAGE_INSTALL_ENABLE_DISABLE_PASSED', bpy.app.version_string)
