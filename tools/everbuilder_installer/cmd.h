#pragma once
#include <windows.h>

void cmd_run_async(const char *cmd, const char *cwd, int wait_for_exit);
int cmd_copy_build_to_src(const char *repo_root);
int cmd_check_python_installed(void);
int cmd_wait_for_http(const char *url, int max_seconds);
int cmd_check_http_url(const char *url, int timeout_seconds);
