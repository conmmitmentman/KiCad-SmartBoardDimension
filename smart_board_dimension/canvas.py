# -*- coding: utf-8 -*-
"""Interactive outline preview. Geometry is committed only by the owning dialog."""
import wx

from .geometry import fmt_iu


class DimensionCanvas(wx.Panel):
    def __init__(self, parent, bounds, on_anchor, on_drag):
        super().__init__(parent, style=wx.TAB_TRAVERSAL)
        self.SetMinSize(self.FromDIP((480, 340)))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.before = self.after = bounds
        self.anchor = 0
        self.valid = True
        self.on_anchor, self.on_drag = on_anchor, on_drag
        self.drag = None
        self.transform = None
        self.hit_anchors = []
        self.hit_handles = []
        self.width_edit = wx.TextCtrl(self, value=fmt_iu(bounds.width),
                                     style=wx.TE_PROCESS_ENTER | wx.TE_CENTRE)
        self.height_edit = wx.TextCtrl(self, value=fmt_iu(bounds.height),
                                      style=wx.TE_PROCESS_ENTER | wx.TE_CENTRE)
        for control, name in ((self.width_edit, '横幅 W (mm)'),
                              (self.height_edit, '縦幅 H (mm)')):
            control.SetName(name)
            control.SetToolTip(name + '\n数式と単位も入力できます。例：2*35、1in+5mm')
            control.Bind(wx.EVT_SET_FOCUS, self._focus)
            control.Bind(wx.EVT_KILL_FOCUS, self._blur)
        self.Bind(wx.EVT_PAINT, self._paint)
        self.Bind(wx.EVT_SIZE, self._size)
        self.Bind(wx.EVT_LEFT_DOWN, self._down)
        self.Bind(wx.EVT_LEFT_UP, self._up)
        self.Bind(wx.EVT_MOTION, self._motion)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self._lost_capture)
        self.Bind(wx.EVT_CHAR_HOOK, self._key)

    def _focus(self, event):
        control = event.GetEventObject()
        control.SelectAll()
        self.Refresh()
        event.Skip()

    def _blur(self, event):
        self.Refresh()
        event.Skip()

    def update_geometry(self, bounds, anchor, valid=True):
        self.after, self.anchor, self.valid = bounds, anchor, valid
        self._layout_geometry()
        self.Refresh()

    def _size(self, event):
        self._layout_geometry()
        self.Refresh()
        event.Skip()

    def _layout_geometry(self):
        width, height = self.GetClientSize()
        # One common scale for old/new outlines; reserve space for input boxes.
        if not self.drag:
            a, b = self.before, self.after
            left, top = min(a.left, b.left), min(a.top, b.top)
            right, bottom = max(a.right, b.right), max(a.bottom, b.bottom)
            area_w, area_h = max(1, width - 194), max(1, height - 132)
            scale = min(area_w / max(1, right-left), area_h / max(1, bottom-top))
            self.transform = (scale, 40 + (area_w-(right-left)*scale)/2-left*scale,
                              74 + (area_h-(bottom-top)*scale)/2-top*scale)
        b = self.after
        x, y = self.screen(b.left, b.top)
        r, z = self.screen(b.right, b.bottom)
        # Keep the edit controls stable while typing, so the pointer never chases a box.
        self.width_edit.SetSize(max(8, (width-130)//2), 25, 130, 28)
        self.height_edit.SetSize(max(8, width-140), max(70, (height-28)//2), 130, 28)
        self.hit_anchors = [self.screen(*b.anchor(i)) for i in range(3)]
        # With bottom-right fixed, drag the opposite (left/top) sides instead.
        self.hit_handles = [(x if self.anchor == 2 else r, (y+z)//2),
                            ((x+r)//2, y if self.anchor == 2 else z)]

    def screen(self, x, y):
        if self.transform is None:
            return 0, 0
        scale, ox, oy = self.transform
        return round(x*scale+ox), round(y*scale+oy)

    def _paint(self, _event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush('#F5F8FB'))
        dc.Clear()
        self._layout_geometry()
        width, height = self.GetClientSize()
        dc.SetPen(wx.Pen('#E4EAF0'))
        for x in range(16, width, 24):
            for y in range(16, height, 24):
                dc.DrawPoint(x, y)
        dc.SetFont(self.GetFont())
        dc.SetTextForeground('#526375')
        dc.DrawText('横幅 W · mm', max(8, (width-130)//2), 6)
        dc.DrawText('縦幅 H · mm', max(8, width-140), max(50, (height-28)//2-21))

        def outline(bounds, pen, brush):
            x, y = self.screen(bounds.left, bounds.top)
            r, b = self.screen(bounds.right, bounds.bottom)
            dc.SetPen(pen)
            dc.SetBrush(brush)
            dc.DrawRectangle(x, y, max(1, r-x), max(1, b-y))

        outline(self.after, wx.Pen('#14876B', 2), wx.Brush('#E0F2EC'))
        if self.before != self.after:
            # Explicit lines avoid host-dependent initialization of stock transparent brushes.
            ox, oy = self.screen(self.before.left, self.before.top)
            oright, obottom = self.screen(self.before.right, self.before.bottom)
            dc.SetPen(wx.Pen('#8494A5', 1, wx.PENSTYLE_SHORT_DASH))
            dc.DrawLines([(ox, oy), (oright, oy), (oright, obottom),
                          (ox, obottom), (ox, oy)])
        x, y = self.screen(self.after.left, self.after.top)
        r, b = self.screen(self.after.right, self.after.bottom)
        dc.SetPen(wx.Pen('#3C77B1', 1))
        # Dimension lines and end ticks stay separate from the editable text.
        for ax, ay, bx, by in ((x, 62, r, 62), (x, 57, x, y), (r, 57, r, y),
                              (r+16, y, r+16, b), (r, y, r+21, y), (r, b, r+21, b)):
            dc.DrawLine(ax, ay, bx, by)
        for i, (cx, cy) in enumerate(self.hit_handles):
            dc.SetPen(wx.Pen('#246DA9', 2))
            dc.SetBrush(wx.Brush('#FFFFFF'))
            dc.DrawRectangle(cx-5, cy-5, 10, 10)
        for i, (cx, cy) in enumerate(self.hit_anchors):
            dc.SetPen(wx.Pen('#BF6B13' if i == self.anchor else '#8192A3', 2))
            dc.SetBrush(wx.Brush('#F6AD45' if i == self.anchor else '#FFFFFF'))
            dc.DrawCircle(cx, cy, 5 if i == self.anchor else 4)
        dc.SetTextForeground('#526375' if self.valid else '#B3261E')
        caption = ('緑：変更後  /  破線：変更前  /  オレンジ：固定点' if self.valid else
                   '入力エラー：最後に有効だった外形を表示中')
        dc.DrawText(caption, 12, max(0, height-40))
        dc.SetTextForeground('#526375')
        dc.DrawText('□ をドラッグ  ·  ○ をクリックして固定点を選択', 12, max(0, height-21))

    @staticmethod
    def _near(point, target):
        return abs(point.x-target[0]) <= 9 and abs(point.y-target[1]) <= 9

    def _down(self, event):
        if not self.valid:
            return
        p = event.GetPosition()
        for i, target in enumerate(self.hit_anchors):
            if self._near(p, target):
                self.on_anchor(i)
                return
        for axis, target in enumerate(self.hit_handles):
            if self._near(p, target):
                self.SetFocus()
                self.drag = (axis, p, self.after, self.width_edit.GetValue(),
                             self.height_edit.GetValue())
                self.CaptureMouse()
                return
        # Picking a visible side selects the dimension perpendicular to it.
        x, y = self.screen(self.after.left, self.after.top)
        r, b = self.screen(self.after.right, self.after.bottom)
        control = None
        if y-5 <= p.y <= b+5 and min(abs(p.x-x), abs(p.x-r)) <= 7:
            control = self.width_edit
        elif x-5 <= p.x <= r+5 and min(abs(p.y-y), abs(p.y-b)) <= 7:
            control = self.height_edit
        if control:
            control.SetFocus()
            control.SelectAll()

    def _motion(self, event):
        p = event.GetPosition()
        if self.drag:
            axis, start, bounds, _, _ = self.drag
            delta = (p.x-start.x if axis == 0 else p.y-start.y) / self.transform[0]
            factor = (1, 2, -1)[self.anchor]
            value = (bounds.width if axis == 0 else bounds.height) + delta*factor
            # Drag uses 0.1 mm increments; typed values retain full precision.
            value = max(10000, min(2000000000, round(value/100000)*100000))
            self.on_drag(axis, value)
        else:
            cursor = wx.CURSOR_ARROW
            if self.valid:
                for axis, target in enumerate(self.hit_handles):
                    if self._near(p, target):
                        cursor = wx.CURSOR_SIZEWE if axis == 0 else wx.CURSOR_SIZENS
                if any(self._near(p, t) for t in self.hit_anchors):
                    cursor = wx.CURSOR_HAND
            self.SetCursor(wx.Cursor(cursor))

    def finish_drag(self, cancel=False):
        if not self.drag:
            return
        _, _, _, w, h = self.drag
        self.drag = None
        if self.HasCapture():
            self.ReleaseMouse()
        if cancel:
            self.width_edit.ChangeValue(w)
            self.height_edit.ChangeValue(h)
            self.on_drag(None, None)
        self._layout_geometry()
        self.Refresh()

    def _up(self, _event):
        self.finish_drag()

    def _lost_capture(self, _event):
        self.finish_drag(cancel=True)

    def _key(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE and self.drag:
            self.finish_drag(cancel=True)
        else:
            event.Skip()
