// SPDX-License-Identifier: GPL-3.0-or-later
#include <boost/test/unit_test.hpp>
#include <tool/tool_manager.h>
#include <pcbnew_utils/board_test_utils.h>
#include <dialogs/smart_board_driving_dimension_impl.h>

namespace
{
struct FIXTURE
{
    BOARD board;
    TOOL_MANAGER manager;
    KI_TEST::DUMMY_TOOL* tool;
    PCB_SHAPE* shape;
    PCB_DIM_ALIGNED* width;
    PCB_DIM_ALIGNED* height;
    FIXTURE()
    {
        manager.SetEnvironment( &board, nullptr, nullptr, nullptr, nullptr );
        tool = new KI_TEST::DUMMY_TOOL(); manager.RegisterTool( tool );
        shape = new PCB_SHAPE( &board, SHAPE_T::RECTANGLE );
        shape->SetLayer( Edge_Cuts ); shape->SetStart( { 100000000,100000000 } );
        shape->SetEnd( { 150000000,130000000 } ); board.Add( shape );
        width = new PCB_DIM_ALIGNED( &board );
        width->SetLayer( Dwgs_User ); width->SetStart( {100000000,100000000} );
        width->SetEnd( {150000000,100000000} ); width->SetHeight( -8000000 ); width->Update();
        board.Add( width );
        height = new PCB_DIM_ALIGNED( &board );
        height->SetLayer( Dwgs_User ); height->SetStart( {150000000,100000000} );
        height->SetEnd( {150000000,130000000} ); height->SetHeight( -8000000 ); height->Update();
        board.Add( height );
    }
};
}
BOOST_AUTO_TEST_SUITE( SmartBoardDrivingDimensions )
BOOST_AUTO_TEST_CASE( ExpressionsAndInvalidNumbers )
{
    double mm = 0;
    BOOST_REQUIRE( SMART_BOARD_NATIVE::parseMillimetres( wxS("2*(30+5)"), mm ) );
    BOOST_CHECK_CLOSE( mm, 70.0, 0.000001 );
    BOOST_REQUIRE( SMART_BOARD_NATIVE::parseMillimetres( wxS("1in+5mm"), mm ) );
    BOOST_CHECK_CLOSE( mm, 30.4, 0.000001 );
    for( const char* text : { "1/0", "0", "-1", "1001", "0.000000001", "nonsense" } )
        BOOST_CHECK( !SMART_BOARD_NATIVE::parseMillimetres( wxString::FromUTF8(text), mm ) );
}
BOOST_FIXTURE_TEST_CASE( ResizesAndStagesBothDimensions, FIXTURE )
{
    BOARD_COMMIT commit( tool ); wxString error;
    BOOST_REQUIRE( SMART_BOARD_NATIVE::resizeRectangle( &board, width, 70, commit, error ) );
    BOOST_CHECK( shape->GetStart() == VECTOR2I(100000000,100000000) );
    BOOST_CHECK( shape->GetEnd() == VECTOR2I(170000000,130000000) );
    BOOST_CHECK_EQUAL( width->GetMeasuredValue(), 70000000 );
    BOOST_CHECK_EQUAL( height->GetMeasuredValue(), 30000000 );
    BOOST_CHECK_EQUAL( height->GetStart().x, 170000000 );
    BOOST_CHECK_EQUAL( commit.GetStatus(shape), CHT_MODIFY );
    BOOST_CHECK_EQUAL( commit.GetStatus(width), CHT_MODIFY );
    BOOST_CHECK_EQUAL( commit.GetStatus(height), CHT_MODIFY );
}
BOOST_FIXTURE_TEST_CASE( RejectsDetachedAndDiagonalDimensions, FIXTURE )
{
    for( VECTOR2I end : { VECTOR2I(150000000,130000000), VECTOR2I(149000000,100000000) } )
    {
        width->SetEnd(end); width->Update();
        BOARD_COMMIT commit(tool); wxString error;
        BOOST_CHECK( !SMART_BOARD_NATIVE::resizeRectangle(&board,width,70,commit,error) );
        BOOST_CHECK( shape->GetEnd() == VECTOR2I(150000000,130000000) );
    }
}
BOOST_FIXTURE_TEST_CASE( SingleCornerDimensionKeepsOtherEndpoint, FIXTURE )
{
    auto* extra = new PCB_DIM_ALIGNED( &board );
    extra->SetLayer( Dwgs_User );
    extra->SetStart( { 150000000, 100000000 } );
    extra->SetEnd( { 180000000, 90000000 } );
    extra->Update(); board.Add( extra );
    BOARD_COMMIT commit( tool ); wxString error;
    BOOST_REQUIRE( SMART_BOARD_NATIVE::resizeRectangle( &board, width, 70, commit, error ) );
    BOOST_CHECK( extra->GetStart() == VECTOR2I( 170000000, 100000000 ) );
    BOOST_CHECK( extra->GetEnd() == VECTOR2I( 180000000, 90000000 ) );
    BOOST_CHECK_EQUAL( commit.GetStatus( extra ), CHT_MODIFY );
}
BOOST_FIXTURE_TEST_CASE( RejectsLockedItemsBeforeMutation, FIXTURE )
{
    height->SetLocked(true);
    BOARD_COMMIT commit(tool); wxString error;
    BOOST_CHECK( !SMART_BOARD_NATIVE::resizeRectangle(&board,width,70,commit,error) );
    BOOST_CHECK( shape->GetEnd() == VECTOR2I(150000000,130000000) );
    BOOST_CHECK_EQUAL( width->GetMeasuredValue(),50000000 );
    height->SetLocked(false); shape->SetLocked(true);
    BOOST_CHECK( !SMART_BOARD_NATIVE::resizeRectangle(&board,width,70,commit,error) );
}
BOOST_FIXTURE_TEST_CASE( ReversedEndpointsAndHeight, FIXTURE )
{
    height->SetStart({150000000,130000000}); height->SetEnd({150000000,100000000}); height->Update();
    BOARD_COMMIT commit(tool); wxString error;
    BOOST_REQUIRE( SMART_BOARD_NATIVE::resizeRectangle(&board,height,45,commit,error) );
    BOOST_CHECK( shape->GetEnd() == VECTOR2I(150000000,145000000) );
    BOOST_CHECK_EQUAL( height->GetMeasuredValue(),45000000 );
    BOOST_CHECK_EQUAL( width->GetMeasuredValue(),50000000 );
}
BOOST_FIXTURE_TEST_CASE( CoordinateLimitIsAtomic, FIXTURE )
{
    shape->SetStart({1950000000,100000000}); shape->SetEnd({1990000000,130000000});
    width->SetStart(shape->GetStart()); width->SetEnd({1990000000,100000000}); width->Update();
    BOARD_COMMIT commit(tool); wxString error;
    BOOST_CHECK( !SMART_BOARD_NATIVE::resizeRectangle(&board,width,100,commit,error) );
    BOOST_CHECK_EQUAL(shape->GetEnd().x,1990000000);
}
BOOST_AUTO_TEST_CASE( FourLinesRequireExactConnections )
{
    BOARD board; SMART_BOARD_NATIVE::RECT_GEOMETRY rect; wxString error;
    std::array<VECTOR2I,4> p{ VECTOR2I(0,0),VECTOR2I(50000000,0),VECTOR2I(50000000,30000000),VECTOR2I(0,30000000) };
    PCB_SHAPE* last = nullptr;
    for(int i=0;i<4;++i)
    {
        last = new PCB_SHAPE(&board,SHAPE_T::SEGMENT); last->SetLayer(Edge_Cuts);
        last->SetStart(p[i]); last->SetEnd(p[(i+1)%4]); board.Add(last);
    }
    BOOST_REQUIRE(SMART_BOARD_NATIVE::collectRectangle(&board,rect,error));
    last->SetEnd({1,0});
    BOOST_CHECK(!SMART_BOARD_NATIVE::collectRectangle(&board,rect,error));
}
BOOST_AUTO_TEST_SUITE_END()

namespace
{
struct CIRCLE_FIXTURE
{
    BOARD board;
    TOOL_MANAGER manager;
    KI_TEST::DUMMY_TOOL* tool;
    PCB_SHAPE* circle;
    PCB_DIM_RADIAL* radius;
    PCB_DIM_ALIGNED* diameter;
    CIRCLE_FIXTURE()
    {
        manager.SetEnvironment( &board, nullptr, nullptr, nullptr, nullptr );
        tool = new KI_TEST::DUMMY_TOOL(); manager.RegisterTool( tool );
        circle = new PCB_SHAPE( &board, SHAPE_T::CIRCLE ); circle->SetLayer( Edge_Cuts );
        circle->SetStart( { 100000000, 100000000 } ); circle->SetEnd( { 120000000, 100000000 } );
        board.Add( circle );
        radius = new PCB_DIM_RADIAL( &board ); radius->SetLayer( Dwgs_User );
        radius->SetStart( circle->GetStart() ); radius->SetEnd( circle->GetEnd() );
        radius->SetTextPos( { 140000000, 90000000 } ); radius->Update(); board.Add( radius );
        diameter = new PCB_DIM_ALIGNED( &board ); diameter->SetLayer( Dwgs_User );
        diameter->SetStart( { 80000000, 100000000 } ); diameter->SetEnd( circle->GetEnd() );
        diameter->SetHeight( -30000000 ); diameter->Update(); board.Add( diameter );
    }
};
}
BOOST_AUTO_TEST_SUITE( SmartBoardDrivingCircles )
BOOST_FIXTURE_TEST_CASE( RadiusKeepsCenterAndUpdatesDiameter, CIRCLE_FIXTURE )
{
    BOARD_COMMIT commit( tool ); wxString error;
    BOOST_REQUIRE( SMART_BOARD_NATIVE::resizeOutline( &board, radius, 30, commit, error ) );
    BOOST_CHECK( circle->GetStart() == VECTOR2I( 100000000, 100000000 ) );
    BOOST_CHECK( circle->GetEnd() == VECTOR2I( 130000000, 100000000 ) );
    BOOST_CHECK_EQUAL( radius->GetMeasuredValue(), 30000000 );
    BOOST_CHECK_EQUAL( diameter->GetMeasuredValue(), 60000000 );
    for( BOARD_ITEM* item : std::vector<BOARD_ITEM*>{ circle, radius, diameter } )
        BOOST_CHECK_EQUAL( commit.GetStatus( item ), CHT_MODIFY );
}
BOOST_FIXTURE_TEST_CASE( DiameterUsesHalfTheEnteredLength, CIRCLE_FIXTURE )
{
    BOARD_COMMIT commit( tool ); wxString error;
    BOOST_REQUIRE( SMART_BOARD_NATIVE::resizeOutline( &board, diameter, 56, commit, error ) );
    BOOST_CHECK_EQUAL( radius->GetMeasuredValue(), 28000000 );
    BOOST_CHECK_EQUAL( diameter->GetMeasuredValue(), 56000000 );
    BOOST_CHECK( circle->GetEnd() == VECTOR2I( 128000000, 100000000 ) );
    BOOST_CHECK( diameter->GetStart() == VECTOR2I( 72000000, 100000000 ) );
}
BOOST_FIXTURE_TEST_CASE( DiagonalRadiusPreservesItsDirection, CIRCLE_FIXTURE )
{
    // 3-4-5 triangle direction; circle geometry and annotation need not share an angle.
    radius->SetEnd( { 112000000, 116000000 } ); radius->Update();
    BOARD_COMMIT commit( tool ); wxString error;
    BOOST_REQUIRE( SMART_BOARD_NATIVE::resizeCircle( &board, radius, 25, commit, error ) );
    BOOST_CHECK( radius->GetEnd() == VECTOR2I( 115000000, 120000000 ) );
    BOOST_CHECK( circle->GetEnd() == VECTOR2I( 125000000, 100000000 ) );
}
BOOST_FIXTURE_TEST_CASE( RejectsChordAndDetachedCenterWithoutStaging, CIRCLE_FIXTURE )
{
    diameter->SetStart( { 100000000, 80000000 } ); diameter->Update();
    BOARD_COMMIT commit( tool ); wxString error;
    BOOST_CHECK( !SMART_BOARD_NATIVE::resizeCircle( &board, diameter, 56, commit, error ) );
    radius->SetStart( { 100100000, 100000000 } ); radius->Update();
    BOOST_CHECK( !SMART_BOARD_NATIVE::resizeCircle( &board, radius, 30, commit, error ) );
    BOOST_CHECK( circle->GetEnd() == VECTOR2I( 120000000, 100000000 ) );
    BOOST_CHECK_EQUAL( commit.GetStatus( circle ), 0 );
}
BOOST_FIXTURE_TEST_CASE( RejectsEveryLockedParticipantBeforeMutation, CIRCLE_FIXTURE )
{
    for( BOARD_ITEM* item : std::vector<BOARD_ITEM*>{ circle, radius, diameter } )
    {
        item->SetLocked( true );
        BOARD_COMMIT commit( tool ); wxString error;
        BOOST_CHECK( !SMART_BOARD_NATIVE::resizeCircle( &board, radius, 30, commit, error ) );
        BOOST_CHECK( circle->GetEnd() == VECTOR2I( 120000000, 100000000 ) );
        BOOST_CHECK_EQUAL( commit.GetStatus( circle ), 0 );
        item->SetLocked( false );
    }
}
BOOST_FIXTURE_TEST_CASE( CircleExtentAndInvalidSizesAreAtomic, CIRCLE_FIXTURE )
{
    circle->SetStart( { 1980000000, 0 } ); circle->SetEnd( { 2000000000, 0 } );
    radius->SetStart( circle->GetStart() ); radius->SetEnd( circle->GetEnd() ); radius->Update();
    for( double size : { 0.0, -1.0, 1001.0, 30.0 } )
    {
        BOARD_COMMIT commit( tool ); wxString error;
        BOOST_CHECK( !SMART_BOARD_NATIVE::resizeCircle( &board, radius, size, commit, error ) );
        BOOST_CHECK_EQUAL( circle->GetEnd().x, 2000000000 );
        BOOST_CHECK_EQUAL( commit.GetStatus( circle ), 0 );
    }
}
BOOST_FIXTURE_TEST_CASE( OneAttachedEndpointMovesAndExternalEndpointStays, CIRCLE_FIXTURE )
{
    auto* extra = new PCB_DIM_ALIGNED( &board ); extra->SetLayer( Dwgs_User );
    extra->SetStart( { 100000000, 120000000 } ); extra->SetEnd( { 100000000, 170000000 } );
    extra->Update(); board.Add( extra );
    BOARD_COMMIT commit( tool ); wxString error;
    BOOST_REQUIRE( SMART_BOARD_NATIVE::resizeCircle( &board, radius, 30, commit, error ) );
    BOOST_CHECK( extra->GetStart() == VECTOR2I( 100000000, 130000000 ) );
    BOOST_CHECK( extra->GetEnd() == VECTOR2I( 100000000, 170000000 ) );
}
BOOST_FIXTURE_TEST_CASE( MultipleOutlinesAreRejected, CIRCLE_FIXTURE )
{
    auto* second = new PCB_SHAPE( &board, SHAPE_T::CIRCLE ); second->SetLayer( Edge_Cuts );
    second->SetStart( { 200000000, 100000000 } ); second->SetEnd( { 220000000, 100000000 } );
    board.Add( second );
    BOARD_COMMIT commit( tool ); wxString error;
    BOOST_CHECK( !SMART_BOARD_NATIVE::resizeOutline( &board, radius, 30, commit, error ) );
    BOOST_CHECK_EQUAL( commit.GetStatus( circle ), 0 );
}
BOOST_FIXTURE_TEST_CASE( RelatedLongDimensionIsRejectedBeforeMutation, CIRCLE_FIXTURE )
{
    circle->SetStart( { 980000000, 0 } ); circle->SetEnd( { 1000000000, 0 } );
    radius->SetStart( circle->GetStart() ); radius->SetEnd( circle->GetEnd() ); radius->Update();
    auto* extra = new PCB_DIM_ALIGNED( &board ); extra->SetLayer( Dwgs_User );
    extra->SetStart( circle->GetEnd() ); extra->SetEnd( { -1000000000, 0 } );
    extra->Update(); board.Add( extra );
    BOARD_COMMIT commit( tool ); wxString error;
    BOOST_CHECK( !SMART_BOARD_NATIVE::resizeCircle( &board, radius, 30, commit, error ) );
    BOOST_CHECK_EQUAL( circle->GetEnd().x, 1000000000 );
    BOOST_CHECK_EQUAL( commit.GetStatus( circle ), 0 );
}
BOOST_AUTO_TEST_SUITE_END()
