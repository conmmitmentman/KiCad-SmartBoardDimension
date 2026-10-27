"""Static patch-generator tests; do NOT test KiCad's C++ runtime."""
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'native_patch'))
from apply_native_patch import patch_pair, main


class PatcherTest(unittest.TestCase):
    def setUp(self):
        self.header = 'begin\n    PCB_DIMENSION_BASE* m_previewDimension;\nend\n'
        self.cpp = (
            '#include "dialog_dimension_properties.h"\n'
            '    SetupStandardButtons();\n'
            'bool DIALOG_DIMENSION_PROPERTIES::TransferDataFromWindow() {\n'
            '    BOARD_COMMIT commit( m_frame );\n'
            '    updateDimensionFromDialog( m_dimension );\n}\n'
        )
        self.selection = ('#include <pcb_base_edit_frame.h>\n'
                          '                        m_previousFirstCell = singleSelectedCell();\n'
                          '    if( aClientFilter )\n        aClientFilter( aWhere, collector, this );\n')

    def test_only_intended_anchors_changed(self):
        a, b = patch_pair(self.header, self.cpp)
        self.assertIn('wxCheckBox* m_cbDriveOutline', a)
        self.assertIn('SMART_BOARD_NATIVE::resizeOutline', b)
        self.assertIn(r'\u3053', b)
        self.assertIn('SetupStandardButtons();', b)
        self.assertIn('updateDimensionFromDialog( m_dimension );', b)

    def test_rejects_double_patch(self):
        a, b = patch_pair(self.header, self.cpp)
        with self.assertRaisesRegex(RuntimeError, 'Already modified'):
            patch_pair(a, b)

    def test_rejects_upstream_mismatch(self):
        with self.assertRaisesRegex(RuntimeError, 'Expected one occurrence'):
            patch_pair(self.header, 'not a KiCad file')

    def test_apply_and_backups(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_dir = base / 'pcbnew' / 'dialogs'
            source_dir.mkdir(parents=True)
            h = source_dir / 'dialog_dimension_properties.h'
            c = source_dir / 'dialog_dimension_properties.cpp'
            h.write_text(self.header)
            c.write_text(self.cpp)
            selection = base / 'pcbnew/tools/pcb_selection_tool.cpp'
            selection.parent.mkdir()
            selection.write_text(self.selection)
            old = sys.argv
            try:
                sys.argv = ['apply_native_patch.py', str(base)]
                main()
            finally:
                sys.argv = old
            self.assertEqual(h.with_suffix('.h.smartboard-original').read_text(), self.header)
            self.assertEqual(c.with_suffix('.cpp.smartboard-original').read_text(), self.cpp)
            self.assertTrue((source_dir / 'smart_board_driving_dimension_impl.h').is_file())
            self.assertTrue((source_dir / 'smart_board_driving_dimension_ui.h').is_file())
            self.assertIn('editOnCanvas', selection.read_text())
            self.assertIn('drivingText', selection.read_text())
            self.assertTrue((source_dir / 'smart_board_driving_circle.h').is_file())

    def test_missing_selection_anchor_leaves_sources_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            directory = base / 'pcbnew/dialogs'
            directory.mkdir(parents=True)
            header = directory / 'dialog_dimension_properties.h'
            source = directory / 'dialog_dimension_properties.cpp'
            header.write_text(self.header)
            source.write_text(self.cpp)
            selection = base / 'pcbnew/tools/pcb_selection_tool.cpp'
            selection.parent.mkdir()
            selection.write_text('#include <pcb_base_edit_frame.h>\n')
            before = {f: f.read_bytes() for f in (header, source, selection)}
            with patch.object(sys, 'argv', ['patch', str(base)]):
                with self.assertRaisesRegex(RuntimeError, 'Expected one occurrence'):
                    main()
            self.assertEqual(before, {f: f.read_bytes() for f in before})
            self.assertEqual(set(base.rglob('*.smartboard-original')), set())
            self.assertFalse((directory / 'smart_board_driving_dimension_impl.h').exists())

    def test_write_failure_restores_all_original_sources(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            directory = base / 'pcbnew/dialogs'
            directory.mkdir(parents=True)
            header = directory / 'dialog_dimension_properties.h'
            source = directory / 'dialog_dimension_properties.cpp'
            header.write_text(self.header)
            source.write_text(self.cpp)
            selection = base / 'pcbnew/tools/pcb_selection_tool.cpp'
            selection.parent.mkdir()
            selection.write_text(self.selection)
            before = {f: f.read_bytes() for f in (header, source, selection)}
            original_write = Path.write_text
            def fail_ui_write(path, *args, **kwargs):
                if path.name == 'smart_board_driving_dimension_ui.h':
                    raise OSError('simulated write failure')
                return original_write(path, *args, **kwargs)
            with patch.object(sys, 'argv', ['patch', str(base)]), patch.object(Path, 'write_text', fail_ui_write):
                with self.assertRaisesRegex(OSError, 'simulated write failure'):
                    main()
            self.assertEqual(before, {f: f.read_bytes() for f in before})
            self.assertFalse((directory / 'smart_board_driving_dimension_impl.h').exists())
            self.assertFalse((directory / 'smart_board_driving_dimension_ui.h').exists())


if __name__ == '__main__':
    unittest.main()
