# -*- coding: utf-8 -*-
"""Standard KiCad dimensions driving one simple outline. No GUI/startup side effects."""
from dataclasses import dataclass
from math import hypot
import pcbnew
from .geometry import DimensionError, Bounds, mm_to_iu, parse_mm, validate_bounds


def point(v):
    return int(v.x), int(v.y)


def is_type(item, name):
    cls = getattr(pcbnew, name, None)
    return cls is not None and isinstance(item, cls)


def dimension_kind(item):
    if is_type(item, 'PCB_DIM_RADIAL'):
        return 'radius'
    if is_type(item, 'PCB_DIM_ALIGNED') or is_type(item, 'PCB_DIM_ORTHOGONAL'):
        return 'linear'
    return None


@dataclass(frozen=True)
class Circle:
    center: tuple
    end: tuple

    @property
    def radius(self):
        return hypot(self.end[0] - self.center[0], self.end[1] - self.center[1])

    def on_edge(self, p):
        return abs(hypot(p[0] - self.center[0], p[1] - self.center[1]) - self.radius) <= min(10000, self.radius / 4)


def outline(board):
    edges = [x for x in board.GetDrawings() if x.GetLayer() == pcbnew.Edge_Cuts]
    if (len(edges) == 1 and is_type(edges[0], 'PCB_SHAPE')
            and edges[0].GetShape() == getattr(pcbnew, 'SHAPE_T_CIRCLE', -999)):
        circle = Circle(point(edges[0].GetStart()), point(edges[0].GetEnd()))
        if not 5000 <= circle.radius <= 1000000000:
            raise DimensionError('円の半径は0.005～1000 mmの範囲が対象です。')
        return edges, circle
    from . import _outline_info
    mode, shapes, bounds = _outline_info(board)
    if mode == 'new':
        raise DimensionError('Edge.Cutsに円または長方形を描いてください。')
    return shapes, bounds


def classify(geometry, dimension):
    kind = dimension_kind(dimension)
    if not kind:
        return None
    a, b = point(dimension.GetStart()), point(dimension.GetEnd())
    if isinstance(geometry, Circle):
        tol = min(10000, geometry.radius / 4)
        if kind == 'radius' and hypot(a[0]-geometry.center[0], a[1]-geometry.center[1]) <= tol and geometry.on_edge(b):
            return 'radius'
        if kind == 'linear' and geometry.on_edge(a) and geometry.on_edge(b):
            if is_type(dimension, 'PCB_DIM_ORTHOGONAL') and a[0] != b[0] and a[1] != b[1]:
                return None  # A projected diagonal length is not the diameter.
            if hypot((a[0]+b[0])/2-geometry.center[0], (a[1]+b[1])/2-geometry.center[1]) <= tol:
                return 'diameter'
        return None
    if kind != 'linear' or a not in geometry.corners() or b not in geometry.corners():
        return None
    if a[1] == b[1] and a[0] != b[0]:
        return 'width'
    if a[0] == b[0] and a[1] != b[1]:
        return 'height'
    return None


def find_selected(board, selection):
    if len(selection) != 1 or not dimension_kind(selection[0]):
        return None
    _, geometry = outline(board)
    return selection[0] if classify(geometry, selection[0]) else None


def current_value(geometry, kind):
    if isinstance(geometry, Circle):
        return round(geometry.radius * (2 if kind == 'diameter' else 1))
    return geometry.width if kind == 'width' else geometry.height


def plan_resize(board, selected, expression):
    """Validate ALL affected geometry/locks before the first setter is called."""
    shapes, before = outline(board)
    kind = classify(before, selected)
    if kind is None:
        raise DimensionError('寸法の端点を外形の角、または円の中心・円周に合わせてください。')
    value = parse_mm(expression)
    if not parse_mm('0.01') <= value <= 1000:
        raise DimensionError('寸法は0.01～1000 mmで入力してください。')
    size = mm_to_iu(value)
    if isinstance(before, Circle):
        radius = size / 2 if kind == 'diameter' else size
        cx, cy = before.center
        if max(abs(cx)+radius, abs(cy)+radius) > 2000000000:
            raise DimensionError('円が座標の範囲±2000 mmを超えます。')

        def mapped(p):
            if not before.on_edge(p):
                return p
            scale = radius / hypot(p[0]-cx, p[1]-cy)
            return round(cx+(p[0]-cx)*scale), round(cy+(p[1]-cy)*scale)
    else:
        after = Bounds(before.left, before.top,
                       before.left + (size if kind == 'width' else before.width),
                       before.top + (size if kind == 'height' else before.height))
        validate_bounds(after)

        def mapped(p):
            if p not in before.corners():
                return p
            return (after.left if p[0] == before.left else after.right,
                    after.top if p[1] == before.top else after.bottom)

    plan = []
    for item in list(shapes) + [x for x in board.GetDrawings() if dimension_kind(x)]:
        start, end = point(item.GetStart()), point(item.GetEnd())
        new_start, new_end = mapped(start), mapped(end)
        if (new_start, new_end) == (start, end):
            continue
        if item.IsLocked():
            raise DimensionError('変更する外形または寸法がロックされています。')
        if max(abs(v) for p in (new_start, new_end) for v in p) > 2000000000:
            raise DimensionError('変更後の座標が±2000 mmを超えます。')
        if dimension_kind(item) and hypot(new_end[0]-new_start[0], new_end[1]-new_start[1]) > 2000000000:
            raise DimensionError('追従する寸法が2000 mmを超えます。')
        plan.append((item, start, end, new_start, new_end))
    return plan


def apply_resize(board, selected, expression):
    plan = plan_resize(board, selected, expression)
    try:
        for item, _, _, start, end in plan:
            item.SetStart(pcbnew.VECTOR2I(*start))
            item.SetEnd(pcbnew.VECTOR2I(*end))
            if dimension_kind(item):
                item.Update()
    except Exception:
        for item, start, end, _, _ in plan:
            item.SetStart(pcbnew.VECTOR2I(*start))
            item.SetEnd(pcbnew.VECTOR2I(*end))
            if dimension_kind(item):
                item.Update()
        raise
    pcbnew.Refresh()


def edit_dialog(board, selected, parent):
    import wx
    _, geometry = outline(board)
    kind = classify(geometry, selected)
    if not kind:
        raise DimensionError('この寸法は外形に接続していません。')
    from .geometry import fmt_iu
    names = {'radius': '半径・中心固定', 'diameter': '直径・中心固定', 'width': '幅・左辺固定', 'height': '高さ・上辺固定'}
    dialog = wx.TextEntryDialog(parent, '数値・計算式（mm）を入力してください。例: 2*15、1in+5mm',
                                names[kind], fmt_iu(current_value(geometry, kind)))
    try:
        while dialog.ShowModal() == wx.ID_OK:
            try:
                apply_resize(board, selected, dialog.GetValue())
                break
            except DimensionError as exc:
                wx.MessageBox(str(exc), '寸法の確認', wx.OK | wx.ICON_WARNING, dialog)
    finally:
        dialog.Destroy()
