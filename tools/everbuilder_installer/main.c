#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// EverBuilder GUI launcher (Windows)
// - Small Win32 window with buttons to:
//   * Install dependencies (python -m pip install -r requirements.txt)
//   * Copy build.py into ./src
//   * Launch the web UI (python build.py)
//   * Exit
// - Runs commands asynchronously and appends simple status messages to a log box.
//
// Notes:
// - This program does not bundle Python. It shells out to the system `python` in PATH.
// - The launcher keeps things intentionally simple: commands are run with CreateProcess
//   and the UI is updated when the process exits. No stdout capture is implemented.

// Control IDs
#define IDC_INSTALL 1001
#define IDC_COPY    1002
#define IDC_LAUNCH  1003
#define IDC_EXIT    1004
#define IDC_LOG     2001

static HWND g_hEdit = NULL;
static HWND g_hWnd = NULL;

static void AppendLog(const char *fmt, ...) {
    char buf[2048];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    // Append newline
    strncat(buf, "\r\n", sizeof(buf) - strlen(buf) - 1);
    if (g_hEdit) {
        // move selection to end and replace (EM_REPLACESEL)
        SendMessageA(g_hEdit, EM_SETSEL, (WPARAM)-1, (LPARAM)-1);
        SendMessageA(g_hEdit, EM_REPLACESEL, FALSE, (LPARAM)buf);
    }
}

struct CmdThreadArg { char cmd[4096]; char cwd[MAX_PATH]; int wait; };

static DWORD WINAPI CmdThreadFunc(LPVOID lpParam) {
    struct CmdThreadArg *a = (struct CmdThreadArg*)lpParam;
    if (!a) return 0;
    AppendLog("Starting: %s", a->cmd);

    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    // If cwd provided, use it
    LPSTR cmdline = a->cmd;
    BOOL ok = CreateProcessA(NULL, cmdline, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, a->cwd[0] ? a->cwd : NULL, &si, &pi);
    if (!ok) {
        DWORD e = GetLastError();
        AppendLog("CreateProcess failed (err=%lu) for: %s", e, a->cmd);
        free(a);
        return 1;
    }

    if (a->wait) {
        DWORD r = WaitForSingleObject(pi.hProcess, INFINITE);
        DWORD exit_code = 0;
        GetExitCodeProcess(pi.hProcess, &exit_code);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        AppendLog("Finished: %s (exit %lu)", a->cmd, exit_code);
    } else {
        // don't wait; detach handles
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        AppendLog("Launched (detached): %s", a->cmd);
    }

    free(a);
    return 0;
}

static void RunCommandAsync(const char *cmd, const char *cwd, int wait_for_exit) {
    struct CmdThreadArg *a = (struct CmdThreadArg*)malloc(sizeof(struct CmdThreadArg));
    if (!a) return;
    memset(a, 0, sizeof(*a));
    strncpy(a->cmd, cmd, sizeof(a->cmd)-1);
    if (cwd) strncpy(a->cwd, cwd, sizeof(a->cwd)-1);
    a->wait = wait_for_exit;
    HANDLE h = CreateThread(NULL, 0, CmdThreadFunc, a, 0, NULL);
    if (h) CloseHandle(h);
}

static int CopyBuildToSrc(const char *repo_root) {
    char src_dir[MAX_PATH];
    snprintf(src_dir, MAX_PATH, "%s\\src", repo_root);
    DWORD attr = GetFileAttributesA(src_dir);
    if (attr == INVALID_FILE_ATTRIBUTES || !(attr & FILE_ATTRIBUTE_DIRECTORY)) {
        if (!CreateDirectoryA(src_dir, NULL)) {
            AppendLog("Failed to create src directory: %s", src_dir);
            // continue (try copying anyway)
        } else {
            AppendLog("Created src directory: %s", src_dir);
        }
    }
    char src_build[MAX_PATH];
    char root_build[MAX_PATH];
    snprintf(src_build, MAX_PATH, "%s\\src\\build.py", repo_root);
    snprintf(root_build, MAX_PATH, "%s\\build.py", repo_root);
    DWORD attr2 = GetFileAttributesA(root_build);
    if (attr2 == INVALID_FILE_ATTRIBUTES) {
        AppendLog("Source build.py not found at %s", root_build);
        return 1;
    }
    if (!CopyFileA(root_build, src_build, FALSE)) {
        DWORD e = GetLastError();
        AppendLog("CopyFile failed (%lu) from %s to %s", e, root_build, src_build);
        return 1;
    }
    AppendLog("Copied %s -> %s", root_build, src_build);
    return 0;
}

LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
    case WM_CREATE: {
        // Buttons
        CreateWindowA("BUTTON", "Install Dependencies", WS_TABSTOP|WS_VISIBLE|WS_CHILD|BS_DEFPUSHBUTTON,
            10, 10, 160, 30, hWnd, (HMENU)IDC_INSTALL, (HINSTANCE)GetWindowLongPtr(hWnd, GWLP_HINSTANCE), NULL);
        CreateWindowA("BUTTON", "Copy build.py to src", WS_TABSTOP|WS_VISIBLE|WS_CHILD,
            180, 10, 160, 30, hWnd, (HMENU)IDC_COPY, (HINSTANCE)GetWindowLongPtr(hWnd, GWLP_HINSTANCE), NULL);
        CreateWindowA("BUTTON", "Launch Web UI", WS_TABSTOP|WS_VISIBLE|WS_CHILD,
            350, 10, 120, 30, hWnd, (HMENU)IDC_LAUNCH, (HINSTANCE)GetWindowLongPtr(hWnd, GWLP_HINSTANCE), NULL);
        CreateWindowA("BUTTON", "Exit", WS_TABSTOP|WS_VISIBLE|WS_CHILD,
            480, 10, 80, 30, hWnd, (HMENU)IDC_EXIT, (HINSTANCE)GetWindowLongPtr(hWnd, GWLP_HINSTANCE), NULL);

        // Log multi-line edit
        g_hEdit = CreateWindowExA(WS_EX_CLIENTEDGE, "EDIT", "",
            WS_CHILD|WS_VISIBLE|WS_VSCROLL|ES_LEFT|ES_MULTILINE|ES_AUTOVSCROLL|ES_READONLY,
            10, 50, 550, 300, hWnd, (HMENU)IDC_LOG, (HINSTANCE)GetWindowLongPtr(hWnd, GWLP_HINSTANCE), NULL);

        AppendLog("EverBuilder launcher ready.");
        break;
    }
    case WM_COMMAND: {
        int id = LOWORD(wParam);
        if (id == IDC_INSTALL) {
            char cwd[MAX_PATH];
            if (!GetCurrentDirectoryA(MAX_PATH, cwd)) strcpy(cwd, ".");
            // Run pip install in repo root and wait
            char cmd[4096];
            snprintf(cmd, sizeof(cmd), "python -m pip install -r \"%s\\requirements.txt\"", cwd);
            RunCommandAsync(cmd, cwd, 1);
        } else if (id == IDC_COPY) {
            char cwd[MAX_PATH];
            if (!GetCurrentDirectoryA(MAX_PATH, cwd)) strcpy(cwd, ".");
            int r = CopyBuildToSrc(cwd);
            if (r == 0) AppendLog("Copy succeeded.");
        } else if (id == IDC_LAUNCH) {
            char cwd[MAX_PATH];
            if (!GetCurrentDirectoryA(MAX_PATH, cwd)) strcpy(cwd, ".");
            // Ensure build.py exists in repo root; launch python build.py (no --cli)
            char cmd[4096];
            snprintf(cmd, sizeof(cmd), "python build.py");
            // Launch detached so UI remains available
            RunCommandAsync(cmd, cwd, 0);
        } else if (id == IDC_EXIT) {
            PostQuitMessage(0);
        }
        break;
    }
    case WM_SIZE: {
        RECT rc;
        GetClientRect(hWnd, &rc);
        if (g_hEdit) {
            SetWindowPos(g_hEdit, NULL, 10, 50, rc.right - 20, rc.bottom - 60, SWP_NOZORDER);
        }
        break;
    }
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcA(hWnd, msg, wParam, lParam);
}

int APIENTRY WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    const char *CLASS_NAME = "EverBuilderLauncherClass";

    WNDCLASSA wc = {0};
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.lpszClassName = CLASS_NAME;

    RegisterClassA(&wc);

    g_hWnd = CreateWindowExA(0, CLASS_NAME, "EverBuilder Setup",
        WS_OVERLAPPEDWINDOW & ~WS_MAXIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT, 600, 420,
        NULL, NULL, hInstance, NULL);

    if (!g_hWnd) return 0;

    ShowWindow(g_hWnd, nCmdShow);

    MSG msg;
    while (GetMessageA(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageA(&msg);
    }

    return (int)msg.wParam;
}
