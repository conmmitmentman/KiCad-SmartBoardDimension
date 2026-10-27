#!/usr/bin/env python3
"""GitHub Release向けのオフライン導入ZIPを作成する（標準ライブラリのみ）。"""
from __future__ import annotations

import argparse
import ast
import hashlib
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

REPOSITORY = Path(__file__).resolve().parents[1]
RELEASE_FILES = (
    'README.md',
    'README_最初にお読みください.txt',
    'LICENSE',
    'ATTRIBUTION.md',
    'CHANGELOG.md',
    'Windows_インストール.bat',
    'Windows_更新.bat',
    'Windows_前の版に戻す.bat',
    'scripts/installer.ps1',
    'smart_board_dimension/__init__.py',
    'smart_board_dimension/geometry.py',
    'smart_board_dimension/updater.py',
    'smart_board_dimension/canvas.py',
    'smart_board_dimension/direct_editor.py',
    'docs/INSTALL_JA.md',
    'docs/UPDATE_JA.md',
    'docs/ONLINE_UPDATE_JA.md',
    'docs/USAGE_JA.md',
    'docs/TROUBLESHOOTING_JA.md',
    'docs/VALIDATION_JA.md',
    'docs/images/dimension-editor.png',
)


def read_plugin_version() -> str:
    tree = ast.parse((REPOSITORY / 'smart_board_dimension/__init__.py').read_text('utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == 'PLUGIN_VERSION' for t in node.targets):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
    raise RuntimeError('PLUGIN_VERSION が見つかりません。')


def build(output_dir: Path) -> Path:
    version = read_plugin_version()
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f'KiCad10_SmartBoardDimension_v{version}_Windows.zip'
    target = output_dir / filename
    plugin_names = [p for p in RELEASE_FILES if p.startswith('smart_board_dimension/') and p.endswith('.py')]
    manifest = {
        'schema': 1,
        'version': version,
        'files': {Path(name).name: hashlib.sha256((REPOSITORY / name).read_bytes()).hexdigest()
                  for name in plugin_names},
    }
    with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for name in RELEASE_FILES:
            source = REPOSITORY / name
            if not source.is_file():
                raise FileNotFoundError(source)
            archive.write(source, arcname=name)
        import json
        archive.writestr('update_manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    with ZipFile(target) as archive:
        if set(archive.namelist()) != set(RELEASE_FILES) | {'update_manifest.json'}:
            raise RuntimeError('ZIPの検証に失敗しました。')
        if archive.testzip() is not None:
            raise RuntimeError('ZIPに破損したファイルがあります。')
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output_dir / (filename + '.sha256')).write_text(
        f'{digest}  {filename}\n', encoding='ascii'
    )
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=REPOSITORY / 'dist')
    args = parser.parse_args()
    output = build(args.output_dir)
    print(f'Release ZIP: {output}')


if __name__ == '__main__':
    main()
