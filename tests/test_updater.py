# -*- coding: utf-8 -*-
"""GitHubへの実通信なしで更新処理を検証する。"""
import hashlib
import io
import json
from pathlib import Path
import tempfile
from unittest import mock
from zipfile import ZipFile
import unittest

import importlib.util

# pcbnew/wxがなくても updater.py だけを読み込めるようにする。
spec = importlib.util.spec_from_file_location(
    'smart_board_update_unit', Path(__file__).resolve().parents[1] /
    'smart_board_dimension/updater.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)
from tools import build_release


class UpdaterTests(unittest.TestCase):
    def test_missing_release_is_explained(self):
        from urllib.error import HTTPError
        with mock.patch.object(updater.request, 'urlopen',
                               side_effect=HTTPError('https://api.github.com', 404, 'Not Found', {}, None)):
            with self.assertRaisesRegex(updater.UpdateError, '正式Release'):
                updater.check_latest('author/repo', '1.3.0')

    def test_bom_settings_and_invalid_structure(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict('os.environ', {'LOCALAPPDATA': folder}):
            directory = Path(folder) / 'SmartBoardDimension'
            directory.mkdir()
            path = directory / 'settings.json'
            path.write_text('{"repository":"author/repo"}', encoding='utf-8-sig')
            self.assertEqual(updater.get_repository(), 'author/repo')
            for bad in ('[]', '{"repository":123}'):
                path.write_text(bad, encoding='utf-8')
                with self.assertRaises(updater.UpdateError):
                    updater.get_repository()

    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as folder:
            cls.package_bytes = build_release.build(Path(folder)).read_bytes()
        with ZipFile(io.BytesIO(cls.package_bytes)) as archive:
            cls.manifest = json.loads(archive.read('update_manifest.json'))

    def test_repository_validation(self):
        self.assertEqual(updater.parse_repository('https://github.com/example/KiCad-plugin.git'),
                         'example/KiCad-plugin')
        for invalid in ('', 'example', 'https://example.com/owner/repo',
                        'example/repo/../../hello', 'a/b?x=1', 'a/../b'):
            with self.subTest(invalid=invalid), self.assertRaises(updater.UpdateError):
                updater.parse_repository(invalid)

    def test_version_comparison(self):
        self.assertLess(updater.version_tuple('1.3.0'), updater.version_tuple('v1.12.0'))
        with self.assertRaises(updater.UpdateError):
            updater.version_tuple('1.3.0rc1')

    def test_user_setting_round_trip(self):
        with tempfile.TemporaryDirectory() as folder, \
             mock.patch.dict('os.environ', {'LOCALAPPDATA': folder}):
            updater.save_repository('https://github.com/author/board')
            self.assertEqual(updater.get_repository(), 'author/board')
            stored = Path(folder) / 'SmartBoardDimension/settings.json'
            self.assertTrue(stored.is_file())

    def _release_info(self):
        size = len(self.package_bytes)
        payload = {
            'tag_name': 'v1.3.0', 'draft': False, 'prerelease': False,
            'assets': [{
                'name': 'KiCad10_SmartBoardDimension_v1.3.0_Windows.zip',
                'state': 'uploaded', 'size': size,
                'browser_download_url': 'https://github.com/author/repo/releases/download/v1.3.0/KiCad10_SmartBoardDimension_v1.3.0_Windows.zip',
                'digest': 'sha256:' + hashlib.sha256(self.package_bytes).hexdigest(),
            }],
        }
        with mock.patch.object(updater, '_get_url', return_value=json.dumps(payload).encode()):
            info = updater.check_latest('author/repo', '1.1.0')
            self.assertTrue(info['available'])
            self.assertEqual(info['latest'], '1.3.0')
            self.assertEqual(info['size'], size)
            self.assertFalse(updater.check_latest('author/repo', '1.3.0')['available'])
        return info

    def test_release_check_found(self):
        self.assertTrue(self._release_info()['available'])

    def test_install_into_mock_plugin_folder(self):
        result = self._release_info()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            installed = root / 'plugins/smart_board_dimension'
            installed.mkdir(parents=True)
            (installed / '__init__.py').write_text("PLUGIN_VERSION = '1.1.0'\n", encoding='utf-8')
            (installed / 'geometry.py').write_text('# old geometry\n', encoding='utf-8')
            def fake_url(url, *_args, **_kwargs):
                self.assertEqual(url, result['asset_url'])
                return self.package_bytes
            with mock.patch.object(updater, '_get_url', side_effect=fake_url), \
                 mock.patch.object(updater, 'app_directory', return_value=root / 'local'):
                backup = updater.perform_update(installed, '1.1.0', result)
            self.assertIn("PLUGIN_VERSION = '1.3.0'", (installed / '__init__.py').read_text(encoding='utf-8'))
            self.assertTrue((installed / 'updater.py').is_file())
            self.assertEqual((backup / '__init__.py').read_text(encoding='utf-8'), "PLUGIN_VERSION = '1.1.0'\n")
            self.assertFalse((backup / 'updater.py').exists())
            self.assertEqual(json.loads((backup / 'metadata.json').read_text(encoding='utf-8'))['previous_version'], '1.1.0')

    def test_reject_corrupt_hash_before_writing(self):
        valid = self._release_info()
        valid['digest'] = 'a' * 64
        with mock.patch.object(updater, '_get_url', return_value=self.package_bytes):
            with self.assertRaisesRegex(updater.UpdateError, 'SHA256'):
                updater.perform_update(Path('/unused'), '1.1.0', valid)

    def test_manifest_verify_and_tamper(self):
        files = updater.verify_archive(self.package_bytes, '1.3.0')
        self.assertEqual(set(files), {'__init__.py', 'geometry.py', 'updater.py', 'canvas.py', 'direct_editor.py'})
        with self.assertRaisesRegex(updater.UpdateError, 'バージョン'):
            updater.verify_archive(self.package_bytes, '9.9.9')
        modified = io.BytesIO()
        with ZipFile(io.BytesIO(self.package_bytes)) as source, ZipFile(modified, 'w') as dest:
            for name in source.namelist():
                data = source.read(name)
                if name == 'smart_board_dimension/geometry.py':
                    data += b'\n# changed\n'
                dest.writestr(name, data)
        with self.assertRaisesRegex(updater.UpdateError, '検証'):
            updater.verify_archive(modified.getvalue(), '1.3.0')

    def test_reject_bad_module_name_even_with_valid_manifest(self):
        manifest = dict(self.manifest)
        manifest['files'] = dict(manifest['files'])
        manifest['files']['../../malware.py'] = 'a'*64
        edited = io.BytesIO()
        with ZipFile(io.BytesIO(self.package_bytes)) as source, ZipFile(edited, 'w') as dest:
            for name in source.namelist():
                data = (json.dumps(manifest).encode() if name == 'update_manifest.json'
                        else source.read(name))
                dest.writestr(name, data)
        with self.assertRaisesRegex(updater.UpdateError, 'ファイル名'):
            updater.verify_archive(edited.getvalue(), '1.3.0')

    def test_install_rolls_back_if_file_replacement_fails(self):
        files = updater.verify_archive(self.package_bytes, '1.3.0')
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            plugin = parent / 'smart_board_dimension'
            plugin.mkdir()
            old = {'__init__.py': b"PLUGIN_VERSION='1.1.0'\n", 'geometry.py': b'# previous\n'}
            for name, source in old.items():
                (plugin/name).write_bytes(source)
            real_replace = updater.os.replace
            blocked = [False]
            def fail_once(src, dst):
                if str(dst).endswith('geometry.py') and '.smart-update-' in str(src) and not blocked[0]:
                    blocked[0] = True
                    raise PermissionError('simulated file lock')
                return real_replace(src, dst)
            with mock.patch.object(updater.os, 'replace', side_effect=fail_once):
                with self.assertRaisesRegex(updater.UpdateError, '失敗'):
                    updater.install_files(plugin, files, '1.1.0', '1.3.0', parent/'backups')
            for name, source in old.items():
                self.assertEqual((plugin/name).read_bytes(), source)
            self.assertFalse((plugin/'updater.py').exists())

    def test_no_downgrade(self):
        with self.assertRaisesRegex(updater.UpdateError, '最新版ではない'):
            updater.install_files(Path('/unused'), {'updater.py': b''}, '2.0.0', '1.3.0')


if __name__ == '__main__':
    unittest.main()
