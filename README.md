EverBuilder
==================

What this repository contains

- `build.py` - A Python-based builder that embeds web game resources into a single offline HTML (`offline.html`). Supports direct CSS embedding and optional Brotli compression of embedded assets.
- `files.txt` - A list of files to embed (used by `build.py`).
- `src/` - Frontend UI for the builder and multiple loader templates.
- `tools/everbuilder_installer/` - A small Windows GUI launcher (`main.c`) and build instructions to compile it into an `.exe`.

Quickstart (CLI)

1. Ensure Python 3.11+ is installed and on PATH.
2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Edit `files.txt` to include the files you want embedded (one per line).
4. Run the CLI builder (embeds CSS directly when `--embed-css` is passed):

```powershell
python build.py --cli --embed-css
```

5. To enable Brotli compression for embedded assets (only when `brotli` is installed):

```powershell
python -m pip install brotli
python build.py --cli --compress
```

Web UI

Run the web UI (Flask) which provides a drag-and-drop upload builder:

```powershell
python build.py
```

Open `http://127.0.0.1:5000/everbuilder` in your browser. The web UI includes options to embed CSS directly and enable compression when supported by the server.

New: Windows GUI installer/launcher

A small Win32 launcher source is provided in `tools/everbuilder_installer/main.c`. It builds a simple GUI that can:

- Install Python dependencies from `requirements.txt`.
- Copy `build.py` into the `src/` folder.
- Launch the web UI (`python build.py`).

To build the launcher with MinGW/GCC:

```powershell
gcc -O2 -Wall -o tools\everbuilder_installer\everbuilder-setup.exe tools\everbuilder_installer\main.c
```

To build with MSVC (Developer Command Prompt):

```cmd
cl /nologo /W3 /O2 /MD /Fe:tools\everbuilder_installer\everbuilder-setup.exe tools\everbuilder_installer\main.c
```

Caveats & Notes

- Silent Python installer actions (if you modify the launcher to download and install Python) may require Administrator privileges.
- Brotli compression is optional but recommended for smaller embedded payloads. If `brotli` isn't installed, `--compress` falls back to uncompressed embedding.
- The embedded fetch monkeypatch in the generated HTML attempts browser-native decompression with `DecompressionStream` when possible; otherwise it serves compressed blobs with a `Content-Encoding` header as a fallback.

Security

- The launcher uses `powershell` for downloads in its original form; be mindful of networks and script-running policies.

Contributing

- Feel free to open issues or submit PRs for making the launcher more robust (proper elevated installs, progress, checksums for downloaded installers, unsigned distribution packaging, NSIS/Inno Setup scripts).

Contact

- This code was generated and adapted in-repo. For questions about usage, open an issue in this repository.
