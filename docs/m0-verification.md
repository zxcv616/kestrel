# M0 verification record

Date: 2026-10-27 (America/Los_Angeles).

## What was run

| Environment | Configuration | Result |
| --- | --- | --- |
| macOS arm64, Apple Clang 16.0.0, CMake 4.1.0, Python 3.13.5 | Debug | Build passed with warnings as errors; 3/3 CTest suites passed |
| Same local environment | Release | Build passed with warnings as errors; 3/3 CTest suites passed |
| Ubuntu 24.04 arm64 container, GCC 13.3.0, CMake 3.28.3, Python 3.12.3, cppcheck 2.13.0 | Debug | Full tools/ci.sh passed, including 3/3 CTest suites and cppcheck with no findings |
| Same Ubuntu environment, independent build directory | Release | Full tools/ci.sh passed, including 3/3 CTest suites and cppcheck with no findings |

The Ubuntu container used the official `ubuntu:24.04` image, resolved during this
run to digest `sha256:24737cef17f4e22b1977df7d9a05e77c4e28b7da5b8911f8d8ccda136bf3573c`.
Both Ubuntu builds fetched the pinned FreeRTOS commit into fresh build directories.
The GitHub workflow targets Ubuntu 24.04 hosted runners (x86_64); the local arm64
container run is evidence for Linux portability, not a hosted x86_64 CI result.

CTest suites:

1. `m0_queue_round_trip`: launches the actual FreeRTOS executable with a deadline;
   checks exit status, 20 ordered messages, payload checksum 2870, and advancing
   scheduler ticks. The C consumer also validates each received sequence/value.
2. `m0_trace_checker`: 10 unit tests cover registry completeness, future evidence,
   release-gate failure without evidence, passed/failed/skipped/error JUnit cases,
   failed parameter variants, multiple required checks, inspection artifacts,
   and malformed reports.
3. `m0_requirements_registry`: validates all 20 IDs and their verification plans.
   Reports **0/20 flight requirements verified, M0 gate PASS**, as intended.

The Release configuration preserves configASSERT, including assertions around
queue and task creation. No FreeRTOS heap implementation is linked. A Linux-only
POSIX.1-2008 feature macro exposes the pthread/clock declarations needed when
compiling the upstream port under strict C11; macOS retains its native declarations.

## Reproducibility and limits

Run the README commands for macOS, or `tools/ci.sh build Debug` and
`tools/ci.sh build-release Release` on Ubuntu with the listed prerequisites.
Local raw reports live in `build/results.xml`, `build-release/results.xml`, and
`build/verification/ubuntu-{debug,release}.xml`; the container log is
`build/verification/ubuntu-ci.log`. Build outputs are intentionally ignored by Git.

A Git repository was initialized on branch `main`. No remote is configured and
no GitHub Actions run has occurred. The workflow and its shared CI script are
ready; hosted CI green remains the outstanding M0 acceptance item until a remote
is selected and the work is pushed. There is no claim of flight behavior, timing
compliance, hardware validation, or completed FSW-001 through FSW-020 in M0.
