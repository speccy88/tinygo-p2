add_library(time OBJECT
    clock.c
    sleep.c
    usleep.c
    time.c
    difftime.c
    strftime.c
    localtim.c
    asctime.c
	settimeofday.c
    gettimeofday.c
)

target_include_directories(time PRIVATE ${CMAKE_SOURCE_DIR}/include)
# LLVM P2 r72a9bb1 asserts in LiveVariables for these two functions at -Oz.
# Keep the target library complete; compile only the crashing translation units
# at the verified lower optimization level rather than changing the backend.
set_source_files_properties(strftime.c localtim.c PROPERTIES COMPILE_OPTIONS "-O1")