// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

// Included after the rectangle helpers. Uses KiCad geometry; no SolidCraft code.
namespace SMART_BOARD_NATIVE
{
struct CIRCLE_GEOMETRY
{
    PCB_SHAPE* shape = nullptr;
    VECTOR2I center;
    double radius = 0;

    double distance( const VECTOR2I& p ) const
    {
        return std::hypot( static_cast<double>( p.x ) - center.x,
                           static_cast<double>( p.y ) - center.y );
    }

    double tolerance() const { return std::min( 10000.0, radius / 4.0 ); }
    bool onCircle( const VECTOR2I& p ) const
    {
        return std::abs( distance( p ) - radius ) <= tolerance();
    }

    VECTOR2I scaledPoint( const VECTOR2I& p, double newRadius ) const
    {
        if( !onCircle( p ) ) return p;
        const double scale = newRadius / distance( p );
        return { static_cast<int>( std::llround( center.x + ( static_cast<double>( p.x ) - center.x ) * scale ) ),
                 static_cast<int>( std::llround( center.y + ( static_cast<double>( p.y ) - center.y ) * scale ) ) };
    }
};

inline bool collectCircle( BOARD* board, CIRCLE_GEOMETRY& out, wxString& message )
{
    out = CIRCLE_GEOMETRY();
    for( BOARD_ITEM* item : board->Drawings() )
    {
        if( item->GetLayer() != Edge_Cuts ) continue;
        auto* shape = dynamic_cast<PCB_SHAPE*>( item );
        if( out.shape || !shape || shape->GetShape() != SHAPE_T::CIRCLE )
        { message = wxS( "円形外形はEdge.Cutsの円1個に対応します。" ); return false; }
        out.shape = shape;
    }
    if( !out.shape ) return false;
    out.center = out.shape->GetStart();
    out.radius = out.distance( out.shape->GetEnd() );
    const double limit = pcbIUScale.mmToIU( 2000.0 );
    if( out.radius < pcbIUScale.mmToIU( 0.005 ) || out.radius > pcbIUScale.mmToIU( 1000.0 )
        || std::abs( static_cast<double>( out.center.x ) ) + out.radius > limit
        || std::abs( static_cast<double>( out.center.y ) ) + out.radius > limit )
    { message = wxS( "円の直径は0.01～2000 mm、円全体の座標は±2000 mm以内にしてください。" ); return false; }
    return true;
}

// 1 = radius, 2 = diameter, 0 = unrelated or unsupported dimension.
inline int circleDimensionFactor( const CIRCLE_GEOMETRY& circle, const PCB_DIMENSION_BASE* dim )
{
    if( !dim ) return 0;
    if( dim->Type() == PCB_DIM_RADIAL_T )
        return circle.distance( dim->GetStart() ) <= circle.tolerance()
               && circle.onCircle( dim->GetEnd() ) ? 1 : 0;
    if( !linearDimension( dim ) || !circle.onCircle( dim->GetStart() )
        || !circle.onCircle( dim->GetEnd() ) ) return 0;
    // A chord is not a diameter. Orthogonal dimensions must measure the full diameter.
    double midpointX = ( static_cast<double>( dim->GetStart().x ) + dim->GetEnd().x ) / 2;
    double midpointY = ( static_cast<double>( dim->GetStart().y ) + dim->GetEnd().y ) / 2;
    return std::hypot( midpointX - circle.center.x, midpointY - circle.center.y ) <= circle.tolerance()
           && std::abs( static_cast<double>( dim->GetMeasuredValue() ) - 2 * circle.radius ) <= circle.tolerance()
           ? 2 : 0;
}

inline bool resizeCircle( BOARD* board, PCB_DIMENSION_BASE* edited, double targetMM,
                          BOARD_COMMIT& commit, wxString& message )
{
    if( !std::isfinite( targetMM ) || targetMM < 0.01 || targetMM > 1000.0 )
    { message = wxS( "寸法は0.01～1000 mm以内で入力してください。" ); return false; }
    CIRCLE_GEOMETRY circle;
    if( !collectCircle( board, circle, message ) ) return false;
    const int factor = circleDimensionFactor( circle, edited );
    if( !factor )
    { message = wxS( "半径寸法は中心と円周、直径寸法は円周上の向かい合う2点に合わせてください。" ); return false; }
    const double newRadius = static_cast<double>( pcbIUScale.mmToIU( targetMM ) ) / factor;
    const double limit = pcbIUScale.mmToIU( 2000.0 );
    if( std::abs( static_cast<double>( circle.center.x ) ) + newRadius > limit
        || std::abs( static_cast<double>( circle.center.y ) ) + newRadius > limit )
    { message = wxS( "変更後の円が座標範囲±2000 mmを超えます。" ); return false; }
    if( circle.shape->IsLocked() || edited->IsLocked() )
    { message = wxS( "円または寸法がロックされています。" ); return false; }
    struct CHANGE { PCB_DIMENSION_BASE* dim; VECTOR2I start, end; };
    std::vector<CHANGE> changes;
    for( BOARD_ITEM* item : board->Drawings() )
    {
        auto* dim = dynamic_cast<PCB_DIMENSION_BASE*>( item );
        if( !dim ) continue;
        VECTOR2I start = dim->GetStart(), end = dim->GetEnd();
        if( dim->Type() == PCB_DIM_RADIAL_T && circleDimensionFactor( circle, dim ) == 1 )
        {
            start = circle.center;
            end = circle.scaledPoint( end, newRadius );
        }
        else if( linearDimension( dim ) )
        {
            start = circle.scaledPoint( start, newRadius );
            end = circle.scaledPoint( end, newRadius );
        }
        else continue;
        if( dim != edited && start == dim->GetStart() && end == dim->GetEnd() ) continue;
        if( !safeDimensionSpan( start, end ) )
        { message = wxS( "追従する寸法の長さが2000 mmを超えます。" ); return false; }
        if( dim->IsLocked() )
        { message = wxS( "追従する寸法がロックされています。" ); return false; }
        changes.push_back( { dim, start, end } );
    }
    // Everything above is read-only: invalid requests cannot leave a half-edited board.
    commit.Modify( circle.shape );
    circle.shape->SetEnd( circle.scaledPoint( circle.shape->GetEnd(), newRadius ) );
    for( const CHANGE& change : changes )
    {
        commit.Modify( change.dim );
        change.dim->SetStart( change.start );
        change.dim->SetEnd( change.end );
        if( change.dim == edited ) change.dim->SetOverrideTextEnabled( false );
        change.dim->Update();
    }
    return true;
}

inline bool resizeOutline( BOARD* board, PCB_DIMENSION_BASE* edited, double targetMM,
                           BOARD_COMMIT& commit, wxString& message )
{
    CIRCLE_GEOMETRY circle;
    if( collectCircle( board, circle, message ) )
        return resizeCircle( board, edited, targetMM, commit, message );
    return resizeRectangle( board, edited, targetMM, commit, message );
}

inline bool canDriveDimension( BOARD* board, PCB_DIMENSION_BASE* dim )
{
    if( !dim || dim->IsLocked() || dim->GetEditFlags() != 0 ) return false;
    wxString message;
    CIRCLE_GEOMETRY circle;
    if( collectCircle( board, circle, message ) ) return circleDimensionFactor( circle, dim ) != 0;
    RECT_GEOMETRY rectangle;
    return collectRectangle( board, rectangle, message ) && dimensionAxis( rectangle, dim ) >= 0;
}
} // namespace SMART_BOARD_NATIVE
