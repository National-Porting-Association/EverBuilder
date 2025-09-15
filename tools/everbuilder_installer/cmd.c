#include "cmd.h"
#include "ui.h"
#include <windows.h>
#include <urlmon.h>
#include <shlwapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct CmdThreadArg { char cmd[4096]; char cwd[MAX_PATH]; int wait; };

static DWORD WINAPI CmdThreadFunc(LPVOID lpParam) {
    struct CmdThreadArg *a = (struct CmdThreadArg*)lpParam;
    if (!a) return 0;
    ui_append_log("Starting: %s", a->cmd);

    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    LPSTR cmdline = a->cmd;
    BOOL ok = CreateProcessA(NULL, cmdline, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, a->cwd[0] ? a->cwd : NULL, &si, &pi);
    if (!ok) {
        DWORD e = GetLastError();
        ui_append_log("CreateProcess failed (err=%lu) for: %s", e, a->cmd);
        free(a);
        return 1;
    }

    if (a->wait) {
        DWORD r = WaitForSingleObject(pi.hProcess, INFINITE);
        DWORD exit_code = 0;
        GetExitCodeProcess(pi.hProcess, &exit_code);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        ui_append_log("Finished: %s (exit %lu)", a->cmd, exit_code);
    } else {
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        ui_append_log("Launched (detached): %s", a->cmd);
    }

    free(a);
    return 0;
}

void cmd_run_async(const char *cmd, const char *cwd, int wait_for_exit) {
    struct CmdThreadArg *a = (struct CmdThreadArg*)malloc(sizeof(struct CmdThreadArg));
    if (!a) return;
    memset(a, 0, sizeof(*a));
    strncpy(a->cmd, cmd, sizeof(a->cmd)-1);
    if (cwd) strncpy(a->cwd, cwd, sizeof(a->cwd)-1);
    a->wait = wait_for_exit;
    HANDLE h = CreateThread(NULL, 0, CmdThreadFunc, a, 0, NULL);
    if (h) CloseHandle(h);
}

int cmd_copy_build_to_src(const char *repo_root) {
    char src_dir[MAX_PATH];
    snprintf(src_dir, MAX_PATH, "%s\\src", repo_root);
    DWORD attr = GetFileAttributesA(src_dir);
    if (attr == INVALID_FILE_ATTRIBUTES || !(attr & FILE_ATTRIBUTE_DIRECTORY)) {
        if (!CreateDirectoryA(src_dir, NULL)) {
            ui_append_log("Failed to create src directory: %s", src_dir);
        } else {
            ui_append_log("Created src directory: %s", src_dir);
        }
    }
    char src_build[MAX_PATH];
    char root_build[MAX_PATH];
    snprintf(src_build, MAX_PATH, "%s\\src\\build.py", repo_root);
    snprintf(root_build, MAX_PATH, "%s\\build.py", repo_root);
    DWORD attr2 = GetFileAttributesA(root_build);
    if (attr2 == INVALID_FILE_ATTRIBUTES) {
        ui_append_log("Source build.py not found at %s", root_build);
        return 1;
    }
    if (!CopyFileA(root_build, src_build, FALSE)) {
        DWORD e = GetLastError();
        ui_append_log("CopyFile failed (%lu) from %s to %s", e, root_build, src_build);
        return 1;
    }
    ui_append_log("Copied %s -> %s", root_build, src_build);
    return 0;
}

int cmd_check_python_installed(void) {
    // Try to run `python --version` and see if process can start and exit 0.
    STARTUPINFOA si; PROCESS_INFORMATION pi; ZeroMemory(&si,sizeof(si)); si.cb = sizeof(si); ZeroMemory(&pi,sizeof(pi));
    char cmd[] = "python --version";
    BOOL ok = CreateProcessA(NULL, cmd, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi);
    if (!ok) return 0;
    DWORD r = WaitForSingleObject(pi.hProcess, 5000);
    DWORD exit_code = 1;
    if (r == WAIT_OBJECT_0) GetExitCodeProcess(pi.hProcess, &exit_code);
    CloseHandle(pi.hProcess); CloseHandle(pi.hThread);
    return exit_code == 0 ? 1 : 0;
}

int cmd_check_http_url(const char *url, int timeout_seconds) {
    // Attempt to download the URL to a temporary file using URLDownloadToFileA.
    char tmp[MAX_PATH];
    char tmp_dir[MAX_PATH];
    if (!GetTempPathA(MAX_PATH, tmp_dir)) strcpy(tmp_dir, ".");
    snprintf(tmp, MAX_PATH, "%s\\everbuilder_probe.tmp", tmp_dir);

    ui_append_log("Checking URL: %s", url);
    // Try repeatedly until timeout
    int attempts = timeout_seconds * 2;
    for (int i=0;i<attempts;i++) {
        HRESULT hr = URLDownloadToFileA(NULL, url, tmp, 0, NULL);
        if (hr == S_OK) {
            DeleteFileA(tmp);
            return 1;
        }
        Sleep(500);
    }
    return 0;
}
