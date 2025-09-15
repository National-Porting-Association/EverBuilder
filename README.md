EverBuilder
==================

Quickstart (CLI)

1. Ensure Python 3.11+ is installed and on PATH.
2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Edit `files.txt` to include the files you want embedded (one per line).
4. Run the CLI builder:

```powershell
python build.py --cli --embed-css
```

5. To enable Brotli compression for embedded assets (only when `brotli` is installed):

```powershell
python -m pip install brotli
python build.py --cli --compress
```

## Quickstart (CLI)

1. Ensure Python 3.11+ is installed and on PATH.
2. Install dependencies used by the builder (if you want to run the web UI):

```powershell
python -m pip install -r requirements.txt
```

3. Edit `files.txt` to include the files you want embedded (one per line).
4. Run the CLI builder:

```powershell
python build.py --cli --embed-css
```

5. To enable Brotli compression for embedded assets (optional):

```powershell
python -m pip install brotli
python build.py --cli --compress
```

## Web UI (Flask)

The web UI provides a drag-and-drop builder and a small HTTP API for builds.

Run the web UI:

```powershell
python build.py
```

Open `http://127.0.0.1:5000/everbuilder` in your browser.

Notes:
- When started normally the server will attempt to auto-open your default browser. If you want to suppress that behavior, pass `--no-browser`.

## Windows GUI installer / launcher

A Win32 launcher is available in `tools/everbuilder_installer/`. It provides a GUI with the following features:

- Install Dependencies.
- Copy `build.py` to `src`.
- Launch Web UI (default behavior).
- Launch Embedded UI

### Build with CMake

The launcher is a small multi-file C project with a `CMakeLists.txt` in `tools/everbuilder_installer/`. Build it with CMake on Windows (MSVC):

```powershell
cd tools\everbuilder_installer
mkdir build; cd build
cmake ..
cmake --build . --config Release
```

The built executable will be at `tools\everbuilder_installer\build\Release\everbuilder_installer.exe`.

## Next steps / Contributions

- If you want true in-window embedding, I can integrate WebView2 (I can implement dynamic loading to avoid needing the SDK at compile-time).
- If you have artwork/icons or a UI library you prefer, drop them into `tools/everbuilder_installer/third_party/` and I'll wire them into the UI.

## Contributing

- Open issues or PRs with improvements.

## Contact

- Chat on our Discord: https://discord.gg/SsW6agAQxR
