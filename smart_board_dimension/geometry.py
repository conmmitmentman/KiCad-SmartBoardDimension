# -*- coding: utf-8 -*-
"""単位計算および長方形外形の判定。KiCad非依存、テスト可能。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import unicodedata

IU_PER_MM = Decimal('1000000')  # KiCad内部単位 1 nm
UNITS = {'mm': '1', 'cm': '10', 'in': '25.4', 'mil': '0.0254'}
UNIT_PATTERN = re.compile(r'(?<=[\d)])\s*(mm|cm|mil|in)\b', re.IGNORECASE)

class DimensionError(ValueError):
    """利用者が修正できる入力・形状エラー。"""


def _eval(node, depth=0):
    if depth > 20:
        raise DimensionError('数式が複雑すぎます。')
    if isinstance(node, ast.Expression):
        return _eval(node.body, depth + 1)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return Decimal(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        n = _eval(node.operand, depth + 1)
        return n if isinstance(node.op, ast.UAdd) else -n
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left, right = _eval(node.left, depth + 1), _eval(node.right, depth + 1)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0:
            raise DimensionError('0で割ることはできません。')
        return left / right
    raise DimensionError('使える演算は +、-、*、/、() だけです。')


def parse_mm(text):
    """数式または長さをmm単位のDecimalで返す。例 2*15, 1in+5mm。"""
    s = unicodedata.normalize('NFKC', str(text)).strip()
    if not s or len(s) > 100:
        raise DimensionError('数値を100文字以内で入力してください。')
    s = UNIT_PATTERN.sub(lambda m: '*' + UNITS[m.group(1).lower()], s)
    try:
        tree = ast.parse(s, mode='eval')
        result = _eval(tree)
        if not result.is_finite():
            raise DimensionError('有限の数値を入力してください。')
        return result
    except (SyntaxError, InvalidOperation, OverflowError) as exc:
        raise DimensionError('数値または数式が正しくありません。') from exc


def mm_to_iu(mm):
    return int((Decimal(str(mm)) * IU_PER_MM).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def fmt_iu(iu):
    number = Decimal(iu) / IU_PER_MM
    return format(number.normalize(), 'f')


@dataclass(frozen=True)
class Bounds:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    def corners(self):
        return {
            (self.left, self.top), (self.right, self.top),
            (self.right, self.bottom), (self.left, self.bottom)
        }

    def anchor(self, kind):
        if kind == 0:  # 左上固定
            return self.left, self.top
        if kind == 1:  # 中心固定（nm単位は丸め）
            return (self.left + self.right) // 2, (self.top + self.bottom) // 2
        if kind == 2:  # 右下固定
            return self.right, self.bottom
        raise DimensionError('基準点の指定が正しくありません。')


def detect_four_line_rectangle(lines):
    """線分[(始点tuple, 終点tuple), ...] が軸平行の閉じた長方形か判定。"""
    if len(lines) != 4:
        raise DimensionError('長方形を構成する4本の直線が必要です。')
    pts = [p for start, end in lines for p in (start, end)]
    xs, ys = sorted({p[0] for p in pts}), sorted({p[1] for p in pts})
    if len(xs) != 2 or len(ys) != 2 or xs[0] == xs[1] or ys[0] == ys[1]:
        raise DimensionError('縦横の直線からなる長方形ではありません。')
    b = Bounds(xs[0], ys[0], xs[1], ys[1])
    tl, tr, br, bl = ((b.left,b.top), (b.right,b.top),
                      (b.right,b.bottom), (b.left,b.bottom))
    expected = {frozenset((tl, tr)), frozenset((tr, br)),
                frozenset((br, bl)), frozenset((bl, tl))}
    found = [frozenset((a, z)) for a, z in lines]
    if set(found) != expected or len(set(found)) != 4:
        raise DimensionError('4辺が隙間なく閉じた長方形ではありません。')
    return b


def place_rectangle(anchor_x, anchor_y, w, h, anchor_kind):
    """基準点と幅・高さはKiCad内部単位(int)。戻り値はBounds。"""
    if w <= 0 or h <= 0:
        raise DimensionError('幅と高さは0より大きくしてください。')
    if anchor_kind == 0:
        left, top = anchor_x, anchor_y
    elif anchor_kind == 1:
        left, top = anchor_x - w // 2, anchor_y - h // 2
    elif anchor_kind == 2:
        left, top = anchor_x - w, anchor_y - h
    else:
        raise DimensionError('基準点の指定が正しくありません。')
    return Bounds(left, top, left + w, top + h)


def map_corner(old, new, point):
    """古い矩形の4隅の座標を新しい矩形の同じ隅へ変換。"""
    x, y = point
    if x not in (old.left, old.right) or y not in (old.top, old.bottom):
        raise DimensionError('元の辺の端点が基板外形の角にありません。')
    return (new.left if x == old.left else new.right,
            new.top if y == old.top else new.bottom)


def validate_bounds(bounds):
    """Keep coordinates and extents within KiCad's signed 32-bit nanometers."""
    limit = 2000 * int(IU_PER_MM)
    if not (0 < bounds.width <= limit and 0 < bounds.height <= limit):
        raise DimensionError('幅と高さは0より大きく2000 mm以内にしてください。')
    if any(abs(v) > limit for v in
           (bounds.left, bounds.top, bounds.right, bounds.bottom)):
        raise DimensionError('変更後の四隅の座標が±2000 mmを超えます。寸法または基準点を変更してください。')
