#include <windows.h>
#include <stdio.h>
#include <string.h>

#include "ui.h"
#include "cmd.h"
#include "downloader.h"

static void on_install(HWND hwnd) {
    char cwd[MAX_PATH];
    if (!GetCurrentDirectoryA(MAX_PATH, cwd)) strcpy(cwd, ".");

    ui_append_log("Install Dependencies pressed. Checking Python...");
    if (!cmd_check_python_installed()) {
        ui_append_log("Python not detected. Will download and run installer.");
        char tmp_path[MAX_PATH];
        char sys_tmp[MAX_PATH];
        if (!GetTempPathA(MAX_PATH, sys_tmp)) strcpy(sys_tmp, ".");
        snprintf(tmp_path, MAX_PATH, "%spython-installer.exe", sys_tmp);
        // Use official python.org installer for Windows x86-64; adjust URL as needed.
        const char *py_url = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe";
        if (downloader_download_file(py_url, tmp_path) == 0) {
            // Run installer silently and wait
            // /quiet /passive options vary; use /quiet /norestart for MSI-like but python exe supports /quiet /passive as well.
            downloader_run_installer(tmp_path, "/quiet InstallAllUsers=1 PrependPath=1");
            ui_append_log("Python installer executed. After installation, please relaunch the app and press install dependencies again.");
            return;
        } else {
            ui_append_log("Failed to download Python installer. Aborting install step.");
            return;
        }
    }

    // Run pip install -r requirements.txt
    char cmdline[4096];
    snprintf(cmdline, sizeof(cmdline), "python -m pip install -r \"%s\\requirements.txt\"", cwd);
    cmd_run_async(cmdline, cwd, 1);
}

static void on_copy(HWND hwnd) {
    char cwd[MAX_PATH];
    if (!GetCurrentDirectoryA(MAX_PATH, cwd)) strcpy(cwd, ".");
    int r = cmd_copy_build_to_src(cwd);
    if (r == 0) ui_append_log("Copy succeeded.");
}

static void start_python_server(int no_browser) {
    char cwd[MAX_PATH];
    if (!GetCurrentDirectoryA(MAX_PATH, cwd)) strcpy(cwd, ".");
    char cmdline[4096];
    if (no_browser) snprintf(cmdline, sizeof(cmdline), "python build.py --no-browser");
    else snprintf(cmdline, sizeof(cmdline), "python build.py");
    cmd_run_async(cmdline, cwd, 0);
}

static void on_launch_browser(HWND hwnd) {
    start_python_server(0);
}

static void on_launch_embedded(HWND hwnd) {
    ui_append_log("Embedded launch requested. Starting web UI and attempting embedded view...");
    // Start the local web UI server (detached) without auto-opening a browser
    start_python_server(1);
    // Wait a short time for server to come up (simple approach)
    Sleep(1500);

    // Poll a few common dev ports to discover where the web server started (prioritize 5000)
    int ports_to_try[] = {5000, 8000, 3000, 8080};
    int found_port = 0;
        ui_set_status("Waiting for local web UI to become available...");
        ui_set_status_color(RGB(0,0,0), RGB(255,230,100));
    for (int i=0;i< (int)(sizeof(ports_to_try)/sizeof(ports_to_try[0])); ++i) {
        int p = ports_to_try[i];
        char urlcheck[256]; snprintf(urlcheck, sizeof(urlcheck), "http://127.0.0.1:%d/everbuilder", p);
        ui_append_log("Checking %s...", urlcheck);
        if (cmd_check_http_url(urlcheck, 6)) { // wait up to 6s per port
            found_port = p; break;
        }
    }

    if (found_port) {
    char url[256]; snprintf(url, sizeof(url), "http://127.0.0.1:%d/everbuilder", found_port);
    ui_append_log("Server reachable at %s", url);
    ui_set_status("Server ready: %s", url);
        ui_set_status_color(RGB(0,0,0), RGB(160,240,160));

        // try Edge app mode, else open default browser
        char edgePath[MAX_PATH] = "";
        HKEY hKey;
        if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\msedge.exe", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
            DWORD len = MAX_PATH;
            RegQueryValueExA(hKey, NULL, NULL, NULL, (LPBYTE)edgePath, &len);
            RegCloseKey(hKey);
        }
        if (edgePath[0]) {
            char cmd[4096]; snprintf(cmd, sizeof(cmd), "\"%s\" --app=%s", edgePath, url);
            ui_append_log("Launching embedded (Edge app): %s", cmd);
            cmd_run_async(cmd, NULL, 0);
        } else {
            ui_append_log("Edge not found; opening default browser to %s", url);
            ShellExecuteA(NULL, "open", url, NULL, NULL, SW_SHOWNORMAL);
        }
    } else {
        ui_append_log("Server did not become reachable on common ports. Opening default address 127.0.0.1:8000");
        ui_set_status("Server not reachable (connection refused)");
        ui_set_status_color(RGB(150,0,0), RGB(255,220,220));
        ShellExecuteA(NULL, "open", "http://127.0.0.1:8000/", NULL, NULL, SW_SHOWNORMAL);
    }
}

int APIENTRY WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    if (!ui_init(hInstance, on_install, on_copy, on_launch_browser, on_launch_embedded)) return 0;

    MSG msg;
    while (GetMessageA(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageA(&msg);
    }
    return (int)msg.wParam;
}
