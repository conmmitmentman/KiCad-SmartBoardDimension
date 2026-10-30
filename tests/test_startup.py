"""Lifecycle and transaction dispatch tests with mocks, no KiCad or wx runtime."""
import sys
import types
import unittest
from unittest.mock import Mock, patch
from test_plugin_mock import mod, Board


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.original = mod._direct_session
        mod._direct_session = None

    def tearDown(self):
        mod._direct_session = self.original

    def test_startup_attaches_without_creating_or_modifying_items(self):
        board = Board()
        session = Mock()
        direct = types.SimpleNamespace(DirectSession=Mock(return_value=session))
        with patch.dict(sys.modules, {'smart_board_dimension.direct_editor': direct}), \
                patch.object(mod.pcbnew, 'GetBoard', return_value=board, create=True), \
                patch.object(mod.wx, 'GetApp', return_value=object(), create=True), \
                patch.object(mod.wx, 'CallLater', create=True) as later:
            mod._attach_when_ready()
            direct.DirectSession.assert_called_once_with(board, mod._plugin.name, show=False)
            self.assertEqual(board.GetDrawings(), [])
            later.assert_called_once_with(1500, mod._attach_when_ready)

    def test_missing_editor_retries_without_mutation(self):
        board = Board()
        direct = types.SimpleNamespace(DirectSession=Mock(side_effect=mod.DimensionError('not ready')))
        with patch.dict(sys.modules, {'smart_board_dimension.direct_editor': direct}), \
                patch.object(mod.pcbnew, 'GetBoard', return_value=board, create=True), \
                patch.object(mod.wx, 'GetApp', return_value=object(), create=True), \
                patch.object(mod.wx, 'CallLater', create=True) as later:
            mod._attach_when_ready()
            self.assertIsNone(mod._direct_session)
            self.assertEqual(board.GetDrawings(), [])
            later.assert_called_once()

    def test_board_switch_closes_old_listener(self):
        old=Mock(); old.matches.return_value=False
        mod._direct_session=old
        direct=types.SimpleNamespace(DirectSession=Mock())
        with patch.dict(sys.modules, {'smart_board_dimension.direct_editor': direct}), \
                patch.object(mod.pcbnew, 'GetBoard', return_value=None, create=True), \
                patch.object(mod.wx, 'GetApp', return_value=None, create=True):
            mod._attach_when_ready()
        old.close.assert_called_once()
        direct.DirectSession.assert_not_called()

    def test_standard_edit_is_dispatched_from_plugin_run(self):
        item=Mock(); item.m_Uuid.AsString.return_value='dimension-id'
        board=Board([item])
        session=Mock(pending=('dimension','dimension-id'))
        session.matches.return_value=True
        mod._direct_session=session
        direct=types.SimpleNamespace(DirectSession=Mock(), find_dimensions=Mock(), sync_dimensions=Mock())
        with patch.dict(sys.modules, {'smart_board_dimension.direct_editor': direct}), \
                patch.object(mod.pcbnew, 'GetBoard', return_value=board, create=True), \
                patch('smart_board_dimension.driving.edit_dialog') as edit:
            mod._plugin.Run()
            edit.assert_called_once_with(board,item,session.editor)
            direct.sync_dimensions.assert_not_called()
            self.assertIsNone(session.pending)
