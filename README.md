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

Web UI

Run the web UI (Flask) which provides a drag-and-drop upload builder:

```powershell
python build.py
```

Open `http://127.0.0.1:5000/everbuilder` in your browser. The web UI includes options to embed CSS directly and enable compression when supported by the server.

New: Windows GUI installer/launcher

A small Win32 launcher source is provided in `tools/everbuilder_installer/main.c`. It builds a simple GUI that can:

- Install Python dependencies from `requirements.txt`.
- Launch the web UI (`python build.py`).

To build the launcher with MinGW/GCC:

```powershell
gcc -O2 -Wall -o tools\everbuilder_installer\everbuilder-setup.exe tools\everbuilder_installer\main.c
```

To build with MSVC (Developer Command Prompt):

```cmd
cl /nologo /W3 /O2 /MD /Fe:tools\everbuilder_installer\everbuilder-setup.exe tools\everbuilder_installer\main.c
```

Security

- The launcher uses `powershell` for downloads in its original form; be mindful of networks and script-running policies.

Contributing

- Feel free to open issues or submit PRs.

Contact

- Please contact us on our discord at https://discord.gg/SsW6agAQxR
