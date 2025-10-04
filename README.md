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

5. To enable Brotli compression for embedded assets:

```powershell
python -m pip install brotli
python build.py --cli --compress
```

## Quickstart (CLI)

1. Ensure Python 3.11+ is installed and on PATH.
2. Install dependencies used by the builder:

```powershell
python -m pip install -r requirements.txt
```

3. Edit `files.txt` to include the files you want embedded (one per line).
4. Run the CLI builder:

```powershell
python build.py --cli --embed-css
```

5. To enable Brotli compression for embedded assets:

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
- Launch Web UI.
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

## Contributing

- Open issues or PRs with improvements.

## Contact

- Chat on our Discord: https://discord.gg/SsW6agAQxR
