// SPDX-License-Identifier: GPL-3.0-or-later
//! Pure dimension mathematics. The C++ adapter owns board objects, locks and Undo.
//!
//! Public geometry is expressed in KiCad nanometers. C ABI output APIs leave
//! outputs untouched on failure and contain all Rust unwinding. Raw pointer
//! validity/alignment and disjoint input/output storage are caller obligations.

use std::panic::{catch_unwind, AssertUnwindSafe};

pub const IU_PER_MM: f64 = 1_000_000.0;
pub const COORD_LIMIT: i64 = 2_000_000_000;
pub const MIN_DIM_MM: f64 = 0.01;
pub const MAX_DIM_MM: f64 = 1000.0;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(i32)]
pub enum Error {
    InvalidArgument = 1,
    InvalidExpression = 2,
    Range = 3,
    InvalidGeometry = 4,
    Panic = 255,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
#[repr(C)]
pub struct Point { pub x: i32, pub y: i32 }

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
#[repr(C)]
pub struct Rect { pub left: i32, pub right: i32, pub top: i32, pub bottom: i32 }

#[derive(Clone, Copy, Debug, Default, PartialEq)]
#[repr(C)]
pub struct Circle { pub center: Point, pub radius: f64 }

fn finite(value: f64) -> Result<f64, Error> {
    if value.is_finite() { Ok(value) } else { Err(Error::InvalidExpression) }
}

fn target_mm(value: f64) -> Result<f64, Error> {
    if value.is_finite() && (MIN_DIM_MM..=MAX_DIM_MM).contains(&value) {
        Ok(value)
    } else { Err(Error::Range) }
}

/// A bounded recursive-descent parser; no eval, variables or executable syntax.
/// Numbers, unary +/-, + - * /, parentheses and length-unit suffixes are allowed.
pub fn parse_mm(text: &str) -> Result<f64, Error> {
    if text.is_empty() || text.len() > 4096 || text.chars().count() > 256 {
        return Err(Error::InvalidExpression);
    }
    // Borrow ASCII input; normalize full-width characters into at most 256 stack bytes.
    let mut normalized = [0u8; 256];
    let input = if text.is_ascii() {
        text.as_bytes()
    } else {
        let mut length = 0;
        for (index, c) in text.chars().enumerate() {
            normalized[index] = match c {
                '０'..='９' => b'0' + (c as u32 - '０' as u32) as u8,
                '＋' => b'+', '－' | '−' => b'-', '＊' | '×' => b'*', '／' | '÷' => b'/',
                '（' => b'(', '）' => b')', '．' => b'.',
                ascii if ascii.is_ascii() => ascii as u8,
                _ => return Err(Error::InvalidExpression),
            };
            length += 1;
        }
        &normalized[..length]
    };
    let mut parser = Parser { text: input, pos: 0 };
    let value = parser.expression(0)?;
    parser.space();
    if parser.pos != parser.text.len() { return Err(Error::InvalidExpression); }
    target_mm(value)
}

struct Parser<'a> { text: &'a [u8], pos: usize }
impl Parser<'_> {
    fn space(&mut self) {
        while self.text.get(self.pos).is_some_and(u8::is_ascii_whitespace) { self.pos += 1; }
    }
    fn take(&mut self, byte: u8) -> bool {
        self.space();
        if self.text.get(self.pos) == Some(&byte) { self.pos += 1; true } else { false }
    }
    fn expression(&mut self, depth: usize) -> Result<f64, Error> {
        if depth > 32 { return Err(Error::InvalidExpression); }
        let mut value = self.product(depth + 1)?;
        loop {
            if self.take(b'+') { value = finite(value + self.product(depth + 1)?)?; }
            else if self.take(b'-') { value = finite(value - self.product(depth + 1)?)?; }
            else { return Ok(value); }
        }
    }
    fn product(&mut self, depth: usize) -> Result<f64, Error> {
        let mut value = self.atom(depth + 1)?;
        loop {
            if self.take(b'*') { value = finite(value * self.atom(depth + 1)?)?; }
            else if self.take(b'/') {
                let right = self.atom(depth + 1)?;
                if right == 0.0 { return Err(Error::InvalidExpression); }
                value = finite(value / right)?;
            } else { return Ok(value); }
        }
    }
    fn atom(&mut self, depth: usize) -> Result<f64, Error> {
        if depth > 96 { return Err(Error::InvalidExpression); }
        if self.take(b'+') { return self.atom(depth + 1); }
        if self.take(b'-') { return finite(-self.atom(depth + 1)?); }
        let value = if self.take(b'(') {
            let value = self.expression(depth + 1)?;
            if !self.take(b')') { return Err(Error::InvalidExpression); }
            value
        } else { self.number()? };
        self.space();
        let start = self.pos;
        while self.text.get(self.pos).is_some_and(u8::is_ascii_alphabetic) { self.pos += 1; }
        if start == self.pos { return Ok(value); }
        let unit = &self.text[start..self.pos];
        let factor = [
            ("mm", 1.0), ("cm", 10.0), ("m", 1000.0), ("um", 0.001),
            ("in", 25.4), ("inch", 25.4), ("inches", 25.4),
            ("mil", 0.0254), ("mils", 0.0254),
        ].into_iter().find_map(|(name, factor)| unit.eq_ignore_ascii_case(name.as_bytes()).then_some(factor))
            .ok_or(Error::InvalidExpression)?;
        finite(value * factor)
    }
    fn number(&mut self) -> Result<f64, Error> {
        self.space();
        let start = self.pos;
        let mut digits = 0;
        while self.text.get(self.pos).is_some_and(u8::is_ascii_digit) { self.pos += 1; digits += 1; }
        if self.text.get(self.pos) == Some(&b'.') {
            self.pos += 1;
            while self.text.get(self.pos).is_some_and(u8::is_ascii_digit) { self.pos += 1; digits += 1; }
        }
        if digits == 0 { return Err(Error::InvalidExpression); }
        if matches!(self.text.get(self.pos), Some(b'e' | b'E')) {
            self.pos += 1;
            if matches!(self.text.get(self.pos), Some(b'+' | b'-')) { self.pos += 1; }
            let exponent = self.pos;
            while self.text.get(self.pos).is_some_and(u8::is_ascii_digit) { self.pos += 1; }
            if exponent == self.pos { return Err(Error::InvalidExpression); }
        }
        let token = std::str::from_utf8(&self.text[start..self.pos]).map_err(|_| Error::InvalidExpression)?;
        finite(token.parse::<f64>().map_err(|_| Error::InvalidExpression)?)
    }
}

impl Rect {
    pub fn validate(self) -> Result<Self, Error> {
        let width = i64::from(self.right) - i64::from(self.left);
        let height = i64::from(self.bottom) - i64::from(self.top);
        if [self.left, self.right, self.top, self.bottom].iter().any(|&v| i64::from(v).abs() > COORD_LIMIT)
            || !(10_000..=COORD_LIMIT).contains(&width) || !(10_000..=COORD_LIMIT).contains(&height) {
            return Err(Error::InvalidGeometry);
        }
        Ok(self)
    }
    pub fn corner(self, index: i32) -> Point {
        Point { x: if index & 1 != 0 { self.right } else { self.left },
                y: if index & 2 != 0 { self.bottom } else { self.top } }
    }
    pub fn find_corner(self, point: Point, snapped: bool) -> i32 {
        if self.validate().is_err() { return -1; }
        let tolerance = if snapped {
            10_000.min((i64::from(self.right)-i64::from(self.left)).min(i64::from(self.bottom)-i64::from(self.top)) / 4)
        } else { 0 };
        for index in 0..4 {
            let q = self.corner(index);
            if (i64::from(point.x)-i64::from(q.x)).abs() <= tolerance && (i64::from(point.y)-i64::from(q.y)).abs() <= tolerance { return index; }
        }
        -1
    }
    pub fn axis(self, start: Point, end: Point, measured: f64) -> i32 {
        if !measured.is_finite() || measured <= 0.0 { return -1; }
        let a = self.find_corner(start, true);
        let b = self.find_corner(end, true);
        if a < 0 || b < 0 { return -1; }
        match a ^ b { 1 => 0, 2 => 1, _ => -1 }
    }
    pub fn target_max(self, axis: i32, target: f64) -> Result<i32, Error> {
        self.validate()?;
        target_mm(target)?;
        let origin = match axis { 0 => self.left, 1 => self.top, _ => return Err(Error::InvalidArgument) };
        let end = i64::from(origin) + (target * IU_PER_MM).round() as i64;
        if end.abs() > COORD_LIMIT { return Err(Error::Range); }
        Ok(end as i32)
    }
    pub fn move_corner(self, p: Point, axis: i32, new_max: i32) -> Result<Point, Error> {
        self.validate()?;
        let origin = match axis { 0 => self.left, 1 => self.top, _ => return Err(Error::InvalidArgument) };
        if i64::from(new_max).abs() > COORD_LIMIT || i64::from(new_max)-i64::from(origin) < 10_000
            || i64::from(new_max)-i64::from(origin) > COORD_LIMIT { return Err(Error::Range); }
        let index = self.find_corner(p, true);
        if index < 0 { return Ok(p); }
        let mut point = self.corner(index);
        if axis == 0 && index & 1 != 0 { point.x = new_max; }
        if axis == 1 && index & 2 != 0 { point.y = new_max; }
        Ok(point)
    }
}

pub fn rect_from_vertices(points: &[Point], segments: bool) -> Result<Rect, Error> {
    if points.len() != if segments { 8 } else { 4 } { return Err(Error::InvalidGeometry); }
    let first = points[0];
    let mut rect = Rect { left: first.x, right: first.x, top: first.y, bottom: first.y };
    for p in points {
        if i64::from(p.x).abs() > COORD_LIMIT || i64::from(p.y).abs() > COORD_LIMIT { return Err(Error::Range); }
        rect.left = rect.left.min(p.x); rect.right = rect.right.max(p.x);
        rect.top = rect.top.min(p.y); rect.bottom = rect.bottom.max(p.y);
    }
    rect.validate()?;
    if !segments {
        let mut mask = 0_u8;
        for &p in points {
            let index = rect.find_corner(p, false);
            if index < 0 { return Err(Error::InvalidGeometry); }
            mask |= 1 << index;
        }
        if mask == 15 { return Ok(rect); }
    } else {
        let mut edges = 0_u16;
        let mut degree = [0; 4];
        for edge in points.chunks_exact(2) {
            let a = rect.find_corner(edge[0], false);
            let b = rect.find_corner(edge[1], false);
            if a < 0 || b < 0 || !matches!(a ^ b, 1 | 2) { return Err(Error::InvalidGeometry); }
            let key = 1 << (a.min(b) * 4 + a.max(b));
            if edges & key != 0 { return Err(Error::InvalidGeometry); }
            edges |= key;
            degree[a as usize] += 1; degree[b as usize] += 1;
        }
        if degree == [2; 4] { return Ok(rect); }
    }
    Err(Error::InvalidGeometry)
}

pub fn safe_dimension_span(start: Point, end: Point) -> bool {
    (f64::from(end.x)-f64::from(start.x)).hypot(f64::from(end.y)-f64::from(start.y)) <= COORD_LIMIT as f64
}

impl Circle {
    pub fn from_points(center: Point, end: Point) -> Result<Self, Error> {
        Self { center, radius: (f64::from(end.x)-f64::from(center.x)).hypot(f64::from(end.y)-f64::from(center.y)) }.validate()
    }
    pub fn validate(self) -> Result<Self, Error> {
        if !self.radius.is_finite() || !(5_000.0..=1_000_000_000.0).contains(&self.radius)
            || f64::from(self.center.x).abs()+self.radius > COORD_LIMIT as f64
            || f64::from(self.center.y).abs()+self.radius > COORD_LIMIT as f64 { return Err(Error::InvalidGeometry); }
        Ok(self)
    }
    pub fn distance(self, p: Point) -> f64 {
        (f64::from(p.x)-f64::from(self.center.x)).hypot(f64::from(p.y)-f64::from(self.center.y))
    }
    pub fn tolerance(self) -> f64 { self.radius.min(40_000.0) / 4.0 }
    pub fn on_circle(self, p: Point) -> bool { (self.distance(p)-self.radius).abs() <= self.tolerance() }
    pub fn dimension_factor(self, kind: i32, start: Point, end: Point, measured: f64) -> i32 {
        if self.validate().is_err() { return 0; }
        if kind == 1 { return i32::from(self.distance(start) <= self.tolerance() && self.on_circle(end)); }
        if kind != 2 || !measured.is_finite() || !self.on_circle(start) || !self.on_circle(end) { return 0; }
        let x = (f64::from(start.x)+f64::from(end.x))/2.0-f64::from(self.center.x);
        let y = (f64::from(start.y)+f64::from(end.y))/2.0-f64::from(self.center.y);
        if x.hypot(y) <= self.tolerance() && (measured-2.0*self.radius).abs() <= self.tolerance() { 2 } else { 0 }
    }
    pub fn target_radius(self, factor: i32, target: f64) -> Result<f64, Error> {
        self.validate()?;
        target_mm(target)?;
        if factor != 1 && factor != 2 { return Err(Error::InvalidArgument); }
        let radius = (target*IU_PER_MM).round() / f64::from(factor);
        Self { center: self.center, radius }.validate().map_err(|_| Error::Range)?;
        Ok(radius)
    }
    pub fn scaled_point(self, p: Point, new_radius: f64) -> Result<Point, Error> {
        self.validate()?;
        Self { center: self.center, radius: new_radius }.validate().map_err(|_| Error::Range)?;
        if !self.on_circle(p) { return Ok(p); }
        let scale = new_radius / self.distance(p);
        let x = (f64::from(self.center.x)+(f64::from(p.x)-f64::from(self.center.x))*scale).round();
        let y = (f64::from(self.center.y)+(f64::from(p.y)-f64::from(self.center.y))*scale).round();
        if x.abs() > COORD_LIMIT as f64 || y.abs() > COORD_LIMIT as f64 { return Err(Error::Range); }
        Ok(Point { x: x as i32, y: y as i32 })
    }
}

// FFI entrypoints use value structs to avoid exposing Rust references or allocation.
// A writable pointer must satisfy the documented caller contract, not just be non-null.
unsafe fn output<T>(ptr: *mut T, operation: impl FnOnce() -> Result<T, Error>) -> i32 {
    if ptr.is_null() { return Error::InvalidArgument as i32; }
    match catch_unwind(AssertUnwindSafe(operation)) {
        Ok(Ok(value)) => { unsafe { ptr.write(value); } 0 },
        Ok(Err(error)) => error as i32,
        Err(_) => Error::Panic as i32,
    }
}

/// # Safety
/// `text` must point to `length` readable bytes and `out` to a writable f64.
/// The two memory regions must not overlap; no pointer is retained.
#[no_mangle]
pub unsafe extern "C" fn sbd_parse_mm(text: *const u8, length: usize, out: *mut f64) -> i32 {
    if text.is_null() || length == 0 || length > 4096 { return Error::InvalidArgument as i32; }
    unsafe { output(out, || {
        let input = std::slice::from_raw_parts(text, length);
        let input = std::str::from_utf8(input).map_err(|_| Error::InvalidExpression)?;
        parse_mm(input)
    }) }
}

/// # Safety
/// Input must have exactly four points (rectangle) or eight (segments), all readable.
/// `out` must be writable and not overlap the input array.
#[no_mangle]
pub unsafe extern "C" fn sbd_rect_from_vertices(points: *const Point, count: usize, segments: i32, out: *mut Rect) -> i32 {
    if points.is_null() || !matches!(segments, 0 | 1) || count != if segments == 1 { 8 } else { 4 } { return Error::InvalidArgument as i32; }
    unsafe { output(out, || rect_from_vertices(std::slice::from_raw_parts(points, count), segments == 1)) }
}

#[no_mangle]
pub extern "C" fn sbd_rect_corner(rect: Rect, point: Point, snapped: i32) -> i32 {
    catch_unwind(|| rect.find_corner(point, snapped != 0)).unwrap_or(-1)
}
#[no_mangle]
pub extern "C" fn sbd_rect_axis(rect: Rect, start: Point, end: Point, measured: f64) -> i32 {
    catch_unwind(|| rect.axis(start, end, measured)).unwrap_or(-1)
}
/// # Safety
/// `out` must point to writable i32 storage.
#[no_mangle]
pub unsafe extern "C" fn sbd_rect_target_max(rect: Rect, axis: i32, target: f64, out: *mut i32) -> i32 {
    unsafe { output(out, || rect.target_max(axis, target)) }
}
/// # Safety
/// `out` must point to writable Point storage.
#[no_mangle]
pub unsafe extern "C" fn sbd_rect_move_corner(rect: Rect, point: Point, axis: i32, new_max: i32, out: *mut Point) -> i32 {
    unsafe { output(out, || rect.move_corner(point, axis, new_max)) }
}
#[no_mangle]
pub extern "C" fn sbd_safe_dimension_span(start: Point, end: Point) -> i32 {
    catch_unwind(|| i32::from(safe_dimension_span(start, end))).unwrap_or(0)
}
/// # Safety
/// `out` must point to writable Circle storage.
#[no_mangle]
pub unsafe extern "C" fn sbd_circle_from_points(center: Point, end: Point, out: *mut Circle) -> i32 {
    unsafe { output(out, || Circle::from_points(center, end)) }
}
#[no_mangle]
pub extern "C" fn sbd_circle_dimension_factor(circle: Circle, kind: i32, start: Point, end: Point, measured: f64) -> i32 {
    catch_unwind(|| circle.dimension_factor(kind, start, end, measured)).unwrap_or(0)
}
/// # Safety
/// `out` must point to writable f64 storage.
#[no_mangle]
pub unsafe extern "C" fn sbd_circle_target_radius(circle: Circle, factor: i32, target: f64, out: *mut f64) -> i32 {
    unsafe { output(out, || circle.target_radius(factor, target)) }
}
/// # Safety
/// `out` must point to writable Point storage.
#[no_mangle]
pub unsafe extern "C" fn sbd_circle_scaled_point(circle: Circle, point: Point, radius: f64, out: *mut Point) -> i32 {
    unsafe { output(out, || circle.scaled_point(point, radius)) }
}

#[cfg(test)]
mod tests;
