# -*- coding: utf-8 -*-
"""Edit board dimensions from KiCad's own PCB canvas.

Event handlers only enqueue a registered ActionPlugin menu command. All board
mutations run inside KiCad's action transaction, never from a timer or event hook.
Only dimensions with the plugin UUID namespace are intercepted. Their identity
is stored in the board without visible prefixes or groups; GUI Undo/Redo still
needs end-to-end validation.
"""
import uuid
import pcbnew
import wx

from .geometry import DimensionError, fmt_iu, mm_to_iu, parse_mm, place_rectangle, validate_bounds

PREFIXES = ('SBD W = ', 'SBD H = ')
GROUP_NAMES = ('SmartBoardDimension:width', 'SmartBoardDimension:height')
UUID_PREFIXES = ('5bd10000-4b1c-4ad0-a0', '5bd10000-4b1c-4ad0-a1')
ANCHORS = ('左上固定', '中心固定', '右下固定')


def resize_bounds(before, axis, text, anchor):
    value = parse_mm(text)
    if not parse_mm('0.01') <= value <= 2000:
        raise DimensionError('寸法は0.01～2000 mmの範囲で入力してください。')
    sizes = [before.width, before.height]
    sizes[axis] = mm_to_iu(value)
    after = place_rectangle(*before.anchor(anchor), *sizes, anchor)
    validate_bounds(after)
    return after


def find_dimensions(board):
    found = {}
    drawings = {item.m_Uuid.AsString(): item for item in board.GetDrawings()}
    ids = [[], []]
    for ident in drawings:
        for axis, prefix in enumerate(UUID_PREFIXES):
            if ident.startswith(prefix) and ident not in ids[axis]:
                ids[axis].append(ident)
    for axis in (0, 1):
        candidates = [drawings[ident] for ident in ids[axis] if ident in drawings]
        if len(candidates) > 1 or any(not isinstance(item, pcbnew.PCB_DIM_ALIGNED) for item in candidates):
            raise DimensionError('管理用の寸法情報が一致しません。寸法線の重複を確認してください。')
        if candidates:
            found[axis] = candidates[0]
    for group in board.Groups():
        if group.GetName() not in GROUP_NAMES:
            continue
        axis = GROUP_NAMES.index(group.GetName())
        members = list(group.GetItemsDeque())
        if len(members) != 1:
            raise DimensionError('管理用の寸法グループは寸法線1個だけにしてください。')
        item = drawings.get(members[0].m_Uuid.AsString())
        if not isinstance(item, pcbnew.PCB_DIM_ALIGNED):
            raise DimensionError('管理用の寸法グループの内容が変更されています。')
        if axis in found and found[axis].m_Uuid.AsString() != item.m_Uuid.AsString():
            raise DimensionError('管理用の寸法グループが重複しています。')
        found[axis] = item
    for item in board.GetDrawings():
        if isinstance(item, pcbnew.PCB_DIM_ALIGNED) and item.GetLayer() == pcbnew.Dwgs_User:
            prefix = item.GetPrefix()
            if prefix in PREFIXES:
                axis = PREFIXES.index(prefix)
                if axis in found and found[axis].m_Uuid.AsString() != item.m_Uuid.AsString():
                    raise DimensionError('SBD寸法が重複しています。重複した寸法線を削除してください。')
                found[axis] = item
    return found


def sync_dimensions(board, bounds):
    dimensions = find_dimensions(board)
    for axis in (0, 1):
        item = dimensions.get(axis)
        if item is None:
            item = pcbnew.PCB_DIM_ALIGNED(board)
            item.SetUuid(pcbnew.KIID(UUID_PREFIXES[axis] + str(uuid.uuid4())[21:]))
            item.SetLayer(pcbnew.Dwgs_User)
            item.SetUnitsMode(pcbnew.DIM_UNITS_MODE_MM)
            item.SetUnitsFormat(pcbnew.DIM_UNITS_FORMAT_BARE_SUFFIX)
            item.SetPrecision(pcbnew.DIM_PRECISION_X_XXX)
            item.SetSuppressZeroes(True)
            item.SetTextSize(pcbnew.VECTOR2I_MM(1.5, 1.5))
            item.SetTextThickness(pcbnew.FromMM(0.2))
            item.SetLineThickness(pcbnew.FromMM(0.15))
            item.SetArrowLength(pcbnew.FromMM(1.2))
            item.SetExtensionOffset(pcbnew.FromMM(1))
            item.SetHeight(pcbnew.FromMM(-8))
            board.Add(item)
            dimensions[axis] = item
        if not item.m_Uuid.AsString().startswith(UUID_PREFIXES[axis]):
            item.SetUuid(pcbnew.KIID(UUID_PREFIXES[axis] + str(uuid.uuid4())[21:]))
        item.SetPrefix('')
        item.SetSuffix('')
        # Keep the user's dimension-line offset, but reattach its endpoints.
        start = (bounds.left, bounds.top) if axis == 0 else (bounds.right, bounds.top)
        end = (bounds.right, bounds.top) if axis == 0 else (bounds.right, bounds.bottom)
        item.SetStart(pcbnew.VECTOR2I(*start))
        item.SetEnd(pcbnew.VECTOR2I(*end))
        item.SetOverrideTextEnabled(False)
        item.Update()
    # Migrate the unpublished grouped prototype without leaving a visible group label.
    for group in list(board.Groups()):
        if group.GetName() in GROUP_NAMES:
            group.RemoveAll()
            board.Remove(group)
    return dimensions


def find_editor_frame():
    frames = [w for w in wx.GetTopLevelWindows()
              if isinstance(w, wx.Frame) and w.GetMenuBar() is not None]
    # The footprint editor can coexist with the PCB editor in the same process.
    pcb = [w for w in frames if 'pcb' in w.GetName().lower()]
    if len(pcb) == 1:
        return pcb[0]
    if len(frames) == 1:
        return frames[0]
    raise DimensionError('PCBエディターのウィンドウを特定できません。')


def find_action_menu(frame, name):
    def scan(menu):
        for item in menu.GetMenuItems():
            if item.GetItemLabelText() == name:
                return item.GetId()
            if item.GetSubMenu():
                result = scan(item.GetSubMenu())
                if result is not None:
                    return result
        return None
    bar = frame.GetMenuBar()
    for index in range(bar.GetMenuCount()):
        result = scan(bar.GetMenu(index))
        if result is not None:
            return result
    raise DimensionError('プラグインのメニューが見つかりません。ツールの外部プラグインから起動してください。')


class CanvasFilter(wx.EventFilter):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.press = None

    def FilterEvent(self, event):
        session = self.session
        if session.closed or pcbnew.IsActionRunning():
            return self.Event_Skip
        kind = event.GetEventType()
        double_click = kind == wx.EVT_LEFT_DCLICK.typeId
        click_down = kind == wx.EVT_LEFT_DOWN.typeId
        click_up = kind == wx.EVT_LEFT_UP.typeId
        edit_key = kind == wx.EVT_CHAR_HOOK.typeId and event.GetKeyCode() in (ord('E'), ord('e'))
        if not (double_click or edit_key or click_down or click_up):
            return self.Event_Skip
        if edit_key and (event.ControlDown() or event.AltDown() or event.ShiftDown()):
            return self.Event_Skip
        # Never intercept text entry, property dialogs, another editor, or tool windows.
        target = event.GetEventObject()
        if not isinstance(target, wx.Window):
            return self.Event_Skip
        focus = wx.Window.FindFocus()
        if edit_key and isinstance(focus, (wx.TextCtrl, wx.ComboBox, wx.SpinCtrl)):
            return self.Event_Skip
        if wx.GetTopLevelParent(target) != session.editor:
            return self.Event_Skip
        if (click_up or click_down or double_click) and 'canvas' not in target.GetName().lower():
            return self.Event_Skip
        if click_down:
            self.press = event.GetPosition()
            return self.Event_Skip
        if click_up:
            start, self.press = self.press, None
            end = event.GetPosition()
            if (start is not None and abs(end.x-start.x) <= 3 and abs(end.y-start.y) <= 3
                    and not (event.ControlDown() or event.ShiftDown() or event.AltDown())):
                # Let KiCad finish picking the item before examining its selection.
                wx.CallLater(50, session.edit_selected)
            return self.Event_Skip
        try:
            axis = session.selected_axis()
            if axis is not None:
                session.request(axis)
                return self.Event_Processed
        except (RuntimeError, DimensionError):
            # A board may have closed or been replaced between native events.
            pass
        return self.Event_Skip


class DirectSession:
    def __init__(self, board, plugin_name, show=True):
        self.editor = find_editor_frame()
        self.menu_id = find_action_menu(self.editor, plugin_name)
        self.board_token = int(board.this)
        self.pending = None
        self.closed = False
        self.window = wx.Frame(self.editor, title='スマート基板寸法 · PCB上で編集',
                               style=wx.CAPTION | wx.CLOSE_BOX | wx.FRAME_TOOL_WINDOW | wx.FRAME_FLOAT_ON_PARENT)
        panel = wx.Panel(self.window)
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(panel, label='PCB上の寸法数値をクリック → 数値・計算式 → Enter'), 0, wx.ALL, 10)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(panel, label='固定点'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.anchor = wx.Choice(panel, choices=list(ANCHORS))
        self.anchor.SetSelection(0)
        row.Add(self.anchor, 0, wx.RIGHT, 10)
        for axis, label in ((0, '幅 W'), (1, '高さ H')):
            button = wx.Button(panel, label=label)
            button.Bind(wx.EVT_BUTTON, lambda event, axis=axis: self.request(axis))
            row.Add(button, 0, wx.RIGHT, 6)
        self.more = wx.Button(panel, label='詳細・更新')
        self.more.Bind(wx.EVT_BUTTON, lambda event: self.request('details'))
        row.Add(self.more, 0)
        layout.Add(row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        panel.SetSizer(layout)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.window.SetSizerAndFit(outer)
        point = self.editor.GetPosition()
        self.window.SetPosition((point.x + self.editor.GetSize().width - self.window.GetSize().width - 25,
                                 point.y + 115))
        self.window.Bind(wx.EVT_CLOSE, self._close)
        self.window.Bind(wx.EVT_WINDOW_DESTROY, self._destroyed)
        self.filter = CanvasFilter(self)
        wx.EvtHandler.AddFilter(self.filter)
        if show:
            self.window.Show()

    def matches(self, board):
        return not self.closed and board is not None and int(board.this) == self.board_token

    def selected_axis(self):
        board = pcbnew.GetBoard()
        if not self.matches(board):
            return None
        selected = pcbnew.GetCurrentSelection()
        dimensions = find_dimensions(board)
        lookup = {item.m_Uuid.AsString(): axis for axis, item in dimensions.items()}
        for group in board.Groups():
            if group.GetName() in GROUP_NAMES:
                lookup[group.m_Uuid.AsString()] = GROUP_NAMES.index(group.GetName())
        axes = {lookup.get(item.m_Uuid.AsString()) for item in selected}
        if len(axes) == 1 and None not in axes:
            return next(iter(axes))
        from .driving import find_selected
        dimension = find_selected(board, list(selected))
        return ('dimension', dimension.m_Uuid.AsString()) if dimension else None

    def edit_selected(self):
        if self.closed or self.pending is not None or pcbnew.IsActionRunning():
            return
        try:
            axis = self.selected_axis()
            if axis is not None:
                self.request(axis)
        except (RuntimeError, DimensionError):
            pass

    def request(self, operation):
        if self.pending is not None or not self.matches(pcbnew.GetBoard()):
            return
        self.pending = operation
        # Dispatch through PCB_EDIT_FRAME::OnActionPluginMenu. Calling Run() directly
        # here would bypass KiCad's undo snapshot and rebuilding of the canvas.
        wx.PostEvent(self.editor, wx.CommandEvent(wx.EVT_MENU.typeId, self.menu_id))

    def _close(self, _event):
        self.close()

    def _destroyed(self, event):
        if event.GetEventObject() == self.window and not self.closed:
            self.closed = True
            wx.EvtHandler.RemoveFilter(self.filter)
        event.Skip()

    def close(self):
        if not self.closed:
            self.closed = True
            wx.EvtHandler.RemoveFilter(self.filter)
            self.window.Destroy()

    def edit_value(self, before, axis):
        current = before.width if axis == 0 else before.height
        name = '横幅 W' if axis == 0 else '縦幅 H'
        dialog = wx.TextEntryDialog(self.editor,
            f'{name} (mm) を入力してください。数式・単位も使えます。\n例：2*35、1in+5mm',
            f'{name}を変更 · {ANCHORS[self.anchor.GetSelection()]}', fmt_iu(current))
        def select_input():
            if not dialog:
                return
            children = list(dialog.GetChildren())
            while children:
                child = children.pop()
                if isinstance(child, wx.TextCtrl):
                    child.SetFocus()
                    child.SelectAll()
                    return
                children.extend(child.GetChildren())
        wx.CallAfter(select_input)
        try:
            while dialog.ShowModal() == wx.ID_OK:
                try:
                    return resize_bounds(before, axis, dialog.GetValue(), self.anchor.GetSelection())
                except (DimensionError, ValueError) as exc:
                    wx.MessageBox(str(exc), '寸法を確認してください', wx.OK | wx.ICON_WARNING, dialog)
            return None
        finally:
            dialog.Destroy()
