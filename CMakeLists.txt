cmake_minimum_required(VERSION 3.24)
project(kestrel VERSION 0.1.0 LANGUAGES C)

if(NOT CMAKE_SYSTEM_NAME MATCHES "^(Linux|Darwin)$")
    message(FATAL_ERROR "M0 supports the FreeRTOS POSIX port on Linux and macOS.")
endif()
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

include(FetchContent)
add_library(freertos_config INTERFACE)
target_include_directories(freertos_config INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}/fsw")
set(FREERTOS_PORT GCC_POSIX CACHE STRING "FreeRTOS port")
if(NOT FREERTOS_PORT STREQUAL "GCC_POSIX")
    message(FATAL_ERROR "Only GCC_POSIX is supported in M0.")
endif()
# V11.3.2, resolved to an immutable commit. No FreeRTOS heap implementation.
FetchContent_Declare(freertos_kernel
    GIT_REPOSITORY https://github.com/FreeRTOS/FreeRTOS-Kernel.git
    GIT_TAG 8a59a4b19bf72977819feddef87d41163ced7004
    GIT_SUBMODULES ""
)
FetchContent_MakeAvailable(freertos_kernel)
# Strict C11 hides POSIX.1-2008 declarations in glibc unless requested explicitly.
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    target_compile_definitions(freertos_kernel_port PRIVATE _POSIX_C_SOURCE=200809L)
endif()

add_executable(kestrel_m0 fsw/src/main.c fsw/src/stack_hook.c)
target_link_libraries(kestrel_m0 PRIVATE freertos_kernel)
target_compile_options(kestrel_m0 PRIVATE -Wall -Wextra -Werror)
# Apply the warning gate to the dependency too, without changing its sources.
target_compile_options(freertos_kernel PRIVATE -Wall -Wextra -Werror)
target_compile_options(freertos_kernel_port PRIVATE -Wall -Wextra -Werror)

add_library(kestrel_packets STATIC fsw/src/ccsds/packet.c fsw/src/ccsds/crc16.c)
target_include_directories(kestrel_packets PUBLIC fsw/include)
target_compile_options(kestrel_packets PRIVATE -Wall -Wextra -Werror)
option(KESTREL_SANITIZERS "Instrument the host packet library and its consumers" OFF)
if(KESTREL_SANITIZERS)
    target_compile_options(kestrel_packets PUBLIC -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(kestrel_packets PUBLIC -fsanitize=address,undefined)
endif()
add_executable(kestrel_packet_probe tools/packet_probe.c)
target_link_libraries(kestrel_packet_probe PRIVATE kestrel_packets)
target_compile_options(kestrel_packet_probe PRIVATE -Wall -Wextra -Werror)

set(FLIGHT_SOURCES fsw/src/flight.c fsw/src/runtime.c fsw/src/stack_hook.c
    fsw/src/tasks/link.c fsw/src/tasks/command.c fsw/src/tasks/mode.c
    fsw/src/tasks/telemetry.c fsw/src/tasks/sensors.c fsw/src/tasks/watchdog.c
    fsw/src/hal/udp_link.c)
add_executable(kestrel_flight ${FLIGHT_SOURCES})
target_link_libraries(kestrel_flight PRIVATE freertos_kernel kestrel_packets)
target_compile_options(kestrel_flight PRIVATE -Wall -Wextra -Werror)

# Deliberately separate binary: injection dispatch and observation are test-only.
add_executable(kestrel_flight_test ${FLIGHT_SOURCES})
target_compile_definitions(kestrel_flight_test PRIVATE KESTREL_TEST=1)
target_link_libraries(kestrel_flight_test PRIVATE freertos_kernel kestrel_packets)
target_compile_options(kestrel_flight_test PRIVATE -Wall -Wextra -Werror)

include(CTest)
if(BUILD_TESTING)
    find_package(Python3 3.9 REQUIRED COMPONENTS Interpreter)
    foreach(pair IN ITEMS "test_fsw_001_boot_safe;boot" "test_fsw_007_invalid_commands;invalid" "test_fsw_008_ack_deadline;deadline" "m2_safe_housekeeping;periodic")
        list(GET pair 0 test_name)
        list(GET pair 1 suite)
        add_test(NAME ${test_name} COMMAND "${Python3_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/integration/flight_link.py" "$<TARGET_FILE:kestrel_flight>" ${suite})
        set_tests_properties(${test_name} PROPERTIES TIMEOUT 25 RUN_SERIAL TRUE)
    endforeach()
    foreach(pair IN ITEMS "test_fsw_002_safe_exit;safe" "test_fsw_003_hk_timing;timing" "test_fsw_004_hk_rate;rate" "test_fsw_009_command_counts;counts" "test_fsw_013_safe_commands;allowlist" "test_fsw_015_att_modes;att")
        list(GET pair 0 test_name)
        list(GET pair 1 suite)
        add_test(NAME ${test_name} COMMAND "${Python3_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/integration/flight_modes.py" "$<TARGET_FILE:kestrel_flight>" ${suite})
        set_tests_properties(${test_name} PROPERTIES TIMEOUT 30 RUN_SERIAL TRUE)
    endforeach()
    foreach(pair IN ITEMS "test_fsw_010_battery_hysteresis;battery" "test_fsw_011_critical_faults;critical" "test_fsw_012_watchdog_safe;watchdog" "test_fsw_014_fault_events;events")
        list(GET pair 0 test_name)
        list(GET pair 1 suite)
        add_test(NAME ${test_name} COMMAND "${Python3_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/integration/fault_recovery.py" "$<TARGET_FILE:kestrel_flight_test>" ${suite})
        set_tests_properties(${test_name} PROPERTIES TIMEOUT 60 RUN_SERIAL TRUE)
    endforeach()
    add_executable(test_link_gate tests/smoke/link_gate.c fsw/src/tasks/link.c fsw/src/runtime.c fsw/src/stack_hook.c)
    target_link_libraries(test_link_gate PRIVATE freertos_kernel kestrel_packets)
    target_compile_options(test_link_gate PRIVATE -Wall -Wextra -Werror)
    add_test(NAME test_fsw_015_link_backpressure COMMAND test_link_gate)
    set_tests_properties(test_fsw_015_link_backpressure PROPERTIES TIMEOUT 10 RUN_SERIAL TRUE)
    foreach(pair IN ITEMS "test_fsw_012_mode_health;health" "test_fsw_014_overflow;overflow" "test_fsw_015_flush;att")
        list(GET pair 0 hardening_name)
        list(GET pair 1 suite)
        add_test(NAME ${hardening_name} COMMAND "${Python3_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/integration/hardening.py" "$<TARGET_FILE:kestrel_flight>" ${suite})
        set_tests_properties(${hardening_name} PROPERTIES TIMEOUT 20 RUN_SERIAL TRUE)
    endforeach()
    add_test(NAME m5_mission_demo COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tools/record_m5.py" --binary "$<TARGET_FILE:kestrel_flight>"
        --output "${CMAKE_CURRENT_BINARY_DIR}/release/demo")
    set_tests_properties(m5_mission_demo PROPERTIES TIMEOUT 30 RUN_SERIAL TRUE)
    add_test(NAME m5_build_inspection COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tools/release_check.py" --build "${CMAKE_CURRENT_BINARY_DIR}"
        --output "${CMAKE_CURRENT_BINARY_DIR}/release" --skip-analysis)
    add_test(NAME ground_link_and_console COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/integration/test_ground.py" "$<TARGET_FILE:kestrel_flight>")
    set_tests_properties(ground_link_and_console PROPERTIES TIMEOUT 20 RUN_SERIAL TRUE)
    find_program(KESTREL_NODE NAMES node nodejs REQUIRED)
    add_test(NAME packet_inspector COMMAND "${KESTREL_NODE}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/protocol/test_inspector.cjs")
    # Unity C test framework v2.6.1, pinned independently of the flight runtime.
    FetchContent_Declare(unity GIT_REPOSITORY https://github.com/ThrowTheSwitch/Unity.git
        GIT_TAG cbcd08fa7de711053a3deec6339ee89cad5d2697 GIT_SUBMODULES "")
    FetchContent_MakeAvailable(unity)
    add_executable(test_mode tests/unit/test_mode.c)
    target_include_directories(test_mode PRIVATE fsw/include)
    target_link_libraries(test_mode PRIVATE unity)
    target_compile_options(test_mode PRIVATE -Wall -Wextra -Werror)
    add_test(NAME test_fsw_002_prerequisites COMMAND test_mode)
    set(VECTOR_HEADER "${CMAKE_CURRENT_BINARY_DIR}/packet_vectors.h")
    add_custom_command(OUTPUT "${VECTOR_HEADER}"
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/vector_header.py"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/vectors/packets.json" "${VECTOR_HEADER}"
        DEPENDS tools/vector_header.py tests/vectors/packets.json VERBATIM)
    add_executable(test_packets tests/unit/test_packet.c "${VECTOR_HEADER}")
    target_include_directories(test_packets PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
    target_link_libraries(test_packets PRIVATE kestrel_packets unity)
    target_compile_definitions(unity PUBLIC UNITY_SUPPORT_64)
    target_compile_options(test_packets PRIVATE -Wall -Wextra -Werror)
    add_test(NAME test_fsw_005_packets_c COMMAND test_packets packets)
    add_test(NAME test_fsw_006_sequence_wrap_c COMMAND test_packets sequences)
    add_test(NAME test_fsw_005_packets_python COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/protocol/test_codec.py")
    add_test(NAME test_fsw_006_sequence_wrap_python COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/protocol/test_codec.py" --sequences)
    add_test(NAME test_fsw_005_packets_cross_language COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/protocol/cross_language.py" "$<TARGET_FILE:kestrel_packet_probe>")
    set_tests_properties(test_fsw_005_packets_cross_language PROPERTIES TIMEOUT 30)
    add_test(NAME m0_queue_round_trip
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/smoke/queue_demo.py"
                "$<TARGET_FILE:kestrel_m0>")
    set_tests_properties(m0_queue_round_trip PROPERTIES TIMEOUT 15)
    add_test(NAME m0_trace_checker
        COMMAND "${Python3_EXECUTABLE}" -m unittest discover
                -s "${CMAKE_CURRENT_SOURCE_DIR}/tests/tools" -p "test_*.py")
    set_tests_properties(m0_trace_checker PROPERTIES WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
    add_test(NAME dashboard_integrity
        COMMAND "${Python3_EXECUTABLE}" -m unittest discover
                -s "${CMAKE_CURRENT_SOURCE_DIR}/tests/dashboard" -p "test_*.py")
    set_tests_properties(dashboard_integrity PROPERTIES WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" TIMEOUT 30)
    add_test(NAME m0_requirements_registry
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/trace.py" --milestone M0)
endif()
