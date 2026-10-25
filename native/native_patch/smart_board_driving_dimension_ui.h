// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "smart_board_driving_dimension_impl.h"
#include <pcb_base_edit_frame.h>
#include <wx/dialog.h>
#include <wx/textctrl.h>
#include <wx/stattext.h>
#include <wx/sizer.h>
#include <wx/display.h>
#include <wx/utils.h>

namespace SMART_BOARD_NATIVE
{
// Called from the native selection tool only after an unmodified click on dimension text.
inline bool editOnCanvas( PCB_BASE_EDIT_FRAME* frame, PCB_DIMENSION_BASE* dim )
{
    RECT_GEOMETRY rect;
    wxString error;
    if( dim->IsLocked() || !collectRectangle( frame->GetBoard(), rect, error ) ) return false;
    const int axis = dimensionAxis( rect, dim );
    if( axis < 0 ) return false;

    wxDialog popup( frame, wxID_ANY, wxS( "寸法を変更" ), wxDefaultPosition, wxDefaultSize,
                    wxBORDER_SIMPLE );
    auto* layout = new wxBoxSizer( wxVERTICAL );
    auto* hint = new wxStaticText( &popup, wxID_ANY,
        axis == 0 ? wxS( "幅 (mm) · 左辺固定" ) : wxS( "高さ (mm) · 上辺固定" ) );
    auto* input = new wxTextCtrl( &popup, wxID_ANY,
        wxString::Format( wxS( "%.6g" ), pcbIUScale.IUTomm( axis == 0 ? rect.right-rect.left : rect.bottom-rect.top ) ),
        wxDefaultPosition, popup.FromDIP( wxSize( 260, -1 ) ), wxTE_PROCESS_ENTER );
    auto* status = new wxStaticText( &popup, wxID_ANY, wxS( "数値・計算式 → Enter確定 / Esc取消" ) );
    layout->Add( hint, 0, wxALL, popup.FromDIP( 8 ) );
    layout->Add( input, 0, wxEXPAND | wxLEFT | wxRIGHT, popup.FromDIP( 8 ) );
    layout->Add( status, 0, wxALL, popup.FromDIP( 8 ) );
    popup.SetSizerAndFit( layout );
    wxPoint at = wxGetMousePosition() + popup.FromDIP( wxPoint( 12, 12 ) );
    int displayIndex = wxDisplay::GetFromPoint( at );
    if( displayIndex != wxNOT_FOUND )
    {
        wxRect area = wxDisplay( displayIndex ).GetClientArea();
        at.x = std::max( area.x, std::min( at.x, area.GetRight() - popup.GetSize().x ) );
        at.y = std::max( area.y, std::min( at.y, area.GetBottom() - popup.GetSize().y ) );
    }
    popup.SetPosition( at );
    input->Bind( wxEVT_TEXT_ENTER, [&]( wxCommandEvent& )
    {
        double millimetres = 0;
        if( !parseMillimetres( input->GetValue(), millimetres ) )
        {
            status->SetLabel( wxS( "0.01～1000 mmの数値・計算式を入力" ) );
            popup.Fit(); input->SetFocus(); input->SelectAll(); return;
        }
        BOARD_COMMIT commit( frame );
        if( !resizeRectangle( frame->GetBoard(), dim, millimetres, commit, error ) )
        {
            status->SetLabel( error ); status->Wrap( popup.FromDIP( 260 ) );
            popup.Fit(); return;
        }
        commit.Push( wxS( "寸法から基板外形を変更" ) );
        popup.EndModal( wxID_OK );
    } );
    popup.Bind( wxEVT_CHAR_HOOK, [&]( wxKeyEvent& event )
    {
        if( event.GetKeyCode() == WXK_ESCAPE ) popup.EndModal( wxID_CANCEL );
        else event.Skip();
    } );
    input->SetFocus(); input->SelectAll();
    popup.ShowModal();
    return true;
}
} // namespace SMART_BOARD_NATIVE
