"""Validate the checked-in ZIP, then publish a new version using GitHub CLI.

Existing releases are left intact. GH_TOKEN is supplied by GitHub Actions.
Use --check-only for local validation without any GitHub writes.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from zipfile import ZipFile

from build_release import REPOSITORY, RELEASE_FILES, read_plugin_version


def check_distribution():
    version = read_plugin_version()
    archive = REPOSITORY / 'dist' / f'KiCad10_SmartBoardDimension_v{version}_Windows.zip'
    checksum = archive.with_name(archive.name + '.sha256')
    expected = checksum.read_text('ascii').strip()
    actual = f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}'
    if expected != actual:
        raise ValueError('Distribution checksum mismatch')
    with ZipFile(archive) as package:
        if set(package.namelist()) != set(RELEASE_FILES) | {'update_manifest.json'}:
            raise ValueError('Distribution file list mismatch')
        for name in RELEASE_FILES:
            if package.read(name) != (REPOSITORY / name).read_bytes():
                raise ValueError(f'Distribution is stale: {name}')
    spec = importlib.util.spec_from_file_location('release_updater', REPOSITORY / 'smart_board_dimension/updater.py')
    updater = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(updater)
    updater.verify_archive(archive.read_bytes(), version)
    return version, archive, checksum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    version, archive, checksum = check_distribution()
    print(f'Validated v{version}: {archive.name}')
    if args.check_only:
        return
    repo = os.environ['GITHUB_REPOSITORY']
    sha = os.environ['GITHUB_SHA']
    tag = f'v{version}'
    result = subprocess.run(['gh', 'api', f'repos/{repo}/releases/tags/{tag}'],
                            capture_output=True, text=True)
    if result.returncode == 0:
        release = json.loads(result.stdout)
        if release['draft']:
            raise RuntimeError('A draft already exists; inspect it before publishing')
        print(f'{tag} is already published; leaving it unchanged.')
        return
    if 'HTTP 404' not in result.stderr:
        raise RuntimeError('Cannot check existing release: ' + result.stderr)
    changelog = (REPOSITORY / 'CHANGELOG.md').read_text('utf-8')
    section = changelog.split(f'## [{version}]', 1)[1].split('\n## [', 1)[0]
    notes = REPOSITORY / 'release-notes.tmp.md'
    notes.write_text(f'## スマート基板寸法 {tag}\n' + '\n'.join(section.splitlines()[1:])
                     + '\n詳細・導入方法はREADMEとdocs/VALIDATION_JA.mdを参照してください。\n', encoding='utf-8')
    subprocess.run(['gh', 'release', 'create', tag, str(archive), str(checksum),
                    '--repo', repo, '--target', sha, '--title', f'スマート基板寸法 {tag}',
                    '--notes-file', str(notes)], check=True)


if __name__ == '__main__':
    main()
