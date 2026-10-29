# Delivery milestones

M0–M5 are complete against the clarified simulator baseline. M6 live scenarios
and M7 hardening are also delivered. The repository is public at
https://github.com/zxcv616/kestrel, with a 30-second live demo GIF and hosted
Debug/Release verification. The [README](../README.md) is the release entry point;
earlier milestone verification files retain their historical results.

| Milestone | Delivery | Acceptance |
| --- | --- | --- |
| M0 | CMake/C11, pinned FreeRTOS POSIX kernel, two queue-connected tasks, requirements/ICD/design baseline, Ubuntu CI workflow | Fresh build; ordered queue transfer and payload checks; Debug/Release gates; hosted CI green after remote setup |
| M1 | C and Python packet codecs, shared vectors, CRC, sequence counters, C unit tests | Byte-identical encodings and valid round trips; malformed packet and rollover tests; FSW-005/006 evidence |
| M2 | Link, command and telemetry tasks; boot to SAFE; NOOP, REQUEST_HK, ACK path; minimal ground CLI | Real UDP command round trip, correct counters and SAFE HK snapshot, bounded ACK latency and invalid-command rejection; FSW-001/007/008 evidence |
| M3 | Mode task, all normal commands, nominal HK/ATT, command restrictions, events, CSV logging | SAFE -> NOMINAL -> SAFE scenario; HK rate changes; ATT suppression; FSW-002/003/004/009/013/015 evidence |
| M4 | Sensor and watchdog tasks, fault injection and automatic injection expiry, hysteresis/dropout/thermal protection | Fault transitions and recovery meet measured deadlines; FSW-010/011/012/014 evidence, including internal timing observation during link/telemetry stalls |
| M5 | Complete inspection/demo evidence, production/test build separation checks, README and recorded demo | All 20 requirements verified, hosted CI green, fresh-checkout reproduction, publication when requested |
| M6 | Four live scenarios with measured steps, cancellation, exclusivity and report export | All scenario paths, cancellation/failure cleanup and HTTP guards verified on macOS/Ubuntu Debug/Release |

## M5 release status

Complete. All 20 clarified requirements pass. The public repository includes the
README, architecture, traceability table, known limitations and a real 30-second
[demo GIF](assets/kestrel-demo.gif). GitHub Actions runs build, 32 CTest entries,
seven scenarios, cppcheck and source-bound trace on every push/PR in Debug and
Release. The public-release code passed in [run 40801095231](https://github.com/zxcv616/kestrel/actions/runs/40801095231).

Gitleaks 8.30.1 scanned the release working tree and all Git history before the
visibility change; both reported no leaks. The hosted progress site was not
published or updated. Hardware remains deferred by user choice.

## Hardening follow-on (M7)

Modular tasks and UDP HAL, stack checking/marks in HK, independently visible Mode
stall detection, ATT purge, dropped-event HK and source-bound GitHub Actions.
The public repository is zxcv616/kestrel; hosted results remain separate from
local evidence. M5 publication and demo deliverables are complete.
