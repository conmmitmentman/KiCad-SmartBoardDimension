"""Run real pcbnew/wx checks with KiCad's Python, outside the PCB editor.

Only plugin registration and Refresh are suppressed; board geometry is real.
Run separately from the mock suite, which replaces pcbnew in sys.modules.
"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pcbnew
import wx

with patch.object(pcbnew.ActionPlugin, 'register'):
    import smart_board_dimension as plugin
from smart_board_dimension import direct_editor


class KiCadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App(False)

    def apply(self, board, after):
        mode, shapes, before = plugin._outline_info(board)
        with patch.object(pcbnew, 'Refresh'):
            plugin._apply(board, mode, shapes, before, after)
        self.assertEqual(plugin._outline_info(board)[2], after)

    def test_create_resize_save_reload(self):
        board = pcbnew.BOARD()
        self.apply(board, plugin.Bounds(100000000, 100000000, 160000000, 145000000))
        self.apply(board, plugin.Bounds(100000000, 100000000, 170000000, 150000000))
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'board.kicad_pcb')
            self.assertTrue(pcbnew.SaveBoard(path, board))
            loaded = pcbnew.LoadBoard(path)
            self.assertEqual(plugin._outline_info(loaded)[2], plugin._outline_info(board)[2])

    def test_native_dimensions_resize_and_persistence(self):
        board = pcbnew.BOARD()
        before = plugin.Bounds(100000000, 100000000, 170000000, 145000000)
        self.apply(board, before)
        dimensions = direct_editor.sync_dimensions(board, before)
        ids = [dimensions[i].m_Uuid.AsString() for i in (0, 1)]
        self.assertEqual([dimensions[i].GetMeasuredValue() for i in (0, 1)], [70000000, 45000000])
        after = direct_editor.resize_bounds(before, 0, '2*40', 1)
        self.assertEqual(after.anchor(1), before.anchor(1))
        self.apply(board, after)
        updated = direct_editor.sync_dimensions(board, after)
        self.assertEqual([updated[i].m_Uuid.AsString() for i in (0, 1)], ids)
        self.assertEqual(updated[0].GetMeasuredValue(), 80000000)
        self.assertEqual(len(list(board.GetDrawings())), 3)
        self.assertFalse(updated[0].GetOverrideTextEnabled())
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'direct.kicad_pcb')
            pcbnew.SaveBoard(path, board)
            loaded = pcbnew.LoadBoard(path)
            saved = direct_editor.find_dimensions(loaded)
            self.assertEqual([saved[i].m_Uuid.AsString() for i in (0, 1)], ids)
            self.assertEqual(plugin._outline_info(loaded)[2], after)

    def test_native_dimensions_reject_invalid_requests(self):
        before = plugin.Bounds(1950000000, 0, 1990000000, 30000000)
        for text in ('0', '-1', '1/0', '10000', '100'):
            with self.subTest(text=text), self.assertRaises(plugin.DimensionError):
                direct_editor.resize_bounds(before, 0, text, 0)
        board = pcbnew.BOARD()
        first = direct_editor.sync_dimensions(board, before)
        duplicate = pcbnew.PCB_DIM_ALIGNED(board)
        duplicate.SetPrefix(direct_editor.PREFIXES[0])
        duplicate.SetLayer(pcbnew.Dwgs_User)
        board.Add(duplicate)
        with self.assertRaises(plugin.DimensionError):
            direct_editor.sync_dimensions(board, before)

    def test_four_lines_and_anchors(self):
        board = pcbnew.BOARD()
        corners = [(100, 100), (150, 100), (150, 130), (100, 130)]
        for start, end in zip(corners, corners[1:] + corners[:1]):
            line = pcbnew.PCB_SHAPE(board)
            line.SetShape(pcbnew.SHAPE_T_SEGMENT)
            line.SetLayer(pcbnew.Edge_Cuts)
            line.SetWidth(pcbnew.FromMM(0.05))
            line.SetStart(pcbnew.VECTOR2I_MM(*end))
            line.SetEnd(pcbnew.VECTOR2I_MM(*start))
            board.Add(line)
        for anchor in (0, 1, 2):
            before = plugin._outline_info(board)[2]
            after = plugin.place_rectangle(*before.anchor(anchor), 60000000, 45000000, anchor)
            self.apply(board, after)

    def test_dialog_size_and_expression_validation(self):
        dialog = plugin.SmartDimensionDialog(plugin.Bounds(100000000, 100000000, 150000000, 130000000), 'new')
        try:
            dialog.Layout()
            body = dialog.w.GetParent()
            self.assertGreaterEqual(body.GetSize().height, body.GetBestSize().height)
            self.assertGreaterEqual(dialog.preview.GetSize().height, dialog.preview.GetBestSize().height)
            dialog.w.SetValue('2*30')
            dialog.h.SetValue('1in+19.6mm')
            self.assertEqual(dialog._read(), plugin.Bounds(100000000, 100000000, 160000000, 145000000))
            dialog.x.SetValue('1990')
            with self.assertRaises(plugin.DimensionError):
                dialog._read()
            dialog.w.SetValue('10000')
            with self.assertRaises(plugin.DimensionError):
                dialog._read()
        finally:
            dialog.Destroy()

    def test_visual_editor_anchor_drag_reset_and_invalid_input(self):
        before = plugin.Bounds(100000000, 100000000, 150000000, 130000000)
        dialog = plugin.SmartDimensionDialog(before, 'shape')
        try:
            dialog.Show()
            wx.Yield()
            dialog.w.SetValue('2*35')
            resized = dialog._read()
            dialog._select_anchor(1)
            self.assertEqual(dialog._read(), resized)
            center = resized.anchor(1)
            dialog._drag_dimension(0, 80000000)
            self.assertEqual(dialog._read().anchor(1), center)
            dialog._select_anchor(2)
            fixed = dialog._read().anchor(2)
            dialog._drag_dimension(1, 45000000)
            self.assertEqual(dialog._read().anchor(2), fixed)
            dialog.w.SetValue('1/0')
            self.assertFalse(dialog.FindWindowById(wx.ID_OK).IsEnabled())
            self.assertFalse(dialog.canvas.valid)
            dialog._select_anchor(0)
            self.assertEqual(dialog.anchor_kind, 2)
            dialog._reset()
            self.assertEqual(dialog._read(), before)
            self.assertTrue(dialog.FindWindowById(wx.ID_OK).IsEnabled())
            # All entry boxes stay inside the canvas after extreme aspect ratios.
            for width, height in [('0.01', '1900'), ('1900', '0.01')]:
                dialog._select_anchor(0)
                dialog.x.SetValue('0')
                dialog.y.SetValue('0')
                dialog.w.SetValue(width)
                dialog.h.SetValue(height)
                dialog.canvas._layout_geometry()
                for control in (dialog.w, dialog.h):
                    self.assertTrue(dialog.canvas.GetClientRect().Contains(control.GetRect()))
            # Cancelling a drag restores the original expression, not only its value.
            dialog._reset()
            dialog.w.SetValue('2*25')
            canvas = dialog.canvas
            canvas.drag = (0, wx.Point(0, 0), dialog._read(), '2*25', '30')
            dialog._drag_dimension(0, 65000000)
            canvas.finish_drag(cancel=True)
            self.assertEqual(dialog.w.GetValue(), '2*25')
            self.assertEqual(dialog._read(), before)
        finally:
            dialog.Destroy()


if __name__ == '__main__':
    print('KiCad', pcbnew.GetBuildVersion(), 'wx', wx.version())
    unittest.main(verbosity=2)
