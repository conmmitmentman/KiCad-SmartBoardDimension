"""Publish the source-only native preview; never replace an existing release."""
import json
import os
from pathlib import Path
import subprocess

from build_native_release import ROOT, build


def main():
    archive = build(ROOT / 'dist')
    checksum = archive.with_suffix('.zip.sha256')
    repo = os.environ['GITHUB_REPOSITORY']
    tag = 'native-source-preview-1'
    result = subprocess.run(['gh', 'api', f'repos/{repo}/releases/tags/{tag}'],
                            capture_output=True, text=True)
    if result.returncode == 0:
        release = json.loads(result.stdout)
        if release['draft']:
            raise RuntimeError('An existing draft needs review before publishing')
        print(f'{tag} already exists; leaving it unchanged.')
        return
    if 'HTTP 404' not in result.stderr:
        raise RuntimeError('Cannot check existing release: ' + result.stderr)
    notes = ROOT / 'native-release-notes.tmp.md'
    notes.write_text(
        '# KiCad 10.0.7 ネイティブ駆動寸法 — Source Preview 1\n\n'
        '**ソースパッチの試作版です。コンパイル済みアプリ・インストーラーは含みません。**\n\n'
        '標準寸法の数字から数値・計算式を入力して長方形外形を変更するC++実装です。'
        'Pythonプラグイン版とは別に、KiCad本体をビルドして使用します。\n\n'
        'WindowsでPCBエディタとQAのビルド・起動を確認。パッチ生成テスト6件、'
        '追加C++テスト8件と既存BoardCommitテスト8件が成功しました。'
        'クリック編集、角への吸着、Undo/Redo、保存後の画面操作は検証中です。\n\n'
        f'対象・制約・導入方法は [native/README.md](https://github.com/{repo}/blob/'
        f'{os.environ["GITHUB_SHA"]}/native/README.md) を参照してください。\n',
        encoding='utf-8')
    subprocess.run(['gh', 'release', 'create', tag, str(archive), str(checksum),
                    '--repo', repo, '--target', os.environ['GITHUB_SHA'],
                    '--title', 'KiCad native dimensions — Source Preview 1',
                    '--prerelease', '--latest=false', '--notes-file', str(notes)], check=True)


if __name__ == '__main__':
    main()
