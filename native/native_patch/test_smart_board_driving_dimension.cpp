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
