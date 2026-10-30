"""Stage a self-contained Windows PCB editor from a verified local KiCad build.

Developer tool. Public binary distribution still requires corresponding sources
and a clean-PC installation test; this tool does not publish anything.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def stage(build, stock, output):
    # Never merge into an old package: stale DLLs must not survive a rebuild.
    if output.exists():
        raise ValueError('Output already exists; choose a new directory')
    deps = build / 'vcpkg_installed/x64-windows'
    required = [build / 'pcbnew/pcbnew.exe', build / 'pcbnew/_pcbnew.dll',
                deps / 'tools/python3/python.exe', stock / 'share/kicad/internat/ja/kicad.mo']
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    app = output / 'app'
    binary = app / 'bin'
    binary.mkdir(parents=True)
    for directory in [deps / 'bin', build / 'common', build / 'common/gal', build / 'api',
                      build / '3d-viewer/3d_cache/sg', build / 'pcbnew']:
        for path in directory.glob('*.dll'):
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
    # wxWidgets supplies translations for common dialogs separately from KiCad.
    shutil.copytree(stock / 'share/locale/ja', app / 'share/locale/ja')
    # Include upstream notices for all bundled dependency packages.
    for path in (deps / 'share').rglob('copyright'):
        target = app / 'licenses/vcpkg' / path.relative_to(deps / 'share')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    if (stock / 'share/doc').is_dir():
        shutil.copytree(stock / 'share/doc', app / 'licenses/stock')
    shutil.copytree(ROOT / 'native', app / 'source-patch',
                    ignore=shutil.ignore_patterns('__pycache__', '*.kicad_pro', '*.kicad_prl',
                                                  '*.lck', '*~', '*.bak', '*-backups'))
    (app / 'examples').mkdir()
    shutil.copy2(ROOT / 'native/examples/circle.kicad_pcb', app / 'examples/circle.kicad_pcb')
    shutil.copy2(ROOT / 'ATTRIBUTION.md', app / 'ATTRIBUTION.md')
    shutil.copy2(ROOT / 'LICENSE', app / 'licenses/Launcher-MIT.txt')
    compiler = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64',
                    '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll',
                    '/reference:Microsoft.CSharp.dll', '/out:' + str(app / 'SmartBoardDimension.exe'),
                    str(ROOT / 'native/windows/Launcher.cs')], check=True)
    shutil.copy2(app / 'SmartBoardDimension.exe', output / 'Install.exe')
    lines = [hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.relative_to(app).as_posix()
             for p in sorted(app.rglob('*')) if p.is_file()]
    (app / 'manifest.sha256').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Staged', len(lines), 'files at', output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--stock', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    stage(args.build.resolve(), args.stock.resolve(), args.output.resolve())
