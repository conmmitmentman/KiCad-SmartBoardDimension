# -*- coding: utf-8 -*-
"""KiCad 10 日本語スマート基板寸法 Action Plugin (SWIG API)。"""
import traceback
import threading
from pathlib import Path

import pcbnew
import wx

from .geometry import (Bounds, DimensionError, detect_four_line_rectangle,
                       fmt_iu, map_corner, mm_to_iu, parse_mm, place_rectangle)
from .updater import (UpdateError, get_repository, save_repository,
                      check_latest, perform_update)


PLUGIN_VERSION = '1.2.0'


def _point(v):
    return int(v.x), int(v.y)


def _vec(p):
    return pcbnew.VECTOR2I(int(p[0]), int(p[1]))


def _outline_info(board):
    # Edge.Cuts に予想外の種類の描画要素がある場合は編集しない。
    edge_items = [item for item in board.GetDrawings()
                  if hasattr(item, 'GetLayer') and item.GetLayer() == pcbnew.Edge_Cuts]
    if not edge_items:
        return 'new', None, Bounds(mm_to_iu(100), mm_to_iu(100),
                                   mm_to_iu(150), mm_to_iu(130))
    if not all(isinstance(item, pcbnew.PCB_SHAPE) for item in edge_items):
        raise DimensionError('Edge.Cutsに線・矩形以外の要素があります。安全のため変更できません。')

    if len(edge_items) == 1 and edge_items[0].GetShape() in (
            pcbnew.SHAPE_T_RECTANGLE, pcbnew.SHAPE_T_RECT):
        shape = edge_items[0]
        if shape.GetCornerRadius() > 0:
            raise DimensionError('角丸長方形はこのバージョンでは編集できません。')
        a, z = _point(shape.GetStart()), _point(shape.GetEnd())
        box = Bounds(min(a[0], z[0]), min(a[1], z[1]),
                     max(a[0], z[0]), max(a[1], z[1]))
        if box.width <= 0 or box.height <= 0:
            raise DimensionError('元の長方形の幅または高さが0です。')
        # 回転した矩形は SetStart/SetEnd のみで変更しない。
        corners = [_point(c) for c in shape.GetCorners()]
        if len(corners) != 4 or set(corners) != box.corners():
            raise DimensionError('回転した長方形は対象外です。軸に平行な矩形を使用してください。')
        return 'shape', edge_items, box

    if len(edge_items) == 4 and all(
            item.GetShape() == pcbnew.SHAPE_T_SEGMENT for item in edge_items):
        lines = [(_point(item.GetStart()), _point(item.GetEnd()))
                 for item in edge_items]
        box = detect_four_line_rectangle(lines)
        return 'lines', edge_items, box

    raise DimensionError('対応する外形は、単独の長方形、または4本の直線でできた長方形です。\n'
                         '複数外形、円弧、穴・切り欠きは変更しません。')


class SmartDimensionDialog(wx.Dialog):
    LABELS = ('左上を固定', '中心を固定', '右下を固定')

    def __init__(self, bounds, mode):
        super().__init__(None, title=f'スマート基板寸法 v{PLUGIN_VERSION}  |  KiCad 10',
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.bounds = bounds
        self.result = None
        self._updating = False
        root = wx.BoxSizer(wx.VERTICAL)
        body = wx.Panel(self)
        main = wx.BoxSizer(wx.VERTICAL)

        heading = wx.StaticText(body, label=('新しい長方形基板を作成' if mode == 'new'
                                             else '現在の基板外形を寸法で変更'))
        font = heading.GetFont()
        font.SetPointSize(font.GetPointSize() + 2)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        heading.SetFont(font)
        main.Add(heading, 0, wx.ALL, 12)
        main.Add(wx.StaticText(body, label='基板外形（Edge.Cuts）・単位 mm'), 0,
                 wx.LEFT | wx.BOTTOM, 12)

        form = wx.FlexGridSizer(0, 2, 9, 12)
        form.AddGrowableCol(1, 1)

        def add_row(title, default):
            form.Add(wx.StaticText(body, label=title), 0, wx.ALIGN_CENTER_VERTICAL)
            control = wx.TextCtrl(body, value=default, size=(220, -1))
            form.Add(control, 1, wx.EXPAND)
            return control

        self.w = add_row('横幅 W (mm)', fmt_iu(bounds.width))
        self.h = add_row('縦幅 H (mm)', fmt_iu(bounds.height))
        form.Add(wx.StaticText(body, label='寸法変更の基準'), 0, wx.ALIGN_CENTER_VERTICAL)
        self.anchor = wx.Choice(body, choices=list(self.LABELS))
        self.anchor.SetSelection(0)
        form.Add(self.anchor, 1, wx.EXPAND)
        self.x = add_row('基準点 X (mm)', fmt_iu(bounds.left))
        self.y = add_row('基準点 Y (mm)', fmt_iu(bounds.top))
        main.Add(form, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 16)
        main.Add(wx.StaticText(body, label='数式も入力可能： 20+5  /  2*15  /  1in+5mm'),
                 0, wx.ALL, 15)

        line = wx.StaticBoxSizer(wx.VERTICAL, body, '変更プレビュー（数値）')
        self.preview = wx.StaticText(body, label='', style=wx.ST_NO_AUTORESIZE)
        line.Add(self.preview, 0, wx.EXPAND | wx.ALL, 10)
        main.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)
        safety = wx.StaticText(body, label='※ 部品・配線・ゾーンは移動しません。変更後はDRC確認を推奨。')
        safety.Wrap(460)
        main.Add(safety, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)

        body.SetSizer(main)
        root.Add(body, 1, wx.EXPAND)
        root.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        actions = wx.BoxSizer(wx.HORIZONTAL)
        self.update_button = wx.Button(self, label='GitHubから更新')
        self.source_button = wx.Button(self, label='更新元の設定')
        actions.Add(self.update_button, 0, wx.RIGHT, 6)
        actions.Add(self.source_button, 0, wx.RIGHT, 6)
        actions.AddStretchSpacer(1)
        actions.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0)
        root.Add(actions, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.update_status = wx.StaticText(self, label='オンライン更新はボタンを押したときだけ確認します。')
        root.Add(self.update_status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.TOP, 12)
        self.SetSizerAndFit(root)
        self.SetMinSize((550, 450))
        self.SetSize((600, 470))
        self.CentreOnScreen()

        self.anchor.Bind(wx.EVT_CHOICE, self._on_anchor)
        for ctrl in (self.w, self.h, self.x, self.y):
            ctrl.Bind(wx.EVT_TEXT, self._update_preview)
        self.Bind(wx.EVT_BUTTON, self._ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._cancel, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.update_button.Bind(wx.EVT_BUTTON, self._check_updates)
        self.source_button.Bind(wx.EVT_BUTTON, self._configure_repository)
        self._update_preview()

    def _cancel(self, _evt):
        if not self._updating:
            self.EndModal(wx.ID_CANCEL)

    def _on_close(self, evt):
        if self._updating and evt.CanVeto():
            evt.Veto()
            return
        evt.Skip()

    def _set_updating(self, state, status):
        self._updating = state
        self.update_button.Enable(not state)
        self.source_button.Enable(not state)
        for ident in (wx.ID_OK, wx.ID_CANCEL):
            button = self.FindWindowById(ident)
            if button:
                button.Enable(not state)
        self.update_status.SetLabel(status)
        self.Layout()

    def _configure_repository(self, _evt=None):
        try:
            previous = get_repository()
        except UpdateError:
            previous = ''
        prompt = ('更新元のGitHubリポジトリURLを入力してください。\n'
                  '例：https://github.com/OWNER/REPOSITORY\n'
                  '※信頼するリポジトリだけを登録してください。')
        dialog = wx.TextEntryDialog(self, prompt, 'GitHub更新元の設定', value=previous)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return False
            repository = dialog.GetValue()
        finally:
            dialog.Destroy()
        try:
            save_repository(repository)
            self.update_status.SetLabel('更新元を保存しました。')
            return True
        except (UpdateError, OSError) as exc:
            wx.MessageBox(str(exc), 'GitHub更新元の設定', wx.OK | wx.ICON_WARNING, self)
            return False

    def _check_updates(self, _evt):
        try:
            repo = get_repository()
            if not repo:
                if not self._configure_repository():
                    return
                repo = get_repository()
        except UpdateError as exc:
            wx.MessageBox(str(exc), '更新設定エラー', wx.OK | wx.ICON_ERROR, self)
            return
        self._set_updating(True, 'GitHub Releasesで最新版を確認しています…')

        def worker():
            try:
                release = check_latest(repo, PLUGIN_VERSION)
                wx.CallAfter(self._checked, release, None)
            except Exception as exc:
                wx.CallAfter(self._checked, None, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _checked(self, release, failure):
        self._set_updating(False, '更新確認が完了しました。')
        if failure:
            wx.MessageBox(failure, '更新を確認できません', wx.OK | wx.ICON_WARNING, self)
            return
        if not release['available']:
            wx.MessageBox(f'現在 v{PLUGIN_VERSION}、更新先 {release["latest"]}。\n最新版です。',
                          'スマート基板寸法', wx.OK | wx.ICON_INFORMATION, self)
            return
        message = (f'新しいバージョン v{release["latest"]} が公開されています。\n'
                   f'現在：v{PLUGIN_VERSION}\n'
                   f'更新元：{release["repository"]}\n\n'
                   'プラグインのPythonコードをダウンロードして置き換えます。\n'
                   '更新前のコードをバックアップします。\n'
                   '続行しますか？（更新後はKiCadの再起動が必要）')
        if wx.MessageBox(message, 'GitHubから更新', wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
                         self) != wx.YES:
            return
        self._set_updating(True, 'ダウンロード・検証・バックアップ・更新を実行しています…')

        def worker():
            try:
                backup = perform_update(Path(__file__).resolve().parent, PLUGIN_VERSION, release)
                wx.CallAfter(self._updated, str(backup), None)
            except Exception as exc:
                wx.CallAfter(self._updated, None, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _updated(self, backup_path, failure):
        self._set_updating(False, '更新処理が完了しました。')
        if failure:
            wx.MessageBox(failure, '更新に失敗しました', wx.OK | wx.ICON_ERROR, self)
            return
        wx.MessageBox('更新ファイルの配置が完了しました。\n\n'
                      '開いている基板を保存し、KiCadのPCBエディタを終了・再起動してください。\n'
                      f'プラグインの旧版バックアップ：\n{backup_path}',
                      '更新完了・再起動が必要', wx.OK | wx.ICON_INFORMATION, self)
        self.EndModal(wx.ID_CANCEL)

    def _on_anchor(self, _evt):
        x, y = self.bounds.anchor(self.anchor.GetSelection())
        self.x.ChangeValue(fmt_iu(x))
        self.y.ChangeValue(fmt_iu(y))
        self._update_preview()

    def _read(self):
        w, h = parse_mm(self.w.GetValue()), parse_mm(self.h.GetValue())
        x, y = parse_mm(self.x.GetValue()), parse_mm(self.y.GetValue())
        if not (parse_mm("0.01") <= w <= parse_mm("10000") and
                parse_mm("0.01") <= h <= parse_mm("10000")):
            raise DimensionError('幅と高さは0.01～10000 mmの範囲にしてください。')
        if not (-100000 <= x <= 100000 and -100000 <= y <= 100000):
            raise DimensionError('X・Y座標は±100000 mm以内にしてください。')
        return place_rectangle(mm_to_iu(x), mm_to_iu(y),
                               mm_to_iu(w), mm_to_iu(h), self.anchor.GetSelection())

    def _update_preview(self, _evt=None):
        try:
            b = self._read()
            txt = (f'外形サイズ：{fmt_iu(b.width)} × {fmt_iu(b.height)} mm\n'
                   f'左上：({fmt_iu(b.left)}, {fmt_iu(b.top)}) mm\n'
                   f'右下：({fmt_iu(b.right)}, {fmt_iu(b.bottom)}) mm')
        except (DimensionError, ValueError):
            txt = '入力を修正すると、新しい寸法が表示されます。'
        self.preview.SetLabel(txt)
        self.Layout()

    def _ok(self, _evt):
        try:
            self.result = self._read()
        except (DimensionError, ValueError) as exc:
            wx.MessageBox(str(exc), '寸法入力の確認', wx.OK | wx.ICON_WARNING, self)
            return
        self.EndModal(wx.ID_OK)


def _apply(board, mode, shapes, before, after):
    if mode == 'new':
        shape = pcbnew.PCB_SHAPE(board)
        shape.SetShape(pcbnew.SHAPE_T_RECTANGLE)
        shape.SetStart(_vec((after.left, after.top)))
        shape.SetEnd(_vec((after.right, after.bottom)))
        shape.SetLayer(pcbnew.Edge_Cuts)
        shape.SetWidth(pcbnew.FromMM(0.05))
        shape.SetFilled(False)
        board.Add(shape)
    elif mode == 'shape':
        shape = shapes[0]
        shape.SetStart(_vec((after.left, after.top)))
        shape.SetEnd(_vec((after.right, after.bottom)))
    elif mode == 'lines':
        # 先に全4辺の変更後座標を計算してから適用。
        coords = [
            (map_corner(before, after, _point(item.GetStart())),
             map_corner(before, after, _point(item.GetEnd())))
            for item in shapes
        ]
        for item, (start, end) in zip(shapes, coords):
            item.SetStart(_vec(start))
            item.SetEnd(_vec(end))
    else:
        raise DimensionError('未対応の編集形式です。')
    pcbnew.Refresh()


class SmartBoardDimensionPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = 'スマート基板寸法（幅・高さ）'
        self.category = '基板外形の編集'
        self.description = 'Edge.Cutsの長方形を日本語UIで幅・高さ指定して変更します'
        self.show_toolbar_button = False

    def Run(self):
        try:
            board = pcbnew.GetBoard()
            if board is None:
                raise DimensionError('PCBエディタで基板を開いてください。')
            mode, shapes, bounds = _outline_info(board)
            dialog = SmartDimensionDialog(bounds, mode)
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                after = dialog.result
            finally:
                dialog.Destroy()
            if mode != 'new' and after == bounds:
                wx.MessageBox('寸法は変更されていません。', 'スマート基板寸法', wx.OK | wx.ICON_INFORMATION)
                return
            _apply(board, mode, shapes, bounds, after)
            wx.MessageBox(
                f'基板外形を {fmt_iu(after.width)} × {fmt_iu(after.height)} mm に変更しました。\n\n'
                '基板を保存し、DRC（設計ルールチェック）を実行してください。\n'
                'このプラグインは元に戻す（Undo）を保証しません。',
                'スマート基板寸法', wx.OK | wx.ICON_INFORMATION)
        except DimensionError as exc:
            wx.MessageBox(str(exc), 'スマート基板寸法：変更できません', wx.OK | wx.ICON_WARNING)
        except Exception as exc:
            wx.MessageBox(f'実行中に予期しないエラーが発生しました。\n{exc}\n\n'
                          + traceback.format_exc(),
                          'スマート基板寸法：エラー', wx.OK | wx.ICON_ERROR)


SmartBoardDimensionPlugin().register()
