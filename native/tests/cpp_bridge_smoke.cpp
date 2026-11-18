// SPDX-License-Identifier: GPL-3.0-or-later
// Compile the ACTUAL adapter header against in-memory stand-ins and the REAL Rust
// static library. This checks C++/Rust ABI and adapter mutation ordering, not KiCad UI.
#include <cstdlib>
#include <iostream>
#include "../native_patch/smart_board_driving_dimension_impl.h"

static void require( bool condition, const char* message )
{
    if( !condition ) { std::cerr << "FAIL: " << message << '\n'; std::exit( 1 ); }
}

static VECTOR2I mm( double x, double y )
{
    return { pcbIUScale.mmToIU( x ), pcbIUScale.mmToIU( y ) };
}

struct CircleFixture
{
    BOARD board;
    PCB_SHAPE circle{ SHAPE_T::CIRCLE };
    PCB_DIMENSION_BASE radius{ PCB_DIM_RADIAL_T }, diameter{ PCB_DIM_ALIGNED_T }, follower{ PCB_DIM_ALIGNED_T };
    CircleFixture()
    {
        circle.SetStart( mm( 100.3, 100.4 ) ); circle.SetEnd( mm( 128.3, 100.4 ) );
        radius.SetStart( circle.GetStart() ); radius.SetEnd( circle.GetEnd() );
        diameter.SetStart( mm( 72.3, 100.4 ) ); diameter.SetEnd( circle.GetEnd() );
        follower.SetStart( circle.GetEnd() ); follower.SetEnd( mm( 128.3, 110.4 ) );
        board.Add( &circle ); board.Add( &radius ); board.Add( &diameter ); board.Add( &follower );
    }
};

static void parser()
{
    double value = 42;
    require( SMART_BOARD_NATIVE::parseMillimetres( wxS( "2*(30+5)" ), value ) && value == 70, "expression via UTF-8 ABI" );
    require( SMART_BOARD_NATIVE::parseMillimetres( wxS( "1in+5mm" ), value ) && std::abs( value - 30.4 ) < 1e-9, "units via ABI" );
    value = 42;
    require( !SMART_BOARD_NATIVE::parseMillimetres( wxS( "1/0" ), value ) && value == 42, "invalid expression preserves output" );
    require( !SMART_BOARD_NATIVE::parseMillimetres( wxS( "2**5" ), value ), "unsupported executable/operator syntax rejected" );
}

static void rectangle()
{
    BOARD board;
    PCB_SHAPE shape( SHAPE_T::RECTANGLE );
    shape.SetStart( mm( 10, 20 ) ); shape.SetEnd( mm( 60, 50 ) );
    PCB_DIMENSION_BASE width( PCB_DIM_ALIGNED_T ), height( PCB_DIM_ORTHOGONAL_T ), follower( PCB_DIM_ALIGNED_T );
    width.SetStart( shape.GetStart() ); width.SetEnd( mm( 60, 20 ) );
    height.SetStart( mm( 60, 20 ) ); height.SetEnd( mm( 60, 50 ) );
    follower.SetStart( mm( 60, 50 ) ); follower.SetEnd( mm( 90, 80 ) );
    board.Add( &shape ); board.Add( &width ); board.Add( &height ); board.Add( &follower );
    BOARD_COMMIT commit; wxString error;
    require( SMART_BOARD_NATIVE::canDriveDimension( &board, &width ), "rectangle classified through Rust" );
    require( SMART_BOARD_NATIVE::resizeRectangle( &board, &width, 70, commit, error ), "rectangle resize succeeds" );
    require( shape.GetStart() == mm( 10, 20 ) && shape.GetEnd() == mm( 80, 50 ), "rectangle anchor and width preserved" );
    require( width.GetEnd() == mm( 80, 20 ) && !width.overrideEnabled, "edited width reattached and override cleared" );
    require( height.GetStart() == mm( 80, 20 ) && height.GetEnd() == mm( 80, 50 ), "related dimension follows both corners" );
    require( follower.GetStart() == mm( 80, 50 ) && follower.GetEnd() == mm( 90, 80 ), "one attached endpoint follows" );
    require( commit.modified.size() == 4, "adapter registers each changed item before mutation" );

    shape.SetLocked( true );
    BOARD_COMMIT locked;
    require( !SMART_BOARD_NATIVE::resizeRectangle( &board, &width, 90, locked, error ), "locked rectangle rejected" );
    require( locked.modified.empty() && shape.GetEnd() == mm( 80, 50 ), "locked rejection leaves transaction and geometry unchanged" );
}

static void circle()
{
    CircleFixture f;
    BOARD_COMMIT commit; wxString error;
    require( SMART_BOARD_NATIVE::canDriveDimension( &f.board, &f.radius ), "radius classified through Rust" );
    require( SMART_BOARD_NATIVE::resizeOutline( &f.board, &f.radius, 30, commit, error ), "radius change succeeds" );
    require( f.circle.GetStart() == mm( 100.3, 100.4 ) && f.circle.GetEnd() == mm( 130.3, 100.4 ), "circle center remains fixed" );
    require( f.radius.GetEnd() == f.circle.GetEnd(), "radius follows circle" );
    require( f.diameter.GetStart() == mm( 70.3, 100.4 ) && f.diameter.GetEnd() == mm( 130.3, 100.4 ), "diameter follows circle" );
    require( f.follower.GetStart() == mm( 130.3, 100.4 ) && f.follower.GetEnd() == mm( 128.3, 110.4 ), "circle follower preserves unattached endpoint" );
    require( commit.modified.size() == 4, "circle transaction includes all changed items" );
    BOARD_COMMIT diameter;
    require( SMART_BOARD_NATIVE::resizeCircle( &f.board, &f.diameter, 56, diameter, error ), "diameter edit succeeds" );
    require( f.circle.GetEnd() == mm( 128.3, 100.4 ) && !f.diameter.overrideEnabled, "diameter uses half radius" );
}

static void rejections_are_read_only()
{
    wxString error;
    for( int locked = 0; locked < 3; ++locked )
    {
        CircleFixture f;
        if( locked == 0 ) f.circle.SetLocked( true );
        else if( locked == 1 ) f.radius.SetLocked( true );
        else f.follower.SetLocked( true );
        BOARD_COMMIT commit;
        require( !SMART_BOARD_NATIVE::resizeCircle( &f.board, &f.radius, 30, commit, error ), "circle/edited/follower lock rejected" );
        require( commit.modified.empty() && f.circle.GetEnd() == mm( 128.3, 100.4 ) && f.radius.GetEnd() == mm( 128.3, 100.4 ), "lock preflight is read-only" );
    }
    CircleFixture f;
    f.circle.SetStart( mm( 1990, 0 ) ); f.circle.SetEnd( mm( 2000, 0 ) );
    f.radius.SetStart( f.circle.GetStart() ); f.radius.SetEnd( f.circle.GetEnd() );
    BOARD_COMMIT outside;
    require( !SMART_BOARD_NATIVE::resizeCircle( &f.board, &f.radius, 20, outside, error ), "whole-circle coordinate limit rejected" );
    require( outside.modified.empty() && f.circle.GetEnd() == mm( 2000, 0 ), "coordinate rejection is read-only" );

    CircleFixture chord;
    chord.diameter.SetStart( mm( 100.3, 72.4 ) );
    BOARD_COMMIT invalid;
    require( !SMART_BOARD_NATIVE::resizeCircle( &chord.board, &chord.diameter, 56, invalid, error ), "chord cannot drive diameter" );
    require( invalid.modified.empty(), "classification rejection happens before transaction changes" );
}

int main()
{
    using SMART_BOARD_NATIVE::dimensionText;
    for( const auto& language : { wxS( "ja" ), wxS( "ja-JP" ), wxS( "en-US" ), wxS( "fr-FR" ) } )
    {
        Pgm().language = language;
        const bool japanese = language == wxS( "ja" ) || language == wxS( "ja-JP" );
        require( dimensionText( wxS( "Width" ), wxS( "幅" ) ) == ( japanese ? wxS( "幅" ) : wxS( "Width" ) ),
                 "dimension text follows the PCB editor language with English fallback" );
    }
    Pgm().language = wxS( "" );
    wxLocale::systemLanguage = wxLANGUAGE_JAPANESE;
    require( dimensionText( wxS( "Width" ), wxS( "幅" ) ) == wxS( "幅" ), "system default follows Japanese locale" );
    Pgm().language = wxS( "en" );

    parser(); rectangle(); circle(); rejections_are_read_only();
    std::cout << "PASS: real Rust static library + C++ adapter, parser, rectangle/circle resizing, followers, locks and preflight.\n";
}
