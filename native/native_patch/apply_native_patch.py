#!/usr/bin/env python3
"""Insert experimental native driving dimensions into KiCad 10 source (not installed binaries)."""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

HEADER_ANCHOR = "    PCB_DIMENSION_BASE* m_previewDimension;"
INCLUDE_ANCHOR = '#include "dialog_dimension_properties.h"'
CTOR_ANCHOR = "    SetupStandardButtons();"
TRANSFER_ANCHOR = "    updateDimensionFromDialog( m_dimension );"


def insert_once(text: str, anchor: str, insertion: str, *, after=True) -> str:
    if text.count(anchor) != 1:
        raise RuntimeError(f"Expected one occurrence, found {text.count(anchor)}: {anchor!r}")
    return text.replace(anchor, anchor + insertion if after else insertion + anchor, 1)


def patch_pair(header: str, source: str) -> tuple[str, str]:
    marker = "SMART_BOARD_NATIVE"
    if marker in source or "m_cbDriveOutline" in header:
        raise RuntimeError("Already modified; do not patch a file twice.")

    matches = re.findall(r'^    PCB_DIMENSION_BASE\* +m_previewDimension;', header, re.M)
    if len(matches) != 1:
        raise RuntimeError('Expected one occurrence of m_previewDimension declaration')
    header = insert_once(header, matches[0],
                         "\n    wxCheckBox* m_cbDriveOutline = nullptr; // SMART_BOARD_NATIVE\n")
    source = insert_once(source, INCLUDE_ANCHOR,
                         '\n#include <wx/checkbox.h>\n'
                         '#include <base_units.h>\n'
                         '#include "smart_board_driving_dimension_impl.h" // SMART_BOARD_NATIVE\n')
    constructor_code = r'''
    // SMART_BOARD_NATIVE: opt-in directly in the built-in Dimension Properties window.
    // Object snapping during dimension placement is handled by KiCad's native drawing tool.
    if( SMART_BOARD_NATIVE::linearDimension( m_dimension ) || m_dimension->Type() == PCB_DIM_RADIAL_T )
    {
        m_cbDriveOutline = new wxCheckBox( m_sizerFormat->GetStaticBox(), wxID_ANY,
                             wxString( L"\u3053\u306e\u5bf8\u6cd5\u5024\u3067\u57fa\u677f\u5916\u5f62\u3092\u5909\u66f4\uff08mm\uff09" ) );
        m_sizerFormat->Add( m_cbDriveOutline, 0, wxLEFT | wxRIGHT | wxBOTTOM, 8 );
        m_cbDriveOutline->SetValue( false ); // prevent accidental geometry modification
        m_cbDriveOutline->Bind( wxEVT_CHECKBOX, [this]( wxCommandEvent& )
        {
            if( m_cbDriveOutline->GetValue() )
            {
                m_cbOverrideValue->SetValue( true );
                m_txtValue->Enable( true );
                m_txtValue->SetFocus();
                m_txtValue->SetValue( wxString::Format( wxS( "%.6g" ), pcbIUScale.IUTomm( m_dimension->GetMeasuredValue() ) ) );
                m_txtValue->SelectAll();
            }
        } );
    }
'''
    source = insert_once(source, CTOR_ANCHOR, constructor_code, after=False)
    transfer_code = r'''
    // SMART_BOARD_NATIVE: on OK, drive the snapped outline rather than just text override.
    if( m_cbDriveOutline && m_cbDriveOutline->GetValue() )
    {
        double millimetres = 0.0;
        if( !pushCommit || !SMART_BOARD_NATIVE::parseMillimetres( m_txtValueActual->GetValue(), millimetres ) )
        {
            wxMessageBox( wxS( "操作中は確定後に編集してください。寸法は0.01～1000 mmの数値・計算式で指定します。" ),
                          wxS( "駆動寸法" ), wxOK | wxICON_WARNING, this );
            return false;
        }
        wxString error;
        if( !SMART_BOARD_NATIVE::resizeOutline( m_frame->GetBoard(), m_dimension,
                                                   millimetres, commit, error ) )
        {
            wxMessageBox( error, wxString( L"\u99c6\u52d5\u5bf8\u6cd5" ), wxOK | wxICON_WARNING, this );
            return false;
        }
        // Re-enable measured display: the visible dimension matches actual geometry.
        m_cbOverrideValue->SetValue( false );
    }
'''
    source = insert_once(source, TRANSFER_ANCHOR, transfer_code, after=False)
    source = insert_once(source, '    BOARD_COMMIT commit( m_frame );', r'''
    if( m_cbDriveOutline && m_cbDriveOutline->GetValue() && m_dimension->GetEditFlags() != 0 )
    {
        wxMessageBox( wxS( "寸法の配置・移動を確定してから編集してください。" ),
                      wxS( "駆動寸法" ), wxOK | wxICON_WARNING, this );
        return false;
    }
''', after=False)
    return header, source


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('kicad_source', type=pathlib.Path, help='Local KiCad 10 source root')
    ap.add_argument('--dry-run', action='store_true', help='Check anchors, do not modify')
    ap.add_argument('--with-tests', action='store_true', help='Register C++ regression tests in KiCad QA')
    args = ap.parse_args()
    directory = args.kicad_source / 'pcbnew' / 'dialogs'
    header = directory / 'dialog_dimension_properties.h'
    source = directory / 'dialog_dimension_properties.cpp'
    if not header.is_file() or not source.is_file():
        ap.error('KiCad 10 source tree not found: pcbnew/dialogs/dialog_dimension_properties.{h,cpp}')
    htext, ctext = patch_pair(header.read_text(encoding='utf-8'), source.read_text(encoding='utf-8'))
    selection = args.kicad_source / 'pcbnew/tools/pcb_selection_tool.cpp'
    selection_text = selection.read_text(encoding='utf-8')
    selection_text = insert_once(selection_text, '#include <pcb_base_edit_frame.h>',
        '\n#include "../dialogs/smart_board_driving_dimension_ui.h" // SMART_BOARD_NATIVE\n')
    selection_text = insert_once(selection_text,
        '    if( aClientFilter )\n        aClientFilter( aWhere, collector, this );', r'''

    // SMART_BOARD_NATIVE: text wins over an overlapping outline, but obey visibility,
    // selection filters, modifiers and normal drag behavior.
    if( !aOnDrag && !aClientFilter && !m_isFootprintEditor && !hasModifier()
        && m_frame->ToolStackIsEmpty() )
    {
        std::set<EDA_ITEM*> drivingText;
        for( EDA_ITEM* item : collector )
        {
            auto* dim = dynamic_cast<PCB_DIMENSION_BASE*>( item );
            if( dim && dim->TextHitTest( aWhere )
                && SMART_BOARD_NATIVE::canDriveDimension( board(), dim ) )
                drivingText.insert( item );
        }
        if( !drivingText.empty() )
            for( int i = collector.GetCount() - 1; i >= 0; --i )
                if( !drivingText.count( collector[i] ) ) collector.Remove( i );
    }
''')
    selection_text = insert_once(selection_text, '                        m_previousFirstCell = singleSelectedCell();', r"""
                        // SMART_BOARD_NATIVE: normal selection remains available on lines/handles.
                        if( brd_editor && !hasModifier() && m_frame->ToolStackIsEmpty()
                            && m_selection.GetSize() == 1 )
                        {
                            auto* dim = dynamic_cast<PCB_DIMENSION_BASE*>( m_selection[0] );
                            if( dim && dim->TextHitTest( evt->Position() )
                                && SMART_BOARD_NATIVE::editOnCanvas(
                                    static_cast<PCB_BASE_EDIT_FRAME*>( frame ), dim ) )
                            {
                                ClearSelection(); // allow another text click without point handles
                                m_frame->GetCanvas()->SetFocus(); // restore save/undo shortcuts
                            }
                        }
""")
    outputs = {header: htext, source: ctext, selection: selection_text}
    payload = pathlib.Path(__file__).parent
    for name in ('smart_board_driving_dimension_impl.h', 'smart_board_driving_dimension_ui.h', 'smart_board_driving_circle.h'):
        target = directory / name
        if target.exists():
            raise RuntimeError(f'Additional header already exists: {target}')
        outputs[target] = (payload / name).read_text(encoding='utf-8')
    if args.with_tests:
        cmake = args.kicad_source / 'qa/tests/pcbnew/CMakeLists.txt'
        outputs[cmake] = insert_once(cmake.read_text(encoding='utf-8'), '    test_board_commit.cpp', '\n    test_smart_board_driving_dimension.cpp')
        test = cmake.parent / 'test_smart_board_driving_dimension.cpp'
        if test.exists():
            raise RuntimeError(f'Test already exists: {test}')
        outputs[test] = (payload / test.name).read_text(encoding='utf-8')
    if args.dry_run:
        print('OK: KiCad dialog and canvas anchors match; no files changed.')
        return
    originals = {f: f.read_bytes() if f.exists() else None for f in outputs}
    for f, original in originals.items():
        if original is not None and f.with_suffix(f.suffix + '.smartboard-original').exists():
            raise RuntimeError(f'Backup already exists for {f}')
    try:
        for f, original in originals.items():
            if original is not None:
                f.with_suffix(f.suffix + '.smartboard-original').write_bytes(original)
        for f, text in outputs.items():
            f.write_text(text, encoding='utf-8', newline='\n')
    except OSError:
        for f, original in originals.items():
            if original is None:
                f.unlink(missing_ok=True)
            else:
                f.write_bytes(original)
        raise
    print('Applied native dimension dialog and single-click canvas editing. Originals backed up.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError) as e:
        sys.exit(f'Error: {e}')
