# -*- coding: utf-8 -*-
"""KiCad 10 日本語スマート基板寸法 Action Plugin (SWIG API)。"""
import traceback
import threading
from pathlib import Path

import pcbnew
import wx

from .geometry import (Bounds, DimensionError, detect_four_line_rectangle,
                       fmt_iu, map_corner, mm_to_iu, parse_mm, place_rectangle,
                       validate_bounds)
from .updater import (UpdateError, get_repository, save_repository,
                      check_latest, perform_update)
from .canvas import DimensionCanvas


PLUGIN_VERSION = '1.4.0'
_direct_session = None
_startup_timer = None


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
        self.pending = bounds
        self.anchor_kind = 0
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
        main.Add(wx.StaticText(body, label='図の寸法を入力、または □ をドラッグしてサイズを変更'), 0,
                 wx.LEFT | wx.BOTTOM, 12)

        workspace = wx.BoxSizer(wx.HORIZONTAL)
        self.canvas = DimensionCanvas(body, bounds, self._select_anchor, self._drag_dimension)
        self.w, self.h = self.canvas.width_edit, self.canvas.height_edit
        workspace.Add(self.canvas, 1, wx.EXPAND | wx.RIGHT, 16)
        settings = wx.Panel(body)
        settings.SetMinSize((330, -1))
        side = wx.BoxSizer(wx.VERTICAL)
        side.Add(wx.StaticText(settings, label='固定する位置'), 0, wx.BOTTOM, 8)
        self.anchor = wx.Choice(settings, choices=list(self.LABELS))
        self.anchor.SetSelection(0)
        side.Add(self.anchor, 0, wx.EXPAND | wx.BOTTOM, 12)
        form = wx.FlexGridSizer(0, 2, 9, 12)
        form.AddGrowableCol(1, 1)

        def add_row(title, default):
            form.Add(wx.StaticText(settings, label=title), 0, wx.ALIGN_CENTER_VERTICAL)
            control = wx.TextCtrl(settings, value=default, size=(115, -1))
            form.Add(control, 1, wx.EXPAND)
            return control

        self.x = add_row('X (mm)', fmt_iu(bounds.left))
        self.y = add_row('Y (mm)', fmt_iu(bounds.top))
        side.Add(form, 0, wx.EXPAND | wx.BOTTOM, 16)
        side.Add(wx.StaticText(settings, label='数式・単位も入力できます\n20+5  /  2*35  /  1in+5mm\n\nTab：次の欄へ\nドラッグ中の Esc：変更を戻す'),
                 0, wx.BOTTOM, 16)

        line = wx.StaticBoxSizer(wx.VERTICAL, settings, '変更後の寸法と位置')
        self.preview = wx.StaticText(line.GetStaticBox(), label='外形サイズ：\n左上：\n右下：')
        line.Add(self.preview, 0, wx.EXPAND | wx.ALL, 10)
        side.Add(line, 0, wx.EXPAND | wx.BOTTOM, 12)
        self.reset_button = wx.Button(settings, label='最初の寸法に戻す')
        self.reset_button.Bind(wx.EVT_BUTTON, self._reset)
        side.Add(self.reset_button, 0, wx.EXPAND)
        settings.SetSizer(side)
        workspace.Add(settings, 0, wx.EXPAND)
        main.Add(workspace, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        self.error = wx.StaticText(body, label='')
        self.error.SetForegroundColour(wx.Colour('#B3261E'))
        self.error.SetMinSize((-1, self.GetCharHeight()*2+8))
        main.Add(self.error, 0, wx.EXPAND | wx.ALL, 12)
        safety = wx.StaticText(body, label='※ 部品・配線・ゾーンは移動しません。変更後はDRC確認を推奨。')
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
        self.FindWindowById(wx.ID_OK).SetLabel('基板に反映')
        root.Add(actions, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.update_status = wx.StaticText(self, label='オンライン更新はボタンを押したときだけ確認します。')
        root.Add(self.update_status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.TOP, 12)
        self.SetSizer(root)

        self.anchor.Bind(wx.EVT_CHOICE, self._on_anchor)
        for ctrl in (self.w, self.h, self.x, self.y):
            ctrl.Bind(wx.EVT_TEXT, self._update_preview)
        self.w.Bind(wx.EVT_TEXT_ENTER, lambda _evt: self.h.SetFocus())
        self.h.Bind(wx.EVT_TEXT_ENTER, lambda _evt: self.FindWindowById(wx.ID_OK).SetFocus())
        self.Bind(wx.EVT_BUTTON, self._ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._cancel, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.update_button.Bind(wx.EVT_BUTTON, self._check_updates)
        self.source_button.Bind(wx.EVT_BUTTON, self._configure_repository)
        self._update_preview()
        # Font/DPI dependent best size must include the three-line preview.
        # A fixed pixel height clips the panel on Windows display scaling.
        self.Fit()
        self.SetMinSize(self.GetSize())
        self.CentreOnScreen()
        self.w.SetFocus()

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
        if not state:
            self._update_preview()
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
        if Path(__file__).with_name('pcm-managed.txt').exists():
            wx.MessageBox('PCMで導入した版は、プラグイン＆コンテンツマネージャーから更新してください。',
                          'プラグインの更新', wx.OK | wx.ICON_INFORMATION, self)
            return
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
        self._select_anchor(self.anchor.GetSelection())

    def _select_anchor(self, kind):
        # Changing the fixed point must not undo the size/position already previewed.
        try:
            current = self._read(anchor=self.anchor_kind)
        except (DimensionError, ValueError):
            self.anchor.SetSelection(self.anchor_kind)
            return
        self.anchor_kind = kind
        self.anchor.SetSelection(kind)
        x, y = current.anchor(kind)
        self.x.ChangeValue(fmt_iu(x))
        self.y.ChangeValue(fmt_iu(y))
        self._update_preview()

    def _reset(self, _evt=None):
        self.canvas.finish_drag(cancel=True)
        self.w.ChangeValue(fmt_iu(self.bounds.width))
        self.h.ChangeValue(fmt_iu(self.bounds.height))
        x, y = self.bounds.anchor(self.anchor_kind)
        self.x.ChangeValue(fmt_iu(x))
        self.y.ChangeValue(fmt_iu(y))
        self._update_preview()

    def _drag_dimension(self, axis, value):
        if axis is not None:
            control = (self.w, self.h)[axis]
            previous = control.GetValue()
            control.ChangeValue(fmt_iu(value))
            try:
                self._read()
            except (DimensionError, ValueError):
                control.ChangeValue(previous)
        self._update_preview()

    def _read(self, anchor=None):
        w, h = parse_mm(self.w.GetValue()), parse_mm(self.h.GetValue())
        x, y = parse_mm(self.x.GetValue()), parse_mm(self.y.GetValue())
        if not (parse_mm("0.01") <= w <= 2000 and
                parse_mm("0.01") <= h <= 2000):
            raise DimensionError('幅と高さは0.01～2000 mmの範囲にしてください。')
        if not (-2000 <= x <= 2000 and -2000 <= y <= 2000):
            raise DimensionError('X・Y座標は±2000 mm以内にしてください。')
        bounds = place_rectangle(mm_to_iu(x), mm_to_iu(y),
                                 mm_to_iu(w), mm_to_iu(h), self.anchor_kind if anchor is None else anchor)
        validate_bounds(bounds)
        return bounds

    def _update_preview(self, _evt=None):
        error = ''
        try:
            b = self._read()
            self.pending = b
            txt = (f'外形サイズ：{fmt_iu(b.width)} × {fmt_iu(b.height)} mm\n'
                   f'左上：({fmt_iu(b.left)}, {fmt_iu(b.top)}) mm\n'
                   f'右下：({fmt_iu(b.right)}, {fmt_iu(b.bottom)}) mm')
        except (DimensionError, ValueError) as exc:
            error = str(exc)
            txt = '入力を修正してください。\n基板にはまだ反映していません。\n'
        self.preview.SetLabel(txt)
        self.error.SetLabel(error)
        self.error.Wrap(max(200, self.canvas.GetSize().width))
        self.canvas.update_geometry(self.pending, self.anchor_kind, not error)
        self.FindWindowById(wx.ID_OK).Enable(not error and not self._updating)
        self.Layout()

    def _ok(self, _evt):
        try:
            self.result = self._read()
        except (DimensionError, ValueError) as exc:
            wx.MessageBox(str(exc), '寸法入力の確認', wx.OK | wx.ICON_WARNING, self)
            return
        self.EndModal(wx.ID_OK)


def _apply(board, mode, shapes, before, after):
    # Validate every endpoint before mutating any existing item.
    validate_bounds(after)
    if any(item.IsLocked() for item in (shapes or [])):
        raise DimensionError('基板外形がロックされています。')
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
        self.name = 'スマート基板寸法（PCB上で編集）'
        self.category = '基板外形の編集'
        self.description = 'PCB上の寸法をダブルクリック、または選択してEで基板外形を変更'
        self.show_toolbar_button = True

    def Run(self):
        global _direct_session
        from .direct_editor import DirectSession, find_dimensions, sync_dimensions
        try:
            board = pcbnew.GetBoard()
            if board is None:
                raise DimensionError('PCBエディタで基板を開いてください。')
            if _direct_session is not None and not _direct_session.matches(board):
                _direct_session.close()
                _direct_session = None
            if _direct_session is None:
                _direct_session = DirectSession(board, self.name, show=False)
            if _direct_session is not None and _direct_session.matches(board):
                operation = _direct_session.pending
                _direct_session.pending = None
                if operation is None:
                    operation = _direct_session.selected_axis()
                if isinstance(operation, tuple) and operation[0] == 'dimension':
                    from .driving import edit_dialog
                    selected = next((x for x in board.GetDrawings()
                                     if x.m_Uuid.AsString() == operation[1]), None)
                    if selected is None:
                        raise DimensionError('選択した寸法が見つかりません。')
                    edit_dialog(board, selected, _direct_session.editor)
                    return
                _direct_session.pending = operation
            from .driving import outline, Circle
            if any(x.GetLayer() == pcbnew.Edge_Cuts for x in board.GetDrawings()):
                if isinstance(outline(board)[1], Circle):
                    wx.MessageBox('標準の半径寸法を円の中心→円周へ配置してください。\n'
                                  '直径は円周の向かい合う2点に整列寸法を配置します。\n'
                                  'Escで配置を終え、寸法をクリックするか選択してEを押します。',
                                  '円の寸法編集', wx.OK | wx.ICON_INFORMATION)
                    return
            mode, shapes, before = _outline_info(board)
            managed = find_dimensions(board)  # Reject duplicates/locks before mutation.
            if any(item.IsLocked() for item in managed.values()):
                raise DimensionError('管理する寸法がロックされています。')
            session = _direct_session
            operation = session.pending
            session.pending = None
            if operation is None:
                operation = session.selected_axis()
            if operation == 'details':
                self._run_form()
                sync_dimensions(board, _outline_info(board)[2])
            elif operation in (0, 1):
                after = session.edit_value(before, operation)
                if after is not None and after != before:
                    _apply(board, mode, shapes, before, after)
                    sync_dimensions(board, after)
            else:
                if mode == 'new':
                    _apply(board, mode, shapes, before, before)
                sync_dimensions(board, before)
                session.window.Show()
                session.window.Raise()
        except DimensionError as exc:
            wx.MessageBox(str(exc), 'スマート基板寸法：変更できません', wx.OK | wx.ICON_WARNING)
        except Exception as exc:
            wx.MessageBox(f'PCB上の寸法編集を開始できません。\n{exc}\n\n' + traceback.format_exc(),
                          'スマート基板寸法：エラー', wx.OK | wx.ICON_ERROR)

    def _run_form(self):
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


_plugin = SmartBoardDimensionPlugin()
_plugin.register()


def _attach_when_ready():
    """Only attach UI listeners here; board changes always use ActionPlugin.Run."""
    global _direct_session, _startup_timer
    try:
        from .direct_editor import DirectSession
        board = pcbnew.GetBoard()
        if _direct_session is not None and not _direct_session.matches(board):
            _direct_session.close()
            _direct_session = None
        if board is not None and _direct_session is None:
            _direct_session = DirectSession(board, _plugin.name, show=False)
    except (RuntimeError, DimensionError):
        pass  # The editor/menu may not exist yet during plugin discovery.
    finally:
        if wx.GetApp() is not None:
            _startup_timer = wx.CallLater(1500, _attach_when_ready)


# A standalone pcbnew interpreter has no wx app; importing never edits a board.
if hasattr(wx, 'GetApp') and wx.GetApp() is not None:
    _startup_timer = wx.CallLater(1500, _attach_when_ready)
