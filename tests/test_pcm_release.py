import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from tools.build_pcm_release import build
from tools.build_release import REPOSITORY, RELEASE_FILES, read_plugin_version


class PcmTests(unittest.TestCase):
    def test_pcm_payload_matches_sources_and_stays_inside_plugins(self):
        with tempfile.TemporaryDirectory() as folder:
            path = build(Path(folder))
            with ZipFile(path) as z:
                meta = json.loads(z.read('metadata.json'))
                self.assertEqual(meta['type'], 'plugin')
                self.assertEqual(meta['versions'][0]['version'], read_plugin_version())
                self.assertEqual(meta['versions'][0]['status'], 'testing')
                self.assertEqual(meta['versions'][0]['runtime'], 'swig')
                self.assertFalse(any(k.startswith('download_') for k in meta['versions'][0]))
                self.assertIsNone(z.testzip())
                for f in RELEASE_FILES:
                    if f.startswith('smart_board_dimension/') and f.endswith('.py'):
                        self.assertEqual(z.read('plugins/'+Path(f).name), (REPOSITORY/f).read_bytes())
                self.assertIn('plugins/pcm-managed.txt', z.namelist())
                self.assertTrue(all(n=='metadata.json' or n.startswith('plugins/') for n in z.namelist()))

    def test_release_stays_prerelease_until_gui_validation(self):
        code = (REPOSITORY/'tools/publish_release.py').read_text('utf-8')
        self.assertIn("'--prerelease'", code)
        self.assertIn("'--latest=false'", code)
