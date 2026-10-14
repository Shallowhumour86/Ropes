"""Check desktop Blender's restricted enable context and failed-install recovery."""
from pathlib import Path
import sys
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
import bpy
from bpy_restrict_state import _RestrictData, _RestrictContext
import ropes

# The PyPI bpy module exposes a different module object from the one used by
# bpy_restrict_state internally. Patch the add-on's actual binding explicitly.
with patch.object(ropes.bpy, 'data', _RestrictData()), \
     patch.object(ropes.bpy, 'context', _RestrictContext()):
    ropes.register()
    assert bpy.app.timers.is_registered(ropes.migrate_after_enable)
    assert len(ropes.registered_classes()) == len(ropes.CLASSES)
    assert ropes.migrate_after_enable() == .1

assert ropes.migrate_after_enable() is None
ropes.unregister()
assert not ropes.registered_classes()
assert not hasattr(bpy.types.Scene, 'ropes_settings')
assert not bpy.app.timers.is_registered(ropes.migrate_after_enable)

# Reproduce the partial registration left by 0.2 when its scene scan raises.
for cls in ropes.CLASSES:
    bpy.utils.register_class(cls)
bpy.types.Object.ropes_rope = bpy.props.PointerProperty(type=ropes.ROPES_PG_Rope)
bpy.types.Scene.ropes_settings = bpy.props.PointerProperty(type=ropes.ROPES_PG_Settings)
bpy.app.handlers.load_post.append(ropes.migrate_on_load)
bpy.ops.mesh.primitive_grid_add(size=3)
target = bpy.context.object
scene = bpy.context.scene
scene.ropes_settings.target = target
rope = ropes.new_rope(scene, target)
rope.ropes_rope.anchors.add().position = (-1, 0, 0)
rope.ropes_rope.anchors.add().position = (1, 0, 0)
uid = rope.ropes_rope.uid

# Use a fresh copy of the entry module's classes, as an installer reload does.
import importlib
importlib.reload(ropes)
with patch.object(ropes.bpy, 'data', _RestrictData()), \
     patch.object(ropes.bpy, 'context', _RestrictContext()):
    ropes.register()
assert ropes.migrate_after_enable() is None
assert len(ropes.registered_classes()) == len(ropes.CLASSES)
assert sum(h.__module__ == 'ropes' and h.__name__ == 'migrate_on_load'
           for h in bpy.app.handlers.load_post) == 1
assert rope.ropes_rope.uid == uid
assert len(rope.ropes_rope.anchors) == 2
ropes.rebuild(scene, target)
ropes.unregister()
print('RESTRICTED_ENABLE_AND_PARTIAL_INSTALL_RECOVERY_PASSED', bpy.app.version_string)
