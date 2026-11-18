"""Stage the native PCB editor with the compiled Rust Windows launcher.

Developer packaging only. This does not build or publish KiCad; corresponding
sources, dependency notices and clean-PC verification remain release prerequisites.
"""
import argparse
import hashlib
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAUNCHER = ROOT / 'target/release/smartboard-launcher.exe'


def stage(build, stock, output, launcher=DEFAULT_LAUNCHER):
    if output.exists():
        raise ValueError('Output already exists; choose a new directory')
    deps = build / 'vcpkg_installed/x64-windows'
    required = [build / 'pcbnew/pcbnew.exe', build / 'pcbnew/_pcbnew.dll',
                deps / 'tools/python3/python.exe', stock / 'share/kicad/internat/ja/kicad.mo',
                launcher, ROOT / 'Cargo.toml', ROOT / 'Cargo.lock']
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    # A missing/unbuilt Rust executable must fail before any output directory is created.
    with launcher.open('rb') as executable:
        if executable.read(2) != b'MZ':
            raise ValueError('Launcher must be a compiled Windows executable')
    app = output / 'app'
    binary = app / 'bin'
    binary.mkdir(parents=True)
    for directory in [deps / 'bin', build / 'common', build / 'common/gal', build / 'api',
                      build / '3d-viewer/3d_cache/sg', build / 'pcbnew']:
        for pattern in ('*.dll', '*.kiface'):
            for path in directory.glob(pattern):
                shutil.copy2(path, binary / path.name)
    for name in ['pcbnew.exe', 'pcbnew.py']:
        shutil.copy2(build / 'pcbnew' / name, binary / name)
    for pattern in ['vcruntime*.dll', 'msvcp*.dll', 'concrt*.dll']:
        for path in (stock / 'bin').glob(pattern):
            shutil.copy2(path, binary / path.name)
    shutil.copytree(deps / 'tools/python3', app / 'python',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pdb', '*.pyc'))
    for name in ['internat/ja', 'resources', 'schemas', 'scripting']:
        shutil.copytree(stock / 'share/kicad' / name, app / 'share/kicad' / name)
    shutil.copytree(stock / 'share/locale/ja', app / 'share/locale/ja')
    for path in (deps / 'share').rglob('copyright'):
        target = app / 'licenses/vcpkg' / path.relative_to(deps / 'share')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    if (stock / 'share/doc').is_dir():
        shutil.copytree(stock / 'share/doc', app / 'licenses/stock')
    (app / 'licenses').mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'LICENSE', app / 'licenses/Launcher-MIT.txt')
    # Preserve the Cargo workspace layout. Build/test artifacts are not source inputs.
    sources = app / 'source-patch'
    shutil.copytree(ROOT / 'native', sources / 'native',
                    ignore=shutil.ignore_patterns('__pycache__', '*.kicad_pro', '*.kicad_prl',
                                                  '*.lck', '*~', '*.bak', '*-backups',
                                                  'target', 'test-output', 'Launcher.cs', 'test_launcher.ps1'))
    for name in ('Cargo.toml', 'Cargo.lock', 'ATTRIBUTION.md', 'LICENSE', 'README.md'):
        shutil.copy2(ROOT / name, sources / name)
    (sources / 'tools').mkdir()
    shutil.copy2(Path(__file__), sources / 'tools/build_native_windows.py')
    (app / 'examples').mkdir()
    shutil.copy2(ROOT / 'native/examples/circle.kicad_pcb', app / 'examples/circle.kicad_pcb')
    shutil.copy2(ROOT / 'ATTRIBUTION.md', app / 'ATTRIBUTION.md')
    # Both entry points are the same Rust program; layout selects installer/launcher mode.
    shutil.copy2(launcher, app / 'SmartBoardDimension.exe')
    shutil.copy2(launcher, output / 'Install.exe')
    manifest = app / 'manifest.sha256'
    count = 0
    with manifest.open('w', encoding='utf-8', newline='\n') as out:
        for path in sorted(app.rglob('*')):
            if path == manifest or not path.is_file():
                continue
            digest = hashlib.sha256()
            with path.open('rb') as file:
                for chunk in iter(lambda: file.read(65536), b''):
                    digest.update(chunk)
            out.write(f'{digest.hexdigest()}  {path.relative_to(app).as_posix()}\n')
            count += 1
    print('Staged', count, 'files with Rust launcher at', output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--stock', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--launcher', type=Path, default=DEFAULT_LAUNCHER,
                        help='Compiled Rust launcher (default: target/release/smartboard-launcher.exe)')
    args = parser.parse_args()
    stage(args.build.resolve(), args.stock.resolve(), args.output.resolve(), args.launcher.resolve())
