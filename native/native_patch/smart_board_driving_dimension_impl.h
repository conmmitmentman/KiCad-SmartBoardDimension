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
#include <libeval/numeric_evaluator.h>

namespace SMART_BOARD_NATIVE
{
struct RECT_GEOMETRY
{
    int left = 0, right = 0, top = 0, bottom = 0;
    std::vector<PCB_SHAPE*> shapes;

    VECTOR2I corner( int i ) const
    {
        return { ( i & 1 ) ? right : left, ( i & 2 ) ? bottom : top };
    }

    int findCorner( const VECTOR2I& p, bool snapped = true ) const
    {
        // Keep distinct corners distinguishable even for very small rectangles.
        const int tolerance = snapped ? static_cast<int>( std::min<long long>(
                pcbIUScale.mmToIU( 0.01 ), std::min( static_cast<long long>( right ) - left,
                                                   static_cast<long long>( bottom ) - top ) / 4 ) ) : 0;
        for( int i = 0; i < 4; ++i )
        {
            VECTOR2I q = corner( i );
            if( std::abs( static_cast<long long>( p.x ) - q.x ) <= tolerance
                && std::abs( static_cast<long long>( p.y ) - q.y ) <= tolerance )
                return i;
        }
        return -1;
    }

    VECTOR2I moveCorner( const VECTOR2I& p, bool width, int newMax ) const
    {
        int i = findCorner( p );
        if( i < 0 ) return p;
        VECTOR2I q = corner( i );
        if( width && ( i & 1 ) ) q.x = newMax;
        if( !width && ( i & 2 ) ) q.y = newMax;
        return q;
    }
};

inline bool linearDimension( const PCB_DIMENSION_BASE* dim )
{
    return dim && ( dim->Type() == PCB_DIM_ALIGNED_T || dim->Type() == PCB_DIM_ORTHOGONAL_T );
}

inline bool safeDimensionSpan( const VECTOR2I& start, const VECTOR2I& end )
{
    // KiCad dimension geometry subtracts integer vectors and rounds the measured length to int.
    return std::hypot( static_cast<double>( end.x ) - start.x,
                       static_cast<double>( end.y ) - start.y ) <= pcbIUScale.mmToIU( 2000.0 );
}

inline bool collectRectangle( BOARD* board, RECT_GEOMETRY& out, wxString& message )
{
    out = RECT_GEOMETRY();
    for( BOARD_ITEM* item : board->Drawings() )
    {
        if( item->GetLayer() != Edge_Cuts ) continue;
        auto* shape = dynamic_cast<PCB_SHAPE*>( item );
        if( !shape ) { message = wxS( "Edge.Cutsに対応しない図形があります。" ); return false; }
        out.shapes.push_back( shape );
    }
    const bool rectangle = out.shapes.size() == 1 && out.shapes[0]->GetShape() == SHAPE_T::RECTANGLE;
    if( !rectangle && out.shapes.size() != 4 )
    {
        message = wxS( "軸に平行な長方形1個、または接続した直線4本に対応します。" );
        return false;
    }
    std::vector<VECTOR2I> vertices;
    if( rectangle ) vertices = out.shapes[0]->GetRectCorners();
    else
        for( PCB_SHAPE* shape : out.shapes )
        {
            if( shape->GetShape() != SHAPE_T::SEGMENT )
            { message = wxS( "円弧・多角形を含む外形には対応していません。" ); return false; }
            vertices.push_back( shape->GetStart() );
            vertices.push_back( shape->GetEnd() );
        }
    if( vertices.empty() ) return false;
    out.left = out.right = vertices[0].x;
    out.top = out.bottom = vertices[0].y;
    const long long limit = pcbIUScale.mmToIU( 2000.0 );
    for( const VECTOR2I& p : vertices )
    {
        if( std::abs( static_cast<long long>( p.x ) ) > limit
            || std::abs( static_cast<long long>( p.y ) ) > limit )
        { message = wxS( "外形の座標は±2000 mm以内にしてください。" ); return false; }
        out.left = std::min( out.left, p.x ); out.right = std::max( out.right, p.x );
        out.top = std::min( out.top, p.y ); out.bottom = std::max( out.bottom, p.y );
    }
    const long long w = static_cast<long long>( out.right ) - out.left;
    const long long h = static_cast<long long>( out.bottom ) - out.top;
    if( w < pcbIUScale.mmToIU( 0.01 ) || h < pcbIUScale.mmToIU( 0.01 )
        || w > pcbIUScale.mmToIU( 2000 ) || h > pcbIUScale.mmToIU( 2000 ) )
    { message = wxS( "外形の幅・高さは0.01～2000 mm以内にしてください。" ); return false; }
    if( rectangle )
    {
        std::set<int> corners;
        for( const VECTOR2I& p : vertices ) corners.insert( out.findCorner( p, false ) );
        if( corners == std::set<int>{ 0, 1, 2, 3 } ) return true;
    }
    else
    {
        std::set<std::pair<int,int>> edges;
        std::array<int,4> degree{};
        for( PCB_SHAPE* shape : out.shapes )
        {
            int a = out.findCorner( shape->GetStart(), false );
            int b = out.findCorner( shape->GetEnd(), false );
            if( a < 0 || b < 0 || ( ( a ^ b ) != 1 && ( a ^ b ) != 2 ) ) break;
            edges.insert( std::minmax( a, b ) ); ++degree[a]; ++degree[b];
        }
        if( edges.size() == 4 && std::all_of( degree.begin(), degree.end(), []( int n ){ return n == 2; } ) )
            return true;
    }
    message = wxS( "回転・隙間・重複のない長方形外形が必要です。" );
    return false;
}

inline int dimensionAxis( const RECT_GEOMETRY& rect, const PCB_DIMENSION_BASE* dim )
{
    if( !linearDimension( dim ) ) return -1;
    int a = rect.findCorner( dim->GetStart() ), b = rect.findCorner( dim->GetEnd() );
    if( a < 0 || b < 0 ) return -1;
    int axis = ( a ^ b ) == 1 ? 0 : ( a ^ b ) == 2 ? 1 : -1;
    // An orthogonal dimension may project onto the wrong axis and measure zero.
    if( axis < 0 || dim->GetMeasuredValue() <= 0 ) return -1;
    return axis;
}

inline bool parseMillimetres( const wxString& text, double& value )
{
    if( text.size() > 256 ) return false;
    NUMERIC_EVALUATOR evaluator( EDA_UNITS::MM );
    return evaluator.Process( text ) && evaluator.Result().ToDouble( &value )
           && std::isfinite( value ) && value >= 0.01 && value <= 1000.0;
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
    long long targetEnd = static_cast<long long>( width ? rect.left : rect.top ) + pcbIUScale.mmToIU( targetMM );
    if( std::abs( targetEnd ) > pcbIUScale.mmToIU( 2000.0 ) )
    { message = wxS( "変更後の外形が座標範囲±2000 mmを超えます。" ); return false; }
    int newMax = static_cast<int>( targetEnd );
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
    for( PCB_SHAPE* shape : rect.shapes )
        if( shape->IsLocked() )
        { message = wxS( "基板外形がロックされています。先にロックを解除してください。" ); return false; }
    for( PCB_SHAPE* shape : rect.shapes )
    {
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
