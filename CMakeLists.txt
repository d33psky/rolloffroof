cmake_minimum_required(VERSION 2.8)

project(rolloffroof)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11 -fPIC -D_REENTRANT")

include_directories(/usr/include)

add_executable(read_TSL237_pigpio ${PROJECT_SOURCE_DIR}/read_TSL237_pigpio.c)
TARGET_LINK_LIBRARIES(read_TSL237_pigpio -lpigpio -lpthread -lrt -lm)

