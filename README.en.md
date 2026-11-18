# SmartBoardDimension — Native

[日本語](README.md) · **English**

Click a dimension value in the KiCad 10.0.7 PCB Editor to resize a rectangular board or change a circle's radius or diameter with a number or formula. Rust handles dimension calculations and the Windows launcher. C++ connects the feature to KiCad's editor and undo system.

## Set up on Windows

The release is a source ZIP. The PCB Editor with native dimension editing and the launcher need to be built once before you register them.

1. Under **Assets** in the [latest release](https://github.com/conmmitmentman/KiCad-SmartBoardDimension/releases/latest), download the `KiCad10_NativeDrivingDimension_Source_v…zip` file and extract the whole archive.
2. Follow the [Windows build guide](native/RUST_MIGRATION_EN.md) to build the editor and the launcher.
3. Open `target\release\smartboard-launcher.exe`. Select **English**, choose **Register or change build folder**, and select the output folder containing `pcbnew`. If you already have a compatible native build, start with registration.

After registration, open **スマート基板寸法（ネイティブ版）** from the desktop or Start menu. The launcher can open a new board, an existing PCB, or the circle example. It remembers the build folder between sessions. Keep that folder on disk and register its new location if you move it.

## Switch between English and Japanese

- **Launcher** — Click **English** or **日本語** in the top-right corner. Your choice is saved for the next launch.
- **PCB Editor** — Use **Preferences → Set Language** and choose **English** or **日本語**. The native dimension editor and its validation messages follow this setting.
- The launcher uses its selected language to create the editor's settings on first launch. If editor settings already exist, use the PCB Editor's language menu to change them.

## Edit a dimension

1. Add a standard dimension to a rectangle or circle on `Edge.Cuts`. For a rectangle, snap to adjacent corners. For a circle, snap to the center and circumference for a radius, or to opposite points for a diameter.
2. Finish placing the dimension and click its value.
3. Enter a number or formula such as `30`, `2*15`, or `1in+5mm`. Press Enter to apply, Esc to cancel, or Ctrl+Z after applying to undo.

For dimensions on another layer, enable object snapping across visible layers. With the cursor over the canvas, use Shift+S to change the snapping mode. Resizing the outline keeps footprints and tracks in place.

Tests cover the Rust engine, the C++ bridge with synthetic boards, and the Windows launcher with simulated setup and launch. The full KiCad build and on-canvas behavior of this Rust version still need verification.

The workflow is inspired by SolidCraft. See [attribution](ATTRIBUTION.md) and [license information](LICENSE).
