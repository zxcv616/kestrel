# Delivery milestones

M0 implementation is present; see [verification](m0-verification.md) for checks
actually executed and the hosted-CI limitation. M1 packet codecs are verified; see [M1 evidence](m1-verification.md). M2 ground-link evidence is recorded in [M2 verification](m2-verification.md). M3 flight modes are implemented; see [M3 evidence](m3-verification.md). M4 fault recovery is implemented; see [M4 evidence](m4-verification.md). M6 live scenarios extend the laptop simulator. M5 local release evidence is implemented; hosted CI and published-checkout reproduction remain pending. A milestone is
complete only when its acceptance evidence exists, not when code is merely added.

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

Static-memory, queue-ownership, production/test separation and warning/static-analysis
inspections are recorded. The ground station demo, playback and verification
bundle are implemented. Local verification is documented in [M5 evidence](m5-verification.md).
M5 stays active until hosted CI and reproduction from the published commit succeed.
No GitHub destination has been supplied; publication remains separately requested.

Every milestone includes its GUI capability. The user chose further laptop simulation after the MVP; hardware is deferred.

## Hardening follow-on (M7)

Modular tasks and UDP HAL, stack checking/marks in HK, independently visible Mode
stall detection, ATT purge, dropped-event HK and source-bound GitHub Actions.
The private repository is zxcv616/kestrel; its hosted result is tracked separately
from local evidence. Public visibility and a demo GIF remain separate release work.
