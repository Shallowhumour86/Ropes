"""Build an installable legacy add-on ZIP without bundling tests or caches."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
output = root / 'dist' / 'surface-ropes-0.9.2.zip'
output.parent.mkdir(exist_ok=True)
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for filename in ('__init__.py', 'geometry.py'):
        archive.write(root / 'ropes' / filename, 'ropes/' + filename)
    for filename in ('README.md', 'LICENSE', 'KNOT_SOURCES.md'):
        archive.write(root / filename, 'ropes/' + filename)
print(output)
