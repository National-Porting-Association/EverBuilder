cmake_minimum_required(VERSION 3.8)
project(everbuilder_installer C)

set(CMAKE_C_STANDARD 11)

add_executable(everbuilder_installer WIN32
    main.c
    ui.c
    cmd.c
    downloader.c
)

target_include_directories(everbuilder_installer PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

if (WIN32)
    target_link_libraries(everbuilder_installer PRIVATE urlmon Shlwapi ws2_32)
    target_link_libraries(everbuilder_installer PRIVATE urlmon Shlwapi ws2_32 wininet)
endif()
