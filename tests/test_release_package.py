# -*- coding: utf-8 -*-
"""KiCad GUI不要のGitHub配布物テスト。"""
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseBuildTests(unittest.TestCase):
    def test_release_contains_installer_and_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            subprocess.run(
                [sys.executable, str(ROOT / 'tools/build_release.py'),
                 '--output-dir', temporary],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            files = list(Path(temporary).glob('*.zip'))
            self.assertEqual(len(files), 1)
            with ZipFile(files[0]) as archive:
                names = archive.namelist()
                for name in ('smart_board_dimension/__init__.py',
                             'smart_board_dimension/geometry.py',
                             'smart_board_dimension/updater.py',
                             'smart_board_dimension/canvas.py',
                             'smart_board_dimension/direct_editor.py',
                             'update_manifest.json',
                             'scripts/installer.ps1', 'Windows_更新.bat',
                             'Windows_前の版に戻す.bat', 'README.md'):
                    self.assertIn(name, names)
                self.assertIsNone(archive.testzip())
                self.assertIn(b"PLUGIN_VERSION = '1.3.0'",
                              archive.read('smart_board_dimension/__init__.py'))

    def test_powershell_script_is_utf8_bom(self):
        raw = (ROOT / 'scripts/installer.ps1').read_bytes()
        self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
        text = raw.decode('utf-8-sig')
        self.assertIn("[ValidateSet('Install', 'Update', 'Rollback')]", text)
        self.assertIn('Create-Backup', text)
        self.assertIn('Restore-Files', text)


if __name__ == '__main__':
    unittest.main()
