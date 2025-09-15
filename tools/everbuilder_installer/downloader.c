#include "downloader.h"
#include "ui.h"
#include <urlmon.h>
#include <shlwapi.h>
#include <stdio.h>
#include <string.h>

int downloader_download_file(const char *url, const char *out_path) {
    ui_append_log("Downloading: %s -> %s", url, out_path);
    HRESULT hr = URLDownloadToFileA(NULL, url, out_path, 0, NULL);
    if (hr != S_OK) {
        ui_append_log("Download failed (HRESULT=0x%08lX)", hr);
        return 1;
    }
    ui_append_log("Download succeeded: %s", out_path);
    return 0;
}

int downloader_run_installer(const char *installer_path, const char *args) {
    char cmdline[4096];
    if (args && args[0]) snprintf(cmdline, sizeof(cmdline), "\"%s\" %s", installer_path, args);
    else snprintf(cmdline, sizeof(cmdline), "\"%s\"", installer_path);

    ui_append_log("Launching installer: %s", cmdline);

    STARTUPINFOA si; PROCESS_INFORMATION pi; ZeroMemory(&si,sizeof(si)); si.cb = sizeof(si); ZeroMemory(&pi,sizeof(pi));
    BOOL ok = CreateProcessA(NULL, cmdline, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi);
    if (!ok) {
        DWORD e = GetLastError();
        ui_append_log("CreateProcess failed for installer (err=%lu)", e);
        return 1;
    }
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD exit_code = 0; GetExitCodeProcess(pi.hProcess, &exit_code);
    CloseHandle(pi.hProcess); CloseHandle(pi.hThread);
    ui_append_log("Installer finished (exit=%lu)", exit_code);
    return exit_code == 0 ? 0 : 1;
}
