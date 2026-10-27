"""Publish the tested native source release; preserve existing releases and Python latest."""
import json
import os
from pathlib import Path
import subprocess

from build_native_release import ROOT, TAG, VERSION, build


def main():
    archive = build(ROOT / 'dist')
    checksum = archive.with_suffix('.zip.sha256')
    repo = os.environ['GITHUB_REPOSITORY']
    tag = TAG
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
        f'# KiCad 10.0.7 ネイティブ駆動寸法 — Source v{VERSION}\n\n'
        '**正式なソース配布版です。コンパイル済みアプリ・インストーラーは含みません。**\n\n'
        '標準寸法の数字から数値・計算式を入力して、長方形の幅・高さと円の半径・直径を変更するC++実装です。'
        'Pythonプラグイン版とは別に、KiCad本体をビルドして使用します。\n\n'
        'WindowsでPCBエディタとQAのビルド・起動を確認。パッチ生成テスト6件、'
        '長方形・円のC++テスト17件と既存BoardCommitテスト8件が成功しました。'
        '画面操作の確認内容と対応範囲は、同梱のnative/README.mdを参照してください。\n\n'
        '操作感はSolidCraftを参考にした独自実装です。コードや画像は取り込んでいません。'
        'SolidCraftの公式・提携・推奨製品ではありません。詳細は同梱のATTRIBUTION.mdに記載しています。\n\n'
        f'対象・制約・導入方法は [native/README.md](https://github.com/{repo}/blob/'
        f'{os.environ["GITHUB_SHA"]}/native/README.md) を参照してください。\n',
        encoding='utf-8')
    subprocess.run(['gh', 'release', 'create', tag, str(archive), str(checksum),
                    '--repo', repo, '--target', os.environ['GITHUB_SHA'],
                    '--title', f'KiCad native dimensions — Source v{VERSION}',
                    '--latest=false', '--notes-file', str(notes)], check=True)


if __name__ == '__main__':
    main()
