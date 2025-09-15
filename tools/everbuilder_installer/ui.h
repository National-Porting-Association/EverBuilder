#pragma once
#include <windows.h>

typedef void (*OnInstallCallback)(HWND hwnd);
typedef void (*OnCopyCallback)(HWND hwnd);
typedef void (*OnLaunchCallback)(HWND hwnd);
typedef void (*OnLaunchEmbeddedCallback)(HWND hwnd);

int ui_init(HINSTANCE hInstance, OnInstallCallback onInstall, OnCopyCallback onCopy, OnLaunchCallback onLaunch, OnLaunchEmbeddedCallback onLaunchEmbedded);
void ui_append_log(const char *fmt, ...);
HWND ui_get_main_hwnd(void);
void ui_set_status(const char *fmt, ...);
void ui_set_status_color(COLORREF text, COLORREF back);
