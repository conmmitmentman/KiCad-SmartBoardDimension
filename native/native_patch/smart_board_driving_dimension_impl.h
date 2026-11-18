// KiCad 10 native driving dimensions, based on the supplied prototype.
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <set>
#include <vector>
#include <base_units.h>
#include <board.h>
#include <board_commit.h>
#include <pcb_dimension.h>
#include <pcb_shape.h>
#include "smartboard-rust-core/include/sbd_rust.h"

namespace SMART_BOARD_NATIVE
{
inline SbdPoint rustPoint( const VECTOR2I& p ) { return { p.x, p.y }; }
inline VECTOR2I nativePoint( SbdPoint p ) { return { p.x, p.y }; }
struct RECT_GEOMETRY
{
    int left = 0, right = 0, top = 0, bottom = 0;
    std::array<PCB_SHAPE*, 4> shapes{};
    std::size_t shapeCount = 0;

    int findCorner( const VECTOR2I& p, bool snapped = true ) const
    {
        return sbd_rect_corner( { left, right, top, bottom }, rustPoint( p ), snapped ? 1 : 0 );
    }

    VECTOR2I moveCorner( const VECTOR2I& p, bool width, int newMax ) const
    {
        SbdPoint moved = rustPoint( p );
        sbd_rect_move_corner( { left, right, top, bottom }, rustPoint( p ), width ? 0 : 1, newMax, &moved );
        return nativePoint( moved );
    }
};

inline bool linearDimension( const PCB_DIMENSION_BASE* dim )
{
    return dim && ( dim->Type() == PCB_DIM_ALIGNED_T || dim->Type() == PCB_DIM_ORTHOGONAL_T );
}

inline bool safeDimensionSpan( const VECTOR2I& start, const VECTOR2I& end )
{
    return sbd_safe_dimension_span( rustPoint( start ), rustPoint( end ) ) != 0;
}

inline bool collectRectangle( BOARD* board, RECT_GEOMETRY& out, wxString& message )
{
    out = RECT_GEOMETRY();
    for( BOARD_ITEM* item : board->Drawings() )
    {
        if( item->GetLayer() != Edge_Cuts ) continue;
        auto* shape = dynamic_cast<PCB_SHAPE*>( item );
        if( !shape ) { message = wxS( "Edge.Cutsに対応しない図形があります。" ); return false; }
        if( out.shapeCount == out.shapes.size() )
        {
            message = wxS( "軸に平行な長方形1個、または接続した直線4本に対応します。" );
            return false;
        }
        out.shapes[out.shapeCount++] = shape;
    }
    const bool rectangle = out.shapeCount == 1 && out.shapes[0]->GetShape() == SHAPE_T::RECTANGLE;
    if( !rectangle && out.shapeCount != 4 )
    {
        message = wxS( "軸に平行な長方形1個、または接続した直線4本に対応します。" );
        return false;
    }
    std::array<SbdPoint, 8> points{};
    std::size_t pointCount = 0;
    if( rectangle )
    {
        const auto corners = out.shapes[0]->GetRectCorners();
        if( corners.size() != 4 )
        { message = wxS( "軸に平行な長方形が必要です。" ); return false; }
        for( const VECTOR2I& p : corners ) points[pointCount++] = rustPoint( p );
    }
    else
        for( PCB_SHAPE* shape : out.shapes )
        {
            if( shape->GetShape() != SHAPE_T::SEGMENT )
            { message = wxS( "円弧・多角形を含む外形には対応していません。" ); return false; }
            points[pointCount++] = rustPoint( shape->GetStart() );
            points[pointCount++] = rustPoint( shape->GetEnd() );
        }
    SbdRect geometry{};
    if( sbd_rect_from_vertices( points.data(), pointCount, rectangle ? 0 : 1, &geometry ) != SBD_OK )
    {
        message = wxS( "座標範囲±2000 mm・幅高さ0.01～2000 mmの、隙間や重複のない長方形が必要です。" );
        return false;
    }
    out.left = geometry.left; out.right = geometry.right;
    out.top = geometry.top; out.bottom = geometry.bottom;
    return true;
}

inline int dimensionAxis( const RECT_GEOMETRY& rect, const PCB_DIMENSION_BASE* dim )
{
    if( !linearDimension( dim ) ) return -1;
    return sbd_rect_axis( { rect.left, rect.right, rect.top, rect.bottom },
                         rustPoint( dim->GetStart() ), rustPoint( dim->GetEnd() ), dim->GetMeasuredValue() );
}

inline bool parseMillimetres( const wxString& text, double& value )
{
    if( text.size() > 256 ) return false;
    const auto utf8 = text.ToUTF8();
    return sbd_parse_mm( reinterpret_cast<const uint8_t*>( utf8.data() ), utf8.length(), &value ) == SBD_OK;
}

// Validate the entire change before touching the board. The caller owns the undo transaction.
inline bool resizeRectangle( BOARD* board, PCB_DIMENSION_BASE* edited, double targetMM,
                             BOARD_COMMIT& commit, wxString& message )
{
    if( !std::isfinite( targetMM ) || targetMM < 0.01 || targetMM > 1000.0 )
    { message = wxS( "寸法は0.01～1000 mm以内で入力してください。" ); return false; }
    RECT_GEOMETRY rect;
    if( !collectRectangle( board, rect, message ) ) return false;
    int axis = dimensionAxis( rect, edited );
    if( axis < 0 )
    { message = wxS( "寸法の両端を長方形の隣り合う2つの角に合わせてください。" ); return false; }
    bool width = axis == 0;
    int32_t newMax = 0;
    if( sbd_rect_target_max( { rect.left, rect.right, rect.top, rect.bottom }, axis, targetMM, &newMax ) != SBD_OK )
    { message = wxS( "変更後の外形が座標範囲±2000 mmを超えます。" ); return false; }
    std::vector<PCB_DIMENSION_BASE*> dimensions;
    for( BOARD_ITEM* item : board->Drawings() )
    {
        auto* dim = dynamic_cast<PCB_DIMENSION_BASE*>( item );
        if( !linearDimension( dim ) || ( rect.findCorner( dim->GetStart() ) < 0
            && rect.findCorner( dim->GetEnd() ) < 0 ) ) continue;
        if( !safeDimensionSpan( rect.moveCorner( dim->GetStart(), width, newMax ),
                                rect.moveCorner( dim->GetEnd(), width, newMax ) ) )
        { message = wxS( "追従する寸法の長さが2000 mmを超えます。" ); return false; }
        if( dim->IsLocked() && ( dim == edited
            || rect.moveCorner( dim->GetStart(), width, newMax ) != dim->GetStart()
            || rect.moveCorner( dim->GetEnd(), width, newMax ) != dim->GetEnd() ) )
        { message = wxS( "追従する寸法がロックされています。先にロックを解除してください。" ); return false; }
        dimensions.push_back( dim );
    }
    for( std::size_t i = 0; i < rect.shapeCount; ++i )
        if( rect.shapes[i]->IsLocked() )
        { message = wxS( "基板外形がロックされています。先にロックを解除してください。" ); return false; }
    for( std::size_t i = 0; i < rect.shapeCount; ++i )
    {
        PCB_SHAPE* shape = rect.shapes[i];
        commit.Modify( shape );
        shape->SetStart( rect.moveCorner( shape->GetStart(), width, newMax ) );
        shape->SetEnd( rect.moveCorner( shape->GetEnd(), width, newMax ) );
    }
    for( PCB_DIMENSION_BASE* dim : dimensions )
    {
        commit.Modify( dim );
        dim->SetStart( rect.moveCorner( dim->GetStart(), width, newMax ) );
        dim->SetEnd( rect.moveCorner( dim->GetEnd(), width, newMax ) );
        if( dim == edited ) dim->SetOverrideTextEnabled( false );
        dim->Update();
    }
    return true;
}
} // namespace SMART_BOARD_NATIVE

#include "smart_board_driving_circle.h"

