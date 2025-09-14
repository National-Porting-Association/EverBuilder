EverBuilder Installer Launcher (Windows)

What this helper does

- Small C console program that:
  - Checks whether `python` is on PATH.
  - If missing, optionally downloads the official Python 3.11.6 Windows installer and runs it silently.
  - Runs `python -m pip install -r requirements.txt` in the repository root.
  - Copies `build.py` into `src/build.py` (overwrites if present).
  - Launches `python build.py` from the `src` folder.

Files added

- `main.c` - the launcher source.
- `README.md` - these instructions.

How to build

Option A — MinGW (recommended for simple builds)

1. Install MinGW (or MSYS2) and ensure `gcc` is in PATH.
2. Open a Windows PowerShell terminal in the project root.
3. Compile:

```powershell
gcc -O2 -Wall -o tools\everbuilder_installer\everbuilder.exe tools\everbuilder_installer\main.c
```

Option B — Microsoft Visual C++ (cl.exe)

1. Open "x64 Native Tools Command Prompt for VS" or similar.
3. Compile:

```powershell
gcc -O2 -Wall -o tools\everbuilder_installer\everbuilder.exe tools\everbuilder_installer\main.c
```


How to run

1. Double-click `tools\everbuilder_installer\everbuilder.exe` from Explorer, or run it from PowerShell:

```powershell
& .\tools\everbuilder_installer\everbuilder.exe
```

2. Follow prompts to install Python if necessary.

Notes and limitations

- This helper uses `powershell` to download the official Python installer. It requires network access.
- The silent Python installer may require elevation. If installation fails, re-run the helper as Administrator or install Python manually.
- The helper assumes `requirements.txt` is present in the repository root and will attempt to run `python -m pip install -r requirements.txt`.
- This program is intentionally small and relies heavily on calling the system Python. It is not a full installer with rollback.

Security

- The tool downloads an installer from python.org. Verify you trust the network and python.org when using the helper.

Customization

- You can change the Python release URL in `main.c` to a different version or a local path.
