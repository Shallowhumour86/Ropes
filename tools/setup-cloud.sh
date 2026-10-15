#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Ropes
export UV_CACHE_DIR=/workspace/.ropes-tools/cache
export UV_PYTHON_INSTALL_DIR=/workspace/.ropes-tools/python
ropes_python=/workspace/.ropes-tools/venv/bin/python
if [ ! -x "$ropes_python" ]; then
    uv venv --python 3.11.17 /workspace/.ropes-tools/venv
fi
uv pip sync --python "$ropes_python" --require-hashes tests/requirements-blender44.txt
"$ropes_python" tests/blender_integration.py
"$ropes_python" tools/package.py
"$ropes_python" tests/package_install.py
"$ropes_python" tests/package_upgrade.py
"$ropes_python" tests/restricted_registration.py
"$ropes_python" tests/package_upgrade.py surface-ropes-0.8.0.zip surface-ropes-0.2.1.zip
"$ropes_python" tests/package_upgrade.py surface-ropes-0.8.0.zip surface-ropes-0.3.0.zip
"$ropes_python" tests/package_upgrade.py surface-ropes-0.8.0.zip surface-ropes-0.4.0.zip
"$ropes_python" tests/package_upgrade.py surface-ropes-0.8.0.zip surface-ropes-0.5.0.zip
"$ropes_python" tests/package_upgrade.py surface-ropes-0.8.0.zip surface-ropes-0.6.0.zip
"$ropes_python" tests/package_upgrade.py surface-ropes-0.8.0.zip surface-ropes-0.7.0.zip
