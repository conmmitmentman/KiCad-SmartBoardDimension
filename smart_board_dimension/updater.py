# -*- coding: utf-8 -*-
"""GitHub Releases からプラグインだけを安全に更新する。KiCad非依存。"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from datetime import datetime, timezone
from urllib import request, error
from urllib.parse import urlparse
from zipfile import ZipFile, BadZipFile
import ast

# 公開者は GitHub アップロード前に 'OWNER/REPOSITORY' を設定できます。
# 未設定の場合、利用者が最初の1回だけ画面から登録します。
DEFAULT_REPOSITORY = 'conmmitmentman/KiCad-SmartBoardDimension'
MAX_ASSET_BYTES = 12 * 1024 * 1024
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_JSON_BYTES = 1024 * 1024
REQUEST_TIMEOUT = 15
REPO_RE = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}$')
MODULE_RE = re.compile(r'^(?:__init__|[a-z][a-z0-9_]{0,60})\.py$')
VERSION_RE = re.compile(r'^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')


class UpdateError(Exception):
    """更新できない場合に日本語で表示するエラー。"""


def app_directory() -> Path:
    root = os.environ.get('LOCALAPPDATA')
    if root:
        return Path(root) / 'SmartBoardDimension'
    # Windows以外での手動配置も考慮する。
    return Path.home() / '.local' / 'share' / 'SmartBoardDimension'


def parse_repository(value: str) -> str:
    source = value.strip().rstrip('/')
    if source.startswith('https://github.com/'):
        source = source[len('https://github.com/'):]
    if source.endswith('.git'):
        source = source[:-4]
    if not REPO_RE.fullmatch(source) or '..' in source or source.endswith('.'):
        raise UpdateError('GitHubのリポジトリを OWNER/REPO または https://github.com/OWNER/REPO の形式で入力してください。')
    return source


def get_repository() -> str:
    settings_path = app_directory() / 'settings.json'
    try:
        if settings_path.is_file():
            settings = json.loads(settings_path.read_text(encoding='utf-8-sig'))
            if not isinstance(settings, dict):
                raise ValueError('設定はJSONオブジェクトである必要があります。')
            if settings.get('repository') and not isinstance(settings['repository'], str):
                raise ValueError('repositoryは文字列である必要があります。')
            if settings.get('repository'):
                return parse_repository(settings['repository'])
    except (OSError, ValueError, TypeError) as exc:
        raise UpdateError(f'保存済みの更新設定を読み込めません: {exc}') from exc
    return parse_repository(DEFAULT_REPOSITORY) if DEFAULT_REPOSITORY else ''


def save_repository(repository: str) -> None:
    repo = parse_repository(repository)
    folder = app_directory()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'settings.json'
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps({'repository': repo}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def version_tuple(value: str) -> tuple[int, int, int]:
    matched = VERSION_RE.fullmatch(value)
    if not matched:
        raise UpdateError(f'対応していないバージョン表記です: {value}')
    return tuple(int(s) for s in matched.groups())


def _get_url(url: str, maximum: int, *, accept: str) -> bytes:
    req = request.Request(url, headers={
        'User-Agent': 'KiCad10-SmartBoardDimension-Updater',
        'Accept': accept,
        'X-GitHub-Api-Version': '2022-11-28',
    })
    try:
        with request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            # 最終URLはGitHubのホスト、またはGitHubリリースのアセット配信ホストのみ。
            host = urlparse(response.geturl()).hostname or ''
            if urlparse(response.geturl()).scheme != 'https' or host not in (
                    'github.com', 'api.github.com', 'release-assets.githubusercontent.com',
                    'objects.githubusercontent.com'):
                raise UpdateError('GitHub以外のダウンロード先に転送されたため中断しました。')
            content = response.read(maximum + 1)
    except error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError('公開済みの正式Releaseまたは配布ファイルが見つかりません (HTTP 404)。\n'
                              '更新元URLとGitHub Releasesの公開状況を確認してください。\n'
                              'ソースやZIPをリポジトリに置くだけでは自動更新できません。\n'
                              '現在のプラグインはそのまま使用できます。') from exc
        raise UpdateError(f'GitHubの応答エラー (HTTP {exc.code})。接続・API利用制限を確認してください。') from exc
    except (error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError(f'GitHubへ接続できません: {exc}') from exc
    if len(content) > maximum:
        raise UpdateError('ダウンロードデータがサイズ上限を超えました。')
    return content


def check_latest(repository: str, installed: str) -> dict:
    """公開済みの最新Releaseを確認。ダウンロードはまだしない。"""
    repo = parse_repository(repository)
    version_tuple(installed)
    data = _get_url(
        f'https://api.github.com/repos/{repo}/releases/latest',
        MAX_JSON_BYTES, accept='application/vnd.github+json')
    try:
        release = json.loads(data)
        if release.get('draft') or release.get('prerelease'):
            raise UpdateError('公開済みの正式リリースが見つかりません。')
        tag = release['tag_name']
        new = version_tuple(tag)
        old = version_tuple(installed)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError('GitHubのRelease情報を解釈できません。') from exc
    if new <= old:
        return {'available': False, 'latest': tag, 'repository': repo}
    ver = '.'.join(map(str, new))
    name = f'KiCad10_SmartBoardDimension_v{ver}_Windows.zip'
    assets = release.get('assets') or []
    matched = [asset for asset in assets if asset.get('name') == name and asset.get('state') == 'uploaded']
    if len(matched) != 1:
        raise UpdateError(f'最新Release v{ver} に更新用ZIP「{name}」がありません。')
    asset = matched[0]
    url = asset.get('browser_download_url', '')
    expected = f'https://github.com/{repo}/releases/download/'
    if not isinstance(url, str) or not url.startswith(expected) or urlparse(url).hostname != 'github.com':
        raise UpdateError('ダウンロードURLが指定されたGitHubリポジトリと一致しません。')
    # GitHub が提供するダイジェストを優先。ない場合は .sha256 アセットを使う。
    digest = asset.get('digest') or ''
    if digest and not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest):
        raise UpdateError('Releaseのチェックサム形式が不正です。')
    hash_assets = [a for a in assets if a.get('name') == name + '.sha256']
    if not digest and not hash_assets:
        raise UpdateError('チェックサムがないReleaseは自動更新できません。')
    hash_url = ''
    if hash_assets:
        hash_url = hash_assets[0].get('browser_download_url', '')
        if not isinstance(hash_url, str) or not hash_url.startswith(expected) or urlparse(hash_url).hostname != 'github.com':
            raise UpdateError('チェックサムファイルのURLが不正です。')
    return {
        'available': True, 'repository': repo, 'latest': ver,
        'asset_url': url, 'asset_name': name, 'digest': digest[7:].lower() if digest else '',
        'hash_url': hash_url, 'size': asset.get('size', 0),
    }


def _verify_checksum(download: bytes, release: dict) -> None:
    calculated = hashlib.sha256(download).hexdigest()
    if release['digest']:
        expected = release['digest']
    else:
        content = _get_url(release['hash_url'], 1024, accept='application/octet-stream')
        line = content.decode('ascii', errors='strict').strip()
        match = re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?([^\r\n]+)', line)
        if not match or match.group(2) != release['asset_name']:
            raise UpdateError('ReleaseのSHA256ファイルを読み取れません。')
        expected = match.group(1).lower()
    if calculated != expected:
        raise UpdateError('ダウンロードしたZIPのSHA256検証に失敗しました。更新を中断します。')


def _plugin_version(source: bytes) -> str:
    try:
        tree = ast.parse(source.decode('utf-8-sig'))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                if any(isinstance(t, ast.Name) and t.id == 'PLUGIN_VERSION' for t in node.targets):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    except (SyntaxError, UnicodeError) as exc:
        raise UpdateError('プラグインのバージョンを読み取れません。') from exc
    raise UpdateError('更新ZIP内にバージョン定義がありません。')


def verify_archive(blob: bytes, expected_version: str) -> dict[str, bytes]:
    """ZIPを解凍せず、マニフェスト指定の.pyのみ読み取る（Zip Slip対策）。"""
    try:
        with ZipFile(io.BytesIO(blob)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or len(names) > 100:
                raise UpdateError('ZIPのファイル構成が不正です。')
            if 'update_manifest.json' not in names:
                raise UpdateError('自動更新対応のマニフェストがありません。')
            manifest_info = archive.getinfo('update_manifest.json')
            if manifest_info.file_size > 30000:
                raise UpdateError('更新マニフェストが大きすぎます。')
            manifest = json.loads(archive.read('update_manifest.json'))
            if manifest.get('schema') != 1 or manifest.get('version') != expected_version:
                raise UpdateError('Releaseタグと更新マニフェストのバージョンが一致しません。')
            files = manifest.get('files')
            if not isinstance(files, dict) or not 3 <= len(files) <= 32:
                raise UpdateError('更新対象ファイルの一覧が不正です。')
            if not {'__init__.py', 'geometry.py', 'updater.py'}.issubset(files):
                raise UpdateError('更新に必要なプラグインファイルが不足しています。')
            result = {}
            for filename, expected_hash in files.items():
                if not isinstance(filename, str) or not MODULE_RE.fullmatch(filename):
                    raise UpdateError('許可されないファイル名が含まれています。')
                if not isinstance(expected_hash, str) or not re.fullmatch('[0-9a-f]{64}', expected_hash):
                    raise UpdateError('マニフェストのSHA256値が不正です。')
                member = f'smart_board_dimension/{filename}'
                if member not in names:
                    raise UpdateError(f'プラグインファイルがありません: {member}')
                info = archive.getinfo(member)
                if info.file_size > MAX_SOURCE_BYTES or info.is_dir():
                    raise UpdateError(f'プラグインファイルが不正です: {member}')
                # zipにはsymlinkも入れられるため明示的に弾く。
                if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                    raise UpdateError('シンボリックリンクを含むZIPには対応しません。')
                content = archive.read(member)
                if hashlib.sha256(content).hexdigest() != expected_hash:
                    raise UpdateError(f'ファイル検証に失敗しました: {filename}')
                try:
                    compile(content, filename, 'exec')
                except (SyntaxError, ValueError) as exc:
                    raise UpdateError(f'Pythonファイルが不正です: {filename}') from exc
                result[filename] = content
            if _plugin_version(result['__init__.py']) != expected_version:
                raise UpdateError('更新内容のバージョンがReleaseと一致しません。')
            return result
    except (BadZipFile, EOFError, UnicodeError, ValueError, KeyError) as exc:
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError(f'ZIPの検証に失敗しました: {exc}') from exc


def install_files(plugin_dir: Path, new_files: dict[str, bytes], current_version: str,
                  new_version: str, backup_root: Path | None = None) -> Path:
    """既存ファイルを退避して置換。失敗時は変更済みファイルも復元。"""
    if version_tuple(new_version) <= version_tuple(current_version):
        raise UpdateError('最新版ではないため、更新を中止しました。')
    plugin_dir = Path(plugin_dir).resolve()
    if not (plugin_dir / '__init__.py').is_file():
        raise UpdateError('KiCadプラグインの配置先が見つかりません。')
    if not new_files or not all(MODULE_RE.fullmatch(n) for n in new_files):
        raise UpdateError('更新するファイルの形式が不正です。')
    base = backup_root or app_directory() / 'backups'
    base.mkdir(parents=True, exist_ok=True)
    existing = {name: (plugin_dir / name).read_bytes() if (plugin_dir / name).is_file() else None
                for name in new_files}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    # レース条件が発生しないよう独立したバックアップフォルダを生成する。
    backup_path = Path(tempfile.mkdtemp(prefix=stamp + '-online-', dir=base))
    try:
        for name, data in existing.items():
            if data is not None:
                (backup_path / name).write_bytes(data)
        (backup_path / 'metadata.json').write_text(json.dumps({
            'mode': 'online', 'previous_version': current_version,
            'new_version': new_version, 'target': str(plugin_dir),
            'old_files': [n for n, value in existing.items() if value is not None],
            'new_files': sorted(new_files),
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        with tempfile.TemporaryDirectory(prefix='.smart-update-', dir=plugin_dir) as staging:
            staged = Path(staging)
            for name, data in new_files.items():
                (staged / name).write_bytes(data)
            changed = []
            try:
                for name in sorted(new_files):
                    os.replace(staged / name, plugin_dir / name)
                    changed.append(name)
            except Exception:
                for name in reversed(changed):
                    previous = existing[name]
                    if previous is None:
                        (plugin_dir / name).unlink(missing_ok=True)
                    else:
                        # 元の内容を復元。バックアップ本体は残す。
                        with tempfile.NamedTemporaryFile(dir=plugin_dir, delete=False) as restore:
                            restore.write(previous)
                            restore_path = restore.name
                        os.replace(restore_path, plugin_dir / name)
                raise
        return backup_path
    except (OSError, PermissionError) as exc:
        raise UpdateError(f'プラグインの更新に失敗しました。ファイル権限・空き容量をご確認ください。\n{exc}') from exc


def perform_update(plugin_dir: Path, installed_version: str, release: dict) -> Path:
    if not release.get('available'):
        raise UpdateError('利用可能な更新がありません。')
    size = release.get('size', 0)
    if not isinstance(size, int) or size > MAX_ASSET_BYTES or size < 1:
        raise UpdateError('Release ZIPのサイズ情報が不正です。')
    data = _get_url(release['asset_url'], MAX_ASSET_BYTES,
                    accept='application/octet-stream')
    if len(data) != size:
        raise UpdateError('ZIPのダウンロードサイズが一致しません。')
    _verify_checksum(data, release)
    files = verify_archive(data, release['latest'])
    return install_files(plugin_dir, files, installed_version, release['latest'])
