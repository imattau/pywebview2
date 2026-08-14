# CLI toolchain

pywebview ships an optional CLI, inspired by Tauri's `init`/`dev`/`build` workflow, that scaffolds a project and turns it into native installers. Install it with:

``` bash
pip install pywebview[cli]
```

This is the recommended path for new projects. For advanced or fully custom freezing setups, see [Freezing](freezing.md), which the CLI's `build` command builds on top of.

## `pywebview init`

Scaffolds a new project:

``` bash
pywebview init my-app --name "My App" --identifier com.example.myapp
```

This creates `pywebview.conf.json`, `main.py`, and a `frontend/` directory with a minimal HTML/CSS/JS starting point.

## `pywebview.conf.json`

Project configuration, analogous to `tauri.conf.json`. Key fields:

- `entry` — Python entry point that calls `webview.start()`
- `window` — passthrough of `webview.create_window()` kwargs
- `bundle.targets` — installer formats to build: `msi`, `nsis`, `dmg`, `deb`, `appimage`
- `bundle.pyinstaller` — PyInstaller passthrough (`onefile`, `excludes`, `extraArgs`)
- `bundle.windows.webview2InstallMode` — how the WebView2 runtime is provisioned
- `bundle.linux.debDepends` — native package dependencies declared in the generated `.deb`

Run `pywebview config` to print the fully resolved configuration (defaults merged with your file) and validate it.

## `pywebview dev`

Runs the app with `PYWEBVIEW_DEV=1` set and debug/devtools enabled. (Frontend hot-reload without a full restart is planned for a later release; for now, `dev` reruns the entry point.)

## `pywebview build`

Freezes the app with PyInstaller (reusing the `webview.__pyinstaller` hook automatically), then builds any installer formats listed in `bundle.targets` for the current OS:

| Target | Platform | External tool required |
|---|---|---|
| `msi` | Windows | [WiX Toolset](https://wixtoolset.org/) |
| `nsis` | Windows | [NSIS](https://nsis.sourceforge.io/) |
| `dmg` | macOS | `hdiutil` (built in) |
| `deb` | Linux | `dpkg-deb` |
| `appimage` | Linux | [appimagetool](https://github.com/AppImage/appimagetool) |
| `android` | Linux | [buildozer](https://buildozer.readthedocs.io/) + Android SDK/NDK/Java |

`build` only attempts targets that are buildable on the host OS -- there is no cross-compilation for installers (e.g. a `.dmg` requires building on macOS). Run `pywebview doctor` to check which external tools are available locally.

WebKitGTK (Linux) cannot be bundled; `.deb` declares it via `Depends:` and AppImage builds print a warning that it must already be present on the target system. WebView2 (Windows) is provisioned per `bundle.windows.webview2InstallMode`.

`android` skips the PyInstaller freeze step (buildozer/python-for-android does its own build) and instead templates a `buildozer.spec` from `mobile.android.buildozerSpecOverrides` and runs `buildozer android debug` (or `--release` for a release build). The entry point must be named `main.py`, which buildozer requires. This wraps the existing manual buildozer workflow described in [Freezing](freezing.md#android) -- pywebview's Android backend itself (Kivy/pyjnius-based) is unchanged.

## `pywebview icon`

Generates a `.ico`, `.icns`, and a set of PNGs from a single source image:

``` bash
pywebview icon logo.png --output icons
```

## `pywebview doctor`

Checks the local environment: Python version, which pywebview backend is importable, and which external packaging tools (WiX, NSIS, dpkg-deb, appimagetool, buildozer) are on `PATH`.
