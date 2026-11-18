// SPDX-License-Identifier: GPL-3.0-or-later
use super::*;

fn p(x: i32, y: i32) -> Point { Point { x, y } }
fn rect() -> Rect { Rect { left: 10_000_000, right: 60_000_000, top: 20_000_000, bottom: 50_000_000 } }
fn circle() -> Circle { Circle::from_points(p(100_300_000, 100_400_000), p(128_300_000, 100_400_000)).unwrap() }

#[test]
fn expressions_preserve_native_examples_and_units() {
    for (text, expected) in [("2*(30+5)", 70.0), ("1in+5mm", 30.4), ("100mil", 2.54),
        ("2.54cm", 25.4), (".5*2", 1.0), ("1e2", 100.0), ("１＋（２＊３）", 7.0),
        ("-(-2)+1", 3.0), ("(2*3)mm", 6.0), (" 1 IN + 5 mm ", 30.4)] {
        assert!((parse_mm(text).unwrap() - expected).abs() < 1e-9, "{text}");
    }
}

#[test]
fn parser_rejects_unsafe_malformed_and_nonfinite_values() {
    for text in ["", "nan", "inf", "1/0", "2/(1-1)", "1e999", "1e", "--", "2**3", "2(3)",
        "__import__('os')", "sqrt(4)", "1;2", "a=5", "2+", "(1", "1)", "0x10", "1foo", "1,5", "1.2.3"] {
        assert!(parse_mm(text).is_err(), "{text}");
    }
    assert!(parse_mm(&"1".repeat(257)).is_err());
    assert!(parse_mm(&format!("{}1{}", "(".repeat(80), ")".repeat(80))).is_err());
}

#[test]
fn target_limits_are_inclusive() {
    assert_eq!(parse_mm("0.01"), Ok(0.01));
    assert_eq!(parse_mm("1000"), Ok(1000.0));
    assert_eq!(parse_mm("0.009999"), Err(Error::Range));
    assert_eq!(parse_mm("1000.00001"), Err(Error::Range));
    assert_eq!(parse_mm("-1"), Err(Error::Range));
}

#[test]
fn rectangle_vertices_accept_arbitrary_order_and_reversed_edges() {
    let r = rect();
    assert_eq!(rect_from_vertices(&[r.corner(3), r.corner(0), r.corner(2), r.corner(1)], false), Ok(r));
    let edges = [r.corner(1), r.corner(0), r.corner(1), r.corner(3), r.corner(3), r.corner(2), r.corner(0), r.corner(2)];
    assert_eq!(rect_from_vertices(&edges, true), Ok(r));
}

#[test]
fn rectangle_rejects_gaps_duplicates_diagonals_and_degenerate_bounds() {
    let r = rect();
    let mut edges = [r.corner(0), r.corner(1), r.corner(1), r.corner(3), r.corner(3), r.corner(2), r.corner(2), r.corner(0)];
    edges[7].x += 1;
    assert!(rect_from_vertices(&edges, true).is_err());
    edges[7] = r.corner(2);
    assert!(rect_from_vertices(&edges, true).is_err());
    edges[6] = r.corner(1); edges[7] = r.corner(2);
    assert!(rect_from_vertices(&edges, true).is_err());
    assert!(rect_from_vertices(&[r.corner(0);4], false).is_err());
    assert!(rect_from_vertices(&[p(0,0),p(1,0),p(1,1),p(0,1)], false).is_err());
}

#[test]
fn rectangle_tolerance_scales_to_small_shapes_and_axis_requires_adjacent_corners() {
    let r = Rect { left: 0, right: 10_000, top: 0, bottom: 10_000 };
    assert_eq!(r.find_corner(p(2_500,2_500),true), 0);
    assert_eq!(r.find_corner(p(2_501,2_501),true), -1);
    assert_eq!(r.find_corner(p(1,0),false), -1);
    assert_eq!(r.axis(r.corner(0),r.corner(1),10_000.0),0);
    assert_eq!(r.axis(r.corner(3),r.corner(1),10_000.0),1);
    assert_eq!(r.axis(r.corner(0),r.corner(3),14_142.0),-1);
    assert_eq!(r.axis(r.corner(0),r.corner(1),0.0),-1);
}

#[test]
fn rectangle_updates_only_related_corners_and_preserves_anchor() {
    let r = rect();
    let end = r.target_max(0,70.0).unwrap();
    assert_eq!(end,80_000_000);
    assert_eq!(r.move_corner(r.corner(0),0,end),Ok(r.corner(0)));
    assert_eq!(r.move_corner(r.corner(3),0,end),Ok(p(80_000_000,50_000_000)));
    assert_eq!(r.move_corner(p(99,99),0,end),Ok(p(99,99)));
    // Snapped endpoints are reattached to exact corners, including fixed corners.
    assert_eq!(r.move_corner(p(r.left+100,r.top),0,end),Ok(r.corner(0)));
}

#[test]
fn rectangle_and_span_use_wide_arithmetic_near_int_limits() {
    let invalid = Rect { left: i32::MIN, right: i32::MAX, top: 0, bottom: 10_000 };
    assert!(invalid.validate().is_err());
    assert_eq!(invalid.find_corner(p(i32::MAX,0),true),-1);
    let edge = Rect { left: 1_990_000_000, right: 2_000_000_000, top: 0, bottom: 10_000_000 };
    assert_eq!(edge.target_max(0,10.0),Ok(2_000_000_000));
    assert_eq!(edge.target_max(0,10.000001),Err(Error::Range));
    assert!(!safe_dimension_span(p(i32::MIN,0),p(i32::MAX,0)));
    assert!(safe_dimension_span(p(-1_000_000_000,0),p(1_000_000_000,0)));
    assert!(!safe_dimension_span(p(-1_000_000_000,0),p(1_000_000_001,0)));
}

#[test]
fn circle_classification_rejects_chords_and_projected_diameters() {
    let c = circle();
    let left = p(72_300_000,100_400_000);
    let right = p(128_300_000,100_400_000);
    assert_eq!(c.dimension_factor(1,c.center,right,28_000_000.0),1);
    assert_eq!(c.dimension_factor(2,left,right,56_000_000.0),2);
    assert_eq!(c.dimension_factor(2,p(100_300_000,72_400_000),right,39_597_980.0),0);
    assert_eq!(c.dimension_factor(2,left,right,0.0),0);
    assert_eq!(c.dimension_factor(1,p(1,2),right,28_000_000.0),0);
    let diagonal = Circle::from_points(p(0,0),p(3_000_000,4_000_000)).unwrap();
    assert_eq!(diagonal.dimension_factor(2,p(-3_000_000,-4_000_000),p(3_000_000,4_000_000),10_000_000.0),2);
    assert_eq!(diagonal.dimension_factor(2,p(-3_000_000,-4_000_000),p(3_000_000,4_000_000),6_000_000.0),0);
}

#[test]
fn circle_resize_preserves_center_and_polar_direction() {
    let c = circle();
    let radius = c.target_radius(2,60.0).unwrap();
    assert_eq!(radius,30_000_000.0);
    assert_eq!(c.scaled_point(p(128_300_000,100_400_000),radius),Ok(p(130_300_000,100_400_000)));
    assert_eq!(c.scaled_point(c.center,radius),Ok(c.center));
    assert_eq!(c.scaled_point(p(8,9),radius),Ok(p(8,9)));
    let diagonal = Circle::from_points(p(0,0),p(3_000_000,4_000_000)).unwrap();
    assert_eq!(diagonal.scaled_point(p(3_000_000,4_000_000),10_000_000.0),Ok(p(6_000_000,8_000_000)));
    assert_eq!(diagonal.scaled_point(p(-3_000_000,-4_000_000),10_000_000.0),Ok(p(-6_000_000,-8_000_000)));
}

#[test]
fn circle_minimum_diameter_remains_valid_and_entire_circle_stays_in_range() {
    let c = circle();
    let tiny_radius = c.target_radius(2,0.01).unwrap();
    assert_eq!(tiny_radius,5_000.0);
    let tiny = Circle { center: c.center, radius: tiny_radius };
    assert!(tiny.validate().is_ok());
    assert_eq!(tiny.target_radius(1,1.0),Ok(1_000_000.0));
    let edge = Circle::from_points(p(1_990_000_000,0),p(2_000_000_000,0)).unwrap();
    assert_eq!(edge.target_radius(1,10.0),Ok(10_000_000.0));
    assert_eq!(edge.target_radius(1,10.000001),Err(Error::Range));
    assert!(Circle { center:p(i32::MIN,0),radius:1.0 }.validate().is_err());
    assert!(Circle { center:p(0,0),radius:f64::NAN }.validate().is_err());
}

#[test]
fn ffi_rejects_null_and_invalid_utf8_without_writing_outputs() {
    let mut number = 42.0;
    unsafe {
        assert_eq!(sbd_parse_mm(std::ptr::null(),5,&mut number),Error::InvalidArgument as i32);
        assert_eq!(sbd_parse_mm([0xff_u8].as_ptr(),1,&mut number),Error::InvalidExpression as i32);
        assert_eq!(sbd_parse_mm(b"1/0".as_ptr(),3,&mut number),Error::InvalidExpression as i32);
        assert_eq!(number,42.0);
        assert_eq!(sbd_parse_mm(b"5".as_ptr(),1,std::ptr::null_mut()),Error::InvalidArgument as i32);
        assert_eq!(sbd_parse_mm(b"2*15".as_ptr(),4,&mut number),0);
        assert_eq!(number,30.0);
    }
}

#[test]
fn ffi_geometry_roundtrips_and_preserves_outputs_on_failure() {
    let r = rect();
    let vertices = [r.corner(0),r.corner(1),r.corner(2),r.corner(3)];
    let mut out = Rect::default();
    unsafe {
        assert_eq!(sbd_rect_from_vertices(vertices.as_ptr(),4,0,&mut out),0);
        assert_eq!(out,r);
        assert_eq!(sbd_rect_from_vertices(vertices.as_ptr(),5,0,&mut out),Error::InvalidArgument as i32);
        assert_eq!(out,r);
        let mut point = p(9,8);
        assert_ne!(sbd_rect_move_corner(r,r.corner(3),8,70_000_000,&mut point),0);
        assert_eq!(point,p(9,8));
        assert_eq!(sbd_rect_move_corner(r,r.corner(3),0,70_000_000,&mut point),0);
        assert_eq!(point,p(70_000_000,50_000_000));
        let mut radius=3.0;
        assert_ne!(sbd_circle_target_radius(circle(),0,10.0,&mut radius),0);
        assert_eq!(radius,3.0);
    }
}

#[test]
fn ffi_layout_matches_c_contract() {
    assert_eq!(std::mem::size_of::<Point>(),8);
    assert_eq!(std::mem::size_of::<Rect>(),16);
    assert_eq!(std::mem::size_of::<Circle>(),16);
    assert_eq!(std::mem::align_of::<Circle>(),8);
}
