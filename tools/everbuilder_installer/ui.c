#include "ui.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <shlwapi.h>

// Control IDs
#define IDC_INSTALL 1001
#define IDC_COPY    1002
#define IDC_LAUNCH  1003
#define IDC_LAUNCH_EMBED 1005
#define IDC_EXIT    1004
#define IDC_LOG     2001

static HWND g_hEdit = NULL;
static HWND g_hWnd = NULL;
static HWND g_hStatus = NULL;
static COLORREF g_status_color = RGB(240,240,240);

static OnInstallCallback g_onInstall = NULL;
static OnCopyCallback g_onCopy = NULL;
static OnLaunchCallback g_onLaunch = NULL;
static OnLaunchEmbeddedCallback g_onLaunchEmbedded = NULL;

static COLORREF g_status_text = RGB(0,0,0);
static COLORREF g_status_back = RGB(240,240,240);

static void AppendLogInternal(const char *fmt, va_list ap) {
    char buf[4096];
    vsnprintf(buf, sizeof(buf), fmt, ap);
    strncat(buf, "\r\n", sizeof(buf) - strlen(buf) - 1);
    if (g_hEdit) {
        SendMessageA(g_hEdit, EM_SETSEL, (WPARAM)-1, (LPARAM)-1);
        SendMessageA(g_hEdit, EM_REPLACESEL, FALSE, (LPARAM)buf);
    }
}

void ui_append_log(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    AppendLogInternal(fmt, ap);
    va_end(ap);
}

void ui_set_status(const char *fmt, ...) {
    if (!g_hStatus) return;
    char buf[1024];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    SetWindowTextA(g_hStatus, buf);
}

// ui_set_status_color is implemented later with (COLORREF text, COLORREF back)

HWND ui_get_main_hwnd(void) { return g_hWnd; }

LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
    case WM_CREATE: {
        CreateWindowA("BUTTON", "Install Dependencies", WS_TABSTOP|WS_VISIBLE|WS_CHILD|BS_DEFPUSHBUTTON,
            10, 10, 160, 30, hWnd, (HMENU)IDC_INSTALL, (HINSTANCE)GetWindowLongPtr(hWnd, GWLP_HINSTANCE), NULL);
        CreateWindowA("BUTTON", "Copy build.py to src", WS_TABSTOP|WS_VISIBLE|WS_CHILD,
            180, 10, 160, 30, hWnd, (HMENU)IDC_COPY, (HINSTANCE)GetWindowLongPtr(hWnd, GWLP_HINSTANCE), NULL);
        CreateWindowA("BUTTON", "Launch Web UI", WS_TABSTOP|WS_VISIBLE|WS_CHILD,
            350, 10, 180, 30, hWnd, (HMENU)IDC_LAUNCH, (HINSTANCE)GetWindowLongPtr(hWnd, GWLP_HINSTANCE), NULL);
        CreateWindowA("BUTTON", "Launch Embedded UI", WS_TABSTOP|WS_VISIBLE|WS_CHILD,
            10, 50, 160, 30, hWnd, (HMENU)IDC_LAUNCH_EMBED, (HINSTANCE)GetWindowLongPtr(hWnd, GWLP_HINSTANCE), NULL);
        CreateWindowA("BUTTON", "Exit", WS_TABSTOP|WS_VISIBLE|WS_CHILD,
            480, 10, 80, 30, hWnd, (HMENU)IDC_EXIT, (HINSTANCE)GetWindowLongPtr(hWnd, GWLP_HINSTANCE), NULL);

        g_hStatus = CreateWindowA("STATIC", "Ready.", WS_CHILD|WS_VISIBLE|SS_LEFT,
            10, 80, 760, 16, hWnd, NULL, (HINSTANCE)GetWindowLongPtr(hWnd, GWLP_HINSTANCE), NULL);

        g_hEdit = CreateWindowExA(WS_EX_CLIENTEDGE, "EDIT", "",
            WS_CHILD|WS_VISIBLE|WS_VSCROLL|ES_LEFT|ES_MULTILINE|ES_AUTOVSCROLL|ES_READONLY,
            10, 100, 760, 440, hWnd, (HMENU)IDC_LOG, (HINSTANCE)GetWindowLongPtr(hWnd, GWLP_HINSTANCE), NULL);

        ui_append_log("EverBuilder launcher ready.");
        break;
    }
    case WM_COMMAND: {
        int id = LOWORD(wParam);
        if (id == IDC_INSTALL && g_onInstall) g_onInstall(hWnd);
        else if (id == IDC_COPY && g_onCopy) g_onCopy(hWnd);
        else if (id == IDC_LAUNCH && g_onLaunch) g_onLaunch(hWnd);
        else if (id == IDC_LAUNCH_EMBED && g_onLaunchEmbedded) g_onLaunchEmbedded(hWnd);
        else if (id == IDC_EXIT) PostQuitMessage(0);
        break;
    }
    case WM_CTLCOLORSTATIC: {
        HDC hdcStatic = (HDC)wParam;
        HWND h = (HWND)lParam;
        if (h == g_hStatus) {
            SetTextColor(hdcStatic, g_status_text);
            SetBkColor(hdcStatic, g_status_back);
            static HBRUSH hbr = NULL;
            if (hbr) DeleteObject(hbr);
            hbr = CreateSolidBrush(g_status_back);
            return (LRESULT)hbr;
        }
        break;
    }
    case WM_SIZE: {
        RECT rc;
        GetClientRect(hWnd, &rc);
        if (g_hStatus) {
            SetWindowPos(g_hStatus, NULL, 10, 80, rc.right - 20, 16, SWP_NOZORDER);
        }
        if (g_hEdit) {
            SetWindowPos(g_hEdit, NULL, 10, 100, rc.right - 20, rc.bottom - 110, SWP_NOZORDER);
        }
        break;
    }
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    
    case WM_CTLCOLOREDIT: {
        HDC hdc = (HDC)wParam;
        HWND hwndCtl = (HWND)lParam;
        if (hwndCtl == g_hEdit) {
            SetTextColor(hdc, RGB(220,220,220));
            SetBkColor(hdc, RGB(30,30,30));
            static HBRUSH hbrEdit = NULL;
            if (hbrEdit) DeleteObject(hbrEdit);
            hbrEdit = CreateSolidBrush(RGB(30,30,30));
            return (LRESULT)hbrEdit;
        }
        break;
    }
    }
    return DefWindowProcA(hWnd, msg, wParam, lParam);
}

int ui_init(HINSTANCE hInstance, OnInstallCallback onInstall, OnCopyCallback onCopy, OnLaunchCallback onLaunch, OnLaunchEmbeddedCallback onLaunchEmbedded) {
    const char *CLASS_NAME = "EverBuilderLauncherClass";

    WNDCLASSA wc = {0};
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.lpszClassName = CLASS_NAME;

    if (!RegisterClassA(&wc)) return 0;


    g_onInstall = onInstall;
    g_onCopy = onCopy;
    g_onLaunch = onLaunch;
    g_onLaunchEmbedded = onLaunchEmbedded;

    g_hWnd = CreateWindowExA(0, CLASS_NAME, "EverBuilder Setup",
        WS_OVERLAPPEDWINDOW & ~WS_MAXIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT, 800, 600,
        NULL, NULL, hInstance, NULL);

    if (!g_hWnd) return 0;

    ShowWindow(g_hWnd, SW_SHOWDEFAULT);
    UpdateWindow(g_hWnd);

    // Try load icon from repo (everlyst-icon.ico) next to executable
    char exe_path[MAX_PATH];
    GetModuleFileNameA(NULL, exe_path, MAX_PATH);
    PathRemoveFileSpecA(exe_path);
    char icon_path[MAX_PATH];
    snprintf(icon_path, MAX_PATH, "%s\\everlyst-icon.ico", exe_path);
    if (PathFileExistsA(icon_path)) {
        HICON hIcon = (HICON)LoadImageA(NULL, icon_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE);
        if (hIcon) SendMessageA(g_hWnd, WM_SETICON, ICON_SMALL, (LPARAM)hIcon);
    }

    // Create a larger font for controls
    HFONT hFont = (HFONT)GetStockObject(DEFAULT_GUI_FONT);
    LOGFONT lf;
    GetObjectA(hFont, sizeof(lf), &lf);
    lf.lfHeight = -14; // bigger
    HFONT hLargeFont = CreateFontIndirectA(&lf);
    // Apply font to top-level children
    HWND hwndChild = GetWindow(g_hWnd, GW_CHILD);
    while (hwndChild) {
        SendMessageA(hwndChild, WM_SETFONT, (WPARAM)hLargeFont, TRUE);
        hwndChild = GetNextWindow(hwndChild, GW_HWNDNEXT);
    }

    return 1;
}

void ui_set_status_color(COLORREF text, COLORREF back) {
    g_status_text = text; g_status_back = back;
    if (g_hStatus) InvalidateRect(g_hStatus, NULL, TRUE);
}
