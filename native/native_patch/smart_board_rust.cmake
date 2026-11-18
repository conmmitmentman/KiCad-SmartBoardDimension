# Included at the end of KiCad's top-level CMakeLists, after PCB/QA targets exist.
# Rust owns arithmetic/geometry. C++ retains board lifetimes, UI and BOARD_COMMIT.
find_program(SBD_CARGO cargo REQUIRED)
set(SBD_RUST_SOURCE "${CMAKE_SOURCE_DIR}/pcbnew/dialogs/smartboard-rust-core")
set(SBD_RUST_TARGET "${CMAKE_BINARY_DIR}/smartboard-rust-target")
if(MSVC)
    set(SBD_RUST_LIBRARY "${SBD_RUST_TARGET}/release/smartboard_dimension_core.lib")
else()
    set(SBD_RUST_LIBRARY "${SBD_RUST_TARGET}/release/libsmartboard_dimension_core.a")
endif()
file(GLOB_RECURSE SBD_RUST_INPUTS CONFIGURE_DEPENDS "${SBD_RUST_SOURCE}/src/*.rs")
add_custom_command(
    OUTPUT "${SBD_RUST_LIBRARY}"
    COMMAND "${SBD_CARGO}" build --manifest-path "${SBD_RUST_SOURCE}/Cargo.toml"
            --target-dir "${SBD_RUST_TARGET}" --release --offline
    DEPENDS ${SBD_RUST_INPUTS} "${SBD_RUST_SOURCE}/Cargo.toml"
    COMMENT "Building SmartBoardDimension Rust engine"
    VERBATIM)
add_custom_target(smartboard_rust_build DEPENDS "${SBD_RUST_LIBRARY}")
add_library(smartboard_rust STATIC IMPORTED GLOBAL)
set_target_properties(smartboard_rust PROPERTIES IMPORTED_LOCATION "${SBD_RUST_LIBRARY}")
add_dependencies(smartboard_rust smartboard_rust_build)
if(WIN32)
    # rustc --print native-static-libs, x86_64-pc-windows-msvc.
    target_link_libraries(smartboard_rust INTERFACE kernel32 ntdll userenv ws2_32 dbghelp synchronization)
else()
    find_package(Threads REQUIRED)
    target_link_libraries(smartboard_rust INTERFACE Threads::Threads ${CMAKE_DL_LIBS} m)
endif()
target_link_libraries(pcbnew_kiface_objects PUBLIC smartboard_rust)
add_dependencies(pcbnew_kiface_objects smartboard_rust_build)
