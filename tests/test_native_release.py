"""Check the native source distribution and its separation from the plugin updater."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_native_release as package
import publish_native_release as publish


class NativeReleaseTests(unittest.TestCase):
    def test_archive_contains_current_payload_and_licenses(self):
        with tempfile.TemporaryDirectory() as td:
            archive = package.build(Path(td))
            with ZipFile(archive) as z:
                self.assertIsNone(z.testzip())
                self.assertEqual(set(z.namelist()), {'START_HERE.txt', 'ATTRIBUTION.md', 'LICENSE'}
                                 | {'native/' + name for name in package.FILES})
                for name in package.FILES:
                    self.assertEqual(z.read('native/' + name), (package.ROOT / 'native' / name).read_bytes())
                self.assertIn(b'not an installer', z.read('START_HERE.txt'))
            self.assertEqual(archive.with_suffix('.zip.sha256').read_text('ascii'),
                             hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')

    def test_formal_source_release_does_not_replace_python_latest(self):
        with tempfile.TemporaryDirectory() as td, patch.object(publish, 'ROOT', Path(td)), \
                patch.dict('os.environ', {'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_SHA': 'a' * 40}), \
                patch.object(publish.subprocess, 'run') as run:
            run.side_effect = [subprocess.CompletedProcess([], 1, '', 'HTTP 404'),
                               subprocess.CompletedProcess([], 0)]
            publish.main()
            args = run.call_args_list[-1].args[0]
            self.assertEqual(args[:4], ['gh', 'release', 'create', package.TAG])
            self.assertNotIn('--prerelease', args)
            self.assertIn('--latest=false', args)
            self.assertEqual(args[args.index('--target') + 1], 'a' * 40)


if __name__ == '__main__':
    unittest.main()
