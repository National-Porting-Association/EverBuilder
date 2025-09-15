#pragma once
#include <windows.h>

int downloader_download_file(const char *url, const char *out_path);
int downloader_run_installer(const char *installer_path, const char *args);
