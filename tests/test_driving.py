"""No KiCad installation, board files, or GUI are accessed by these tests."""
import unittest
from test_plugin_mock import mod, Shape, Point, Board
from smart_board_dimension import driving as d


class Dimension(Shape):
    def __init__(self, start, end):
        super().__init__()
        self.layer = 40
        self.SetStart(Point(*start)); self.SetEnd(Point(*end))
    def Update(self): pass


class Aligned(Dimension): pass
class Radial(Dimension): pass
class Orthogonal(Dimension): pass
mod.pcbnew.PCB_DIM_ALIGNED = Aligned
mod.pcbnew.PCB_DIM_RADIAL = Radial
mod.pcbnew.PCB_DIM_ORTHOGONAL = Orthogonal


class DrivingTests(unittest.TestCase):
    def circle(self):
        c = Shape(shape=4)
        c.SetStart(Point(100300000, 100400000)); c.SetEnd(Point(128300000, 100400000))
        r = Radial((100300000,100400000), (128300000,100400000))
        diameter = Aligned((72300000,100400000), (128300000,100400000))
        return Board([c,r,diameter]), c, r, diameter

    def test_radius_expression_updates_circle_and_diameter(self):
        b,c,r,diameter = self.circle()
        d.apply_resize(b,r,'2*15')
        self.assertEqual(d.point(c.GetStart()), (100300000,100400000))
        self.assertEqual(d.point(c.GetEnd()), (130300000,100400000))
        self.assertEqual(d.point(r.GetEnd()), d.point(c.GetEnd()))
        self.assertEqual(d.point(diameter.GetStart()), (70300000,100400000))

    def test_diameter_and_units(self):
        b,c,r,diameter = self.circle()
        d.apply_resize(b,diameter,'1in+4.6mm')
        self.assertEqual(d.point(c.GetEnd()), (115300000,100400000))

    def test_minimum_diameter_remains_editable(self):
        b,c,r,diameter = self.circle()
        d.apply_resize(b,diameter,'0.01')
        d.apply_resize(b,diameter,'2')
        self.assertEqual(d.point(c.GetEnd()), (101300000,100400000))

    def test_unconnected_dimensions_preserved(self):
        b,c,r,_ = self.circle()
        separate = Aligned((1,2),(3,4)); b.Add(separate)
        d.apply_resize(b,r,'20')
        self.assertEqual(d.point(separate.GetEnd()), (3,4))

    def test_lock_preflight_prevents_partial_edits(self):
        for lock_index in (0,1,2):
            b,c,r,diameter = self.circle()
            b.drawings[lock_index].locked = True
            with self.assertRaises(d.DimensionError): d.apply_resize(b,r,'30')
            self.assertEqual(d.point(c.GetEnd()), (128300000,100400000))
            self.assertEqual(d.point(r.GetEnd()), (128300000,100400000))

    def test_bad_values_leave_circle_unchanged(self):
        for value in ('1/0','0','-1','1001','__import__("os")'):
            b,c,r,_ = self.circle()
            with self.assertRaises(d.DimensionError): d.apply_resize(b,r,value)
            self.assertEqual(d.point(c.GetEnd()), (128300000,100400000))

    def test_chord_and_unattached_radius_rejected(self):
        b,c,r,_ = self.circle()
        _, circle = d.outline(b)
        self.assertIsNone(d.classify(circle, Aligned((100300000,72400000),(128300000,100400000))))
        self.assertIsNone(d.classify(circle, Radial((1,2),(128300000,100400000))))

    def test_projected_diagonal_is_not_diameter(self):
        circle = d.Circle((0,0),(3000000,4000000))
        self.assertIsNone(d.classify(circle, Orthogonal((-3000000,-4000000),(3000000,4000000))))
        self.assertEqual(d.classify(circle, Aligned((-3000000,-4000000),(3000000,4000000))), 'diameter')

    def test_circle_bounds_and_multiple_outlines(self):
        b,c,r,_ = self.circle()
        c.SetStart(Point(1990000000,0)); c.SetEnd(Point(1995000000,0))
        r.SetStart(Point(1990000000,0)); r.SetEnd(Point(1995000000,0))
        with self.assertRaises(d.DimensionError): d.plan_resize(b,r,'20')
        b.Add(Shape(shape=4))
        with self.assertRaises(d.DimensionError): d.outline(b)

    def test_rectangle_standard_dimension_and_partial_attachment(self):
        c=Shape(shape=2); c.SetStart(Point(0,0)); c.SetEnd(Point(50000000,30000000))
        w=Aligned((0,0),(50000000,0)); partial=Aligned((50000000,30000000),(99000000,99000000))
        b=Board([c,w,partial]); d.apply_resize(b,w,'2*35')
        self.assertEqual(d.point(c.GetEnd()), (70000000,30000000))
        self.assertEqual(d.point(partial.GetStart()), (70000000,30000000))
        self.assertEqual(d.point(partial.GetEnd()), (99000000,99000000))

    def test_follower_limit_checked_before_mutation(self):
        b,c,r,_=self.circle()
        b.Add(Aligned((128300000,100400000),(-1900000000,100400000)))
        with self.assertRaises(d.DimensionError): d.apply_resize(b,r,'100')
        self.assertEqual(d.point(c.GetEnd()), (128300000,100400000))
