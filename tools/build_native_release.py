#!/usr/bin/env python3
"""Package the native source patch. This archive does not install a KiCad binary."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import argparse
import hashlib

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0.0'
TAG = 'native-source-v' + VERSION
FILES = (
    'README.md', 'README_PROTOTYPE_JA.md',
    'LICENSE_PYTHON.txt', 'LICENSE_GPLv3.txt',
    'native_patch/apply_native_patch.py',
    'native_patch/smart_board_driving_dimension_impl.h',
    'native_patch/smart_board_driving_dimension_ui.h',
    'native_patch/smart_board_driving_circle.h',
    'native_patch/test_smart_board_driving_dimension.cpp',
    'tests/test_patch.py',
    'launch_windows.ps1',
    'examples/circle.kicad_pcb',
)


def build(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f'KiCad10_NativeDrivingDimension_Source_v{VERSION}.zip'
    notice = (f'KiCad 10.0.7 native driving dimensions - SOURCE RELEASE {VERSION}\n\n'
              'This is source code, not an installer or a compiled KiCad application.\n'
              'Read native/README.md for the current verification status and build instructions.\n'
              'Applying this patch requires a separate KiCad 10.0.7 source checkout.\n')
    with ZipFile(target, 'w', ZIP_DEFLATED) as z:
        z.writestr('START_HERE.txt', notice)
        for name in ('ATTRIBUTION.md', 'LICENSE'):
            z.write(ROOT / name, name)
        for name in FILES:
            z.write(ROOT / 'native' / name, 'native/' + name)
    with ZipFile(target) as z:
        if z.testzip() is not None:
            raise RuntimeError('Archive integrity check failed')
        for name in ('ATTRIBUTION.md', 'LICENSE'):
            if z.read(name) != (ROOT / name).read_bytes():
                raise RuntimeError('Archive content mismatch: ' + name)
        for name in FILES:
            if z.read('native/' + name) != (ROOT / 'native' / name).read_bytes():
                raise RuntimeError('Archive content mismatch: ' + name)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{digest}  {target.name}\n', encoding='ascii')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    print(build(parser.parse_args().output_dir))
