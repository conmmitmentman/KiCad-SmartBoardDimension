# -*- coding: utf-8 -*-
"""KiCad 10 SWIG APIを模したスタブによるロジック結合試験（GUI実機試験ではない）。"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

SRC_DIR = Path(__file__).resolve().parents[1] / 'smart_board_dimension'


class Point:
    def __init__(self, x, y):
        self.x, self.y = int(x), int(y)


class Shape:
    def __init__(self, board=None, shape=1):
        self.shape = shape
        self.start = Point(0, 0)
        self.end = Point(0, 0)
        self.layer = 44
        self.corner_radius = 0
        self.board = board

    def GetLayer(self): return self.layer
    def SetLayer(self, layer): self.layer = layer
    def GetShape(self): return self.shape
    def SetShape(self, shape): self.shape = shape
    def GetStart(self): return self.start
    def GetEnd(self): return self.end
    def SetStart(self, point): self.start = point
    def SetEnd(self, point): self.end = point
    def GetCornerRadius(self): return self.corner_radius
    def SetWidth(self, _width): pass
    def SetFilled(self, _flag): pass

    def GetCorners(self):
        return [Point(self.start.x, self.start.y), Point(self.end.x, self.start.y),
                Point(self.end.x, self.end.y), Point(self.start.x, self.end.y)]


class Board:
    def __init__(self, drawings=None): self.drawings = drawings or []
    def GetDrawings(self): return self.drawings
    def Add(self, item): self.drawings.append(item)


def load_with_mocked_kicad():
    pcbnew = types.ModuleType('pcbnew')
    pcbnew.PCB_SHAPE = Shape
    pcbnew.SHAPE_T_RECTANGLE = 2
    pcbnew.SHAPE_T_RECT = 2
    pcbnew.SHAPE_T_SEGMENT = 1
    pcbnew.Edge_Cuts = 44
    pcbnew.FromMM = lambda v: int(v * 1000000)
    pcbnew.VECTOR2I = Point
    pcbnew.Refresh = lambda: None
    class ActionPlugin:
        def register(self): self.defaults()
    pcbnew.ActionPlugin = ActionPlugin
    wx = types.ModuleType('wx')
    wx.Dialog = object
    sys.modules['pcbnew'] = pcbnew
    sys.modules['wx'] = wx
    spec = importlib.util.spec_from_file_location(
        'smart_board_dimension', SRC_DIR / '__init__.py',
        submodule_search_locations=[str(SRC_DIR)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules['smart_board_dimension'] = mod
    spec.loader.exec_module(mod)
    return mod


mod = load_with_mocked_kicad()
from smart_board_dimension.geometry import Bounds, DimensionError


class IntegrationTests(unittest.TestCase):
    def test_new_outline(self):
        board = Board()
        mode, shapes, before = mod._outline_info(board)
        self.assertEqual(mode, 'new')
        new = Bounds(500, 500, 50000500, 30000500)
        mod._apply(board, mode, shapes, before, new)
        self.assertEqual(len(board.drawings), 1)
        self.assertEqual((board.drawings[0].GetEnd().x, board.drawings[0].GetEnd().y),
                         (new.right, new.bottom))

    def test_one_rectangle_edit(self):
        shape = Shape(shape=2)
        shape.SetStart(Point(10,20)); shape.SetEnd(Point(40,50))
        board = Board([shape])
        mode, shapes, old = mod._outline_info(board)
        self.assertEqual(mode,'shape')
        new = Bounds(10, 20, 90, 110)
        mod._apply(board, mode, shapes, old, new)
        self.assertEqual((shape.GetStart().x,shape.GetEnd().x), (10,90))

    def test_four_lines_edit_keep_orientation(self):
        pts = [((30,10),(10,10)),((30,40),(30,10)),((10,40),(30,40)),((10,10),(10,40))]
        shapes = []
        for a,b in pts:
            s = Shape(shape=1)
            s.SetStart(Point(*a)); s.SetEnd(Point(*b))
            shapes.append(s)
        board = Board(shapes)
        mode, shape_list, before = mod._outline_info(board)
        self.assertEqual(mode,'lines')
        self.assertEqual(before, Bounds(10,10,30,40))
        new = Bounds(10,10,110,200)
        mod._apply(board, mode, shape_list, before, new)
        self.assertEqual((shapes[0].GetStart().x, shapes[0].GetEnd().x), (110,10))
        self.assertEqual((shapes[1].GetStart().y, shapes[1].GetEnd().y), (200,10))

    def test_reject_complex_outline(self):
        s = Shape(shape=2)
        s.SetStart(Point(10,10)); s.SetEnd(Point(20,20))
        s.corner_radius = 5
        with self.assertRaises(DimensionError):
            mod._outline_info(Board([s]))
        with self.assertRaises(DimensionError):
            mod._outline_info(Board([s, Shape(shape=1)]))

if __name__ == '__main__': unittest.main()
