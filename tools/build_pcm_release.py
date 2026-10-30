"""Create a KiCad PCM archive without importing pcbnew or touching KiCad settings."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

try:
    from .build_release import REPOSITORY, RELEASE_FILES, read_plugin_version
except ImportError:
    from build_release import REPOSITORY, RELEASE_FILES, read_plugin_version


def build(output_dir):
    version = read_plugin_version()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f'KiCad10_SmartBoardDimension_v{version}_PCM.zip'
    metadata = {
        '$schema': 'https://go.kicad.org/pcm/schemas/v2',
        'name': 'Smart Board Dimension',
        'description': 'Drive simple PCB outlines from standard dimensions. Japanese UI. Testing release.',
        'description_full': 'Edit rectangle width/height and circle radius/diameter with expressions in the standard KiCad PCB editor. Japanese UI. GUI behavior and Undo/Redo have not been validated for this release.',
        'identifier': 'com.github.conmmitmentman.smartboarddimension',
        'type': 'plugin', 'license': 'MIT',
        'author': {'name': 'conmmitmentman', 'contact': {'web': 'https://github.com/conmmitmentman/KiCad-SmartBoardDimension/issues'}},
        'resources': {'homepage': 'https://github.com/conmmitmentman/KiCad-SmartBoardDimension'},
        'versions': [{'version': version, 'status': 'testing', 'kicad_version': '10.0',
                      'kicad_version_max': '10.99', 'runtime': 'swig'}],
    }
    with ZipFile(archive, 'w', ZIP_DEFLATED) as z:
        z.writestr('metadata.json', json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
        z.writestr('plugins/pcm-managed.txt', 'Update and uninstall this package with KiCad PCM.\n')
        for path in RELEASE_FILES:
            if path.startswith('smart_board_dimension/') and path.endswith('.py'):
                z.write(REPOSITORY / path, 'plugins/' + Path(path).name)
        for name in ('LICENSE', 'ATTRIBUTION.md'):
            z.write(REPOSITORY / name, 'plugins/' + name)
        z.write(REPOSITORY / 'docs/PLUGIN_1_4_JA.md', 'plugins/README_JA.md')
    with ZipFile(archive) as z:
        if z.testzip():
            raise RuntimeError('PCM archive integrity check failed')
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{checksum}  {archive.name}\n', encoding='ascii')
    return archive


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, default=REPOSITORY / 'dist')
    print(build(p.parse_args().output_dir))
