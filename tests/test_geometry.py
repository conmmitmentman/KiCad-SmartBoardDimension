# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'smart_board_dimension'))
from geometry import (Bounds, DimensionError, detect_four_line_rectangle,
                      fmt_iu, mm_to_iu, map_corner, parse_mm, place_rectangle)


class TestSmartDimensions(unittest.TestCase):
    def test_expressions(self):
        self.assertEqual(parse_mm('2 * 15 + 5'), 35)
        self.assertEqual(parse_mm('1in + 5mm'), parse_mm('30.4'))
        self.assertEqual(parse_mm('2.54cm'), parse_mm('25.4'))
        self.assertEqual(parse_mm('100mil'), parse_mm('2.54'))
        self.assertEqual(parse_mm('（２０＋５）'), 25)
        self.assertEqual(mm_to_iu('0.001'), 1000)
        self.assertEqual(fmt_iu(25400000), '25.4')

    def test_expressions_reject_unsafe_code(self):
        for source in ('__import__("os")', '2**5', 'a+10', '1/0', '3//2'):
            with self.subTest(source=source), self.assertRaises(DimensionError):
                parse_mm(source)

    def test_detect_segments_any_direction(self):
        l, t, r, b = 100, 200, 301, 401
        lines = [((r,t),(l,t)), ((r,b),(r,t)), ((l,b),(r,b)), ((l,t),(l,b))]
        self.assertEqual(detect_four_line_rectangle(lines), Bounds(l,t,r,b))

    def test_reject_gap_and_duplicates(self):
        lines = [((0,0),(10,0)), ((10,0),(10,10)),
                 ((10,10),(0,10)), ((0,10),(0,1))]
        with self.assertRaises(DimensionError):
            detect_four_line_rectangle(lines)
        with self.assertRaises(DimensionError):
            detect_four_line_rectangle([lines[0]] * 4)

    def test_anchors_and_corner_mapping(self):
        b = Bounds(100, 200, 300, 400)
        new = place_rectangle(100, 200, 500, 350, 0)
        self.assertEqual(new, Bounds(100, 200, 600, 550))
        self.assertEqual(map_corner(b, new, (300, 400)), (600,550))
        self.assertEqual(place_rectangle(200, 300, 500, 350, 1),
                         Bounds(-50,125,450,475))
        self.assertEqual(place_rectangle(300, 400, 500, 350, 2),
                         Bounds(-200,50,300,400))

if __name__ == '__main__':
    unittest.main()
