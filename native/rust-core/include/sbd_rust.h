/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef SBD_RUST_H
#define SBD_RUST_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Geometry uses KiCad nanometers (1 mm = 1,000,000 units). */
typedef struct { int32_t x, y; } SbdPoint;
typedef struct { int32_t left, right, top, bottom; } SbdRect;
typedef struct { SbdPoint center; double radius; } SbdCircle;

enum SbdStatus {
    SBD_OK = 0, SBD_INVALID_ARGUMENT = 1, SBD_INVALID_EXPRESSION = 2,
    SBD_RANGE = 3, SBD_INVALID_GEOMETRY = 4, SBD_PANIC = 255
};

/* All output-pointer APIs write only on SBD_OK. Pointers must be aligned and
 * writable for their declared type, input buffers readable for the given length.
 * The caller owns all memory. Input/output memory must not overlap. Null pointers
 * are rejected. Arbitrary invalid/dangling pointers cannot be detected by the ABI.
 * No function retains pointers or invokes KiCad. Rust unwinding never crosses ABI.
 */
int32_t sbd_parse_mm(const uint8_t* utf8, size_t length, double* output);
/* segments=0: four rectangle vertices; segments=1: four start/end pairs. */
int32_t sbd_rect_from_vertices(const SbdPoint* points, size_t count, int32_t segments, SbdRect* output);
/* corner: -1 if unrelated/invalid, otherwise bit 0=right, bit 1=bottom. */
int32_t sbd_rect_corner(SbdRect rect, SbdPoint point, int32_t snapped);
/* Caller must establish that the dimension is aligned/orthogonal. */
int32_t sbd_rect_axis(SbdRect rect, SbdPoint start, SbdPoint end, double measured);
int32_t sbd_rect_target_max(SbdRect rect, int32_t axis, double target_mm, int32_t* output);
int32_t sbd_rect_move_corner(SbdRect rect, SbdPoint point, int32_t axis, int32_t new_max, SbdPoint* output);
int32_t sbd_safe_dimension_span(SbdPoint start, SbdPoint end);
int32_t sbd_circle_from_points(SbdPoint center, SbdPoint end, SbdCircle* output);
/* kind=1 radial, kind=2 aligned/orthogonal; return 0 unrelated, 1 radius, 2 diameter. */
int32_t sbd_circle_dimension_factor(SbdCircle circle, int32_t kind, SbdPoint start, SbdPoint end, double measured);
int32_t sbd_circle_target_radius(SbdCircle circle, int32_t factor, double target_mm, double* output);
int32_t sbd_circle_scaled_point(SbdCircle circle, SbdPoint point, double new_radius, SbdPoint* output);

#ifdef __cplusplus
}
#endif
#endif
