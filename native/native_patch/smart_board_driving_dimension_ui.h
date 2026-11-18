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
    CIRCLE_GEOMETRY circle;
    wxString error;
    if( dim->IsLocked() || dim->GetEditFlags() != 0 ) return false;
    wxString label;
    double currentMM = 0;
    if( collectCircle( frame->GetBoard(), circle, error ) )
    {
        const int factor = circleDimensionFactor( circle, dim );
        if( !factor ) return false;
        label = factor == 1
                ? dimensionText( wxS( "Radius (mm) · center fixed" ), wxS( "半径 (mm) · 中心固定" ) )
                : dimensionText( wxS( "Diameter (mm) · center fixed" ), wxS( "直径 (mm) · 中心固定" ) );
        currentMM = circle.radius * factor / pcbIUScale.IU_PER_MM;
    }
    else
    {
        if( !collectRectangle( frame->GetBoard(), rect, error ) ) return false;
        const int axis = dimensionAxis( rect, dim );
        if( axis < 0 ) return false;
        label = axis == 0
                ? dimensionText( wxS( "Width (mm) · left edge fixed" ), wxS( "幅 (mm) · 左辺固定" ) )
                : dimensionText( wxS( "Height (mm) · top edge fixed" ), wxS( "高さ (mm) · 上辺固定" ) );
        currentMM = pcbIUScale.IUTomm( axis == 0 ? rect.right-rect.left : rect.bottom-rect.top );
    }

    wxDialog popup( frame, wxID_ANY, dimensionText(
            wxS( "Change dimension" ),
            wxS( "寸法を変更" ) ), wxDefaultPosition, wxDefaultSize,
                    wxBORDER_SIMPLE );
    auto* layout = new wxBoxSizer( wxVERTICAL );
    auto* hint = new wxStaticText( &popup, wxID_ANY, label );
    auto* input = new wxTextCtrl( &popup, wxID_ANY,
        wxString::Format( wxS( "%.6g" ), currentMM ),
        wxDefaultPosition, popup.FromDIP( wxSize( 260, -1 ) ), wxTE_PROCESS_ENTER );
    auto* status = new wxStaticText( &popup, wxID_ANY, dimensionText(
            wxS( "Number or formula. Enter to apply / Esc to cancel." ),
            wxS( "数値・計算式 → Enter確定 / Esc取消" ) ) );
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
            status->SetLabel( dimensionText(
                    wxS( "Enter a number or formula between 0.01 and 1000 mm" ),
                    wxS( "0.01～1000 mmの数値・計算式を入力" ) ) );
            status->Wrap( popup.FromDIP( 260 ) );
            popup.Fit(); input->SetFocus(); input->SelectAll(); return;
        }
        BOARD_COMMIT commit( frame );
        if( !resizeOutline( frame->GetBoard(), dim, millimetres, commit, error ) )
        {
            status->SetLabel( error ); status->Wrap( popup.FromDIP( 260 ) );
            popup.Fit(); return;
        }
        commit.Push( dimensionText( wxS( "Resize board outline from dimension" ), wxS( "寸法から基板外形を変更" ) ) );
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
