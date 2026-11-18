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

    SbdCircle rustGeometry() const { return { rustPoint( center ), radius }; }

    VECTOR2I scaledPoint( const VECTOR2I& p, double newRadius ) const
    {
        SbdPoint result = rustPoint( p );
        sbd_circle_scaled_point( rustGeometry(), rustPoint( p ), newRadius, &result );
        return nativePoint( result );
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
        {
            message = dimensionText(
                wxS( "Use a single circle on Edge.Cuts." ),
                wxS( "円形外形はEdge.Cutsの円1個に対応します。" ) );
            return false;
        }
        out.shape = shape;
    }
    if( !out.shape ) return false;
    SbdCircle geometry{};
    if( sbd_circle_from_points( rustPoint( out.shape->GetStart() ), rustPoint( out.shape->GetEnd() ), &geometry ) != SBD_OK )
    {
        message = dimensionText(
            wxS( "Use a circle with a diameter between 0.01 and 2000 mm, entirely within the ±2000 mm coordinate range." ),
            wxS( "円の直径は0.01～2000 mm、円全体の座標は±2000 mm以内にしてください。" ) );
        return false;
    }
    out.center = nativePoint( geometry.center );
    out.radius = geometry.radius;
    return true;
}

// 1 = radius, 2 = diameter, 0 = unrelated or unsupported dimension.
inline int circleDimensionFactor( const CIRCLE_GEOMETRY& circle, const PCB_DIMENSION_BASE* dim )
{
    if( !dim ) return 0;
    const int kind = dim->Type() == PCB_DIM_RADIAL_T ? 1 : linearDimension( dim ) ? 2 : 0;
    return sbd_circle_dimension_factor( circle.rustGeometry(), kind,
                rustPoint( dim->GetStart() ), rustPoint( dim->GetEnd() ), dim->GetMeasuredValue() );
}

inline bool resizeCircle( BOARD* board, PCB_DIMENSION_BASE* edited, double targetMM,
                          BOARD_COMMIT& commit, wxString& message )
{
    if( !std::isfinite( targetMM ) || targetMM < 0.01 || targetMM > 1000.0 )
    {
        message = dimensionText(
            wxS( "Enter a dimension between 0.01 and 1000 mm." ),
            wxS( "寸法は0.01～1000 mm以内で入力してください。" ) );
        return false;
    }
    CIRCLE_GEOMETRY circle;
    if( !collectCircle( board, circle, message ) ) return false;
    const int factor = circleDimensionFactor( circle, edited );
    if( !factor )
    {
        message = dimensionText(
            wxS( "For a radius, snap to the center and circumference. For a diameter, snap to opposite points on the circle." ),
            wxS( "半径寸法は中心と円周、直径寸法は円周上の向かい合う2点に合わせてください。" ) );
        return false;
    }
    double newRadius = 0;
    if( sbd_circle_target_radius( circle.rustGeometry(), factor, targetMM, &newRadius ) != SBD_OK )
    {
        message = dimensionText(
            wxS( "The resized circle exceeds the ±2000 mm coordinate range." ),
            wxS( "変更後の円が座標範囲±2000 mmを超えます。" ) );
        return false;
    }
    if( circle.shape->IsLocked() || edited->IsLocked() )
    { message = dimensionText( wxS( "The circle or dimension is locked." ), wxS( "円または寸法がロックされています。" ) ); return false; }
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
        {
            message = dimensionText(
                wxS( "A linked dimension would exceed 2000 mm." ),
                wxS( "追従する寸法の長さが2000 mmを超えます。" ) );
            return false;
        }
        if( dim->IsLocked() )
        { message = dimensionText( wxS( "A linked dimension is locked." ), wxS( "追従する寸法がロックされています。" ) ); return false; }
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

