// SPDX-License-Identifier: GPL-3.0-or-later
// Minimal in-memory API stand-ins. They never read or run a KiCad installation.
#pragma once
#include <cmath>
#include <cstddef>
#include <string>
#include <utility>
#include <vector>

struct VECTOR2I
{
    int x = 0, y = 0;
    bool operator==( const VECTOR2I& other ) const { return x == other.x && y == other.y; }
    bool operator!=( const VECTOR2I& other ) const { return !( *this == other ); }
};

class wxString
{
public:
    struct Buffer
    {
        std::string value;
        const char* data() const { return value.data(); }
        std::size_t length() const { return value.size(); }
    };
    wxString() = default;
    wxString( const char* value ) : m_value( value ) {}
    std::size_t size() const { return m_value.size(); }
    Buffer ToUTF8() const { return { m_value }; }
private:
    std::string m_value;
};
#define wxS(text) wxString(text)

struct PCB_IU_SCALE
{
    static constexpr double IU_PER_MM = 1000000.0;
    int mmToIU( double mm ) const { return static_cast<int>( std::llround( mm * IU_PER_MM ) ); }
    double IUTomm( int value ) const { return value / IU_PER_MM; }
};
inline constexpr PCB_IU_SCALE pcbIUScale{};
inline constexpr int Edge_Cuts = 44;
inline constexpr int Dwgs_User = 40;
inline constexpr int PCB_DIM_ALIGNED_T = 1;
inline constexpr int PCB_DIM_ORTHOGONAL_T = 2;
inline constexpr int PCB_DIM_RADIAL_T = 3;
inline constexpr int PCB_DIM_OTHER_T = 4;

class BOARD_ITEM
{
public:
    virtual ~BOARD_ITEM() = default;
    int GetLayer() const { return m_layer; }
    void SetLayer( int layer ) { m_layer = layer; }
    bool IsLocked() const { return m_locked; }
    void SetLocked( bool locked ) { m_locked = locked; }
    int GetEditFlags() const { return m_editFlags; }
    void SetEditFlags( int flags ) { m_editFlags = flags; }
private:
    int m_layer = Dwgs_User;
    bool m_locked = false;
    int m_editFlags = 0;
};

enum class SHAPE_T { RECTANGLE, SEGMENT, CIRCLE, ARC };
class PCB_SHAPE : public BOARD_ITEM
{
public:
    explicit PCB_SHAPE( SHAPE_T shape ) : m_shape( shape ) { SetLayer( Edge_Cuts ); }
    SHAPE_T GetShape() const { return m_shape; }
    VECTOR2I GetStart() const { return m_start; }
    VECTOR2I GetEnd() const { return m_end; }
    void SetStart( VECTOR2I point ) { m_start = point; }
    void SetEnd( VECTOR2I point ) { m_end = point; }
    std::vector<VECTOR2I> GetRectCorners() const
    {
        return { m_start, { m_end.x, m_start.y }, m_end, { m_start.x, m_end.y } };
    }
private:
    SHAPE_T m_shape;
    VECTOR2I m_start, m_end;
};

class PCB_DIMENSION_BASE : public BOARD_ITEM
{
public:
    explicit PCB_DIMENSION_BASE( int type ) : m_type( type ) {}
    int Type() const { return m_type; }
    VECTOR2I GetStart() const { return m_start; }
    VECTOR2I GetEnd() const { return m_end; }
    void SetStart( VECTOR2I point ) { m_start = point; }
    void SetEnd( VECTOR2I point ) { m_end = point; }
    double GetMeasuredValue() const
    {
        if( m_type == PCB_DIM_ORTHOGONAL_T ) return std::abs( static_cast<double>( m_end.x ) - m_start.x );
        return std::hypot( static_cast<double>( m_end.x ) - m_start.x,
                           static_cast<double>( m_end.y ) - m_start.y );
    }
    void SetOverrideTextEnabled( bool enabled ) { overrideEnabled = enabled; }
    void Update() { ++updates; }
    bool overrideEnabled = true;
    int updates = 0;
private:
    int m_type;
    VECTOR2I m_start, m_end;
};

class BOARD
{
public:
    void Add( BOARD_ITEM* item ) { m_items.push_back( item ); }
    const std::vector<BOARD_ITEM*>& Drawings() const { return m_items; }
private:
    std::vector<BOARD_ITEM*> m_items;
};

class BOARD_COMMIT
{
public:
    void Modify( BOARD_ITEM* item ) { modified.push_back( item ); }
    std::vector<BOARD_ITEM*> modified;
};
