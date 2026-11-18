# Rust dimension core

This crate implements expression evaluation and outline mathematics independently
of KiCad. It builds an `rlib` and the `smartboard_dimension_core` static library.
It has no third-party Rust dependencies. License: GPL-3.0-or-later.

```sh
cargo test -p sbd-rust-core
cargo build -p sbd-rust-core --release
```

The C ABI is declared in `include/sbd_rust.h`. Geometry coordinates and lengths
use KiCad nanometers; expression values and target input lengths use millimeters.
The ABI does not allocate memory for its caller, retain pointers, call the editor,
or modify board objects. Output-pointer functions write only when returning
`SBD_OK`. Callers must provide valid, properly aligned buffers of the stated sizes.
Rust panics are caught at the FFI boundary with the workspace `panic = "unwind"`
profile. Invalid/dangling C pointers are still caller errors and cannot be caught
by Rust unwinding.

The C++ adapter owns selection, board objects, layer/type checks, locks, mutation
preflight, and the `BOARD_COMMIT` Undo transaction. Functions accepting a linear
dimension assume that the adapter has already checked aligned/orthogonal type.

Input supports numbers, unary signs, `+ - * /`, parentheses, and `mm`, `cm`, `m`,
`um`, `in`, `inch`, `inches`, `mil`, `mils` unit suffixes. Unit names are case
insensitive. Full-width Japanese digits/operators are normalized. Input is limited
to 256 Unicode characters and bounded nesting; variables, functions, assignments,
implicit multiplication and executable syntax are rejected. Only final lengths
between 0.01 and 1000 mm are accepted. Scientific notation is supported.

Rectangle geometry retains the native exact 4-edge topology validation and
size-dependent corner tolerance. Circle edits preserve their center and polar
direction; the minimum radius is 0.005 mm so a 0.01 mm diameter remains editable.
All geometry computations use widened differences before integer conversion.
Related dimensions are limited to 2000 mm and coordinates to +/-2000 mm.

The unit tests run without KiCad. `native/tests/cpp_bridge_smoke.cpp` additionally
compiles the actual adapter headers against in-memory stand-ins and links this
real static library. It checks the ABI and mutation preflight, and is not a KiCad
application or GUI test.
