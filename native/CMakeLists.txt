cmake_minimum_required(VERSION 3.20)
project(vt_dsp LANGUAGES CXX)

add_library(vt_dsp STATIC src/dsp.cpp)
target_compile_features(vt_dsp PUBLIC cxx_std_17)
target_include_directories(vt_dsp PUBLIC include)

include(CTest)
if(BUILD_TESTING)
    include(FetchContent)
    set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
    FetchContent_Declare(googletest
        GIT_REPOSITORY https://github.com/google/googletest.git
        GIT_TAG v1.14.0
        GIT_SHALLOW TRUE)
    FetchContent_MakeAvailable(googletest)
    add_executable(test_dsp tests/test_dsp.cpp)
    target_link_libraries(test_dsp PRIVATE vt_dsp GTest::gtest_main)
    include(GoogleTest)
    gtest_discover_tests(test_dsp)
endif()
