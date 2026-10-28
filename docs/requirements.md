# Kestrel requirements register

This is the implementation baseline derived from the original MVP PDF. IDs are
preserved. Clarifications and deliberate scope changes are recorded in
[design.md](design.md); wire details live in [icd.md](icd.md).

`Due` is the first milestone that requires passing evidence. A verification name
is a planned check, **not proof that the requirement passes**. M1 reports provide codec evidence for FSW-005/006; transport integration will
exercise these again in M2. The queue demo is infrastructure evidence only.

| ID | Requirement | Method | Due | Verification |
| --- | --- | --- | --- | --- |
| FSW-001 | Finish initialization and enter SAFE within 2 s of process start. | Test | M2 | test_fsw_001_boot_safe |
| FSW-002 | Leave SAFE only on a valid SET_MODE NOMINAL command with healthy prerequisites. | Test | M3 | test_fsw_002_safe_exit, test_fsw_002_prerequisites |
| FSW-003 | Send periodic HK at the default 1 Hz within 50 ms in NOMINAL, under documented host conditions. | Test | M3 | test_fsw_003_hk_timing |
| FSW-004 | Accept configured NOMINAL HK periods from 250 through 10000 ms inclusive and reject others. | Test | M3 | test_fsw_004_hk_rate |
| FSW-005 | Every emitted packet has a valid CCSDS primary header, Kestrel secondary header and CRC. | Test | M1 | test_fsw_005_packets_c, test_fsw_005_packets_python, test_fsw_005_packets_cross_language |
| FSW-006 | Each sender's per-APID sequence counter advances once per emitted packet and wraps from 16383 to 0. | Test | M1 | test_fsw_006_sequence_wrap_c, test_fsw_006_sequence_wrap_python |
| FSW-007 | Reject commands with bad CRC, unknown APID or function code, invalid header or wrong length. | Test | M2 | test_fsw_007_invalid_commands |
| FSW-008 | While the link and command path are operational, emit one ACK within 100 ms of each received command datagram; unidentifiable packets use the sequence sentinel in the ICD. | Test | M2 | test_fsw_008_ack_deadline |
| FSW-009 | HK reports accepted and rejected command counts with the reset semantics in the ICD. | Test | M3 | test_fsw_009_command_counts |
| FSW-010 | From NOMINAL, enter LOW_POWER below 20% battery; from LOW_POWER return to NOMINAL at 30% or above if no critical fault is active. | Test | M4 | test_fsw_010_battery_hysteresis |
| FSW-011 | Enter SAFE within 1 s of simulated battery below 10%, temperature outside -20 through 60 C, or sensor dropout. | Test | M4 | test_fsw_011_critical_faults |
| FSW-012 | Enter SAFE within 4 s of a link, command, telemetry or sensor task ceasing check-ins, after 3 missed 1 s windows, while mode, watchdog and scheduler remain operational. | Test | M4 | test_fsw_012_watchdog_safe, test_fsw_012_mode_health |
| FSW-013 | In SAFE accept only NOOP, SET_MODE, REQUEST_HK and RESET_COUNTERS; all commands still undergo validation. | Test | M3 | test_fsw_013_safe_commands |
| FSW-014 | Enqueue an EVENT on each actual mode transition and each newly detected fault; delivery requires an operational link/telemetry path and available bounded queue capacity. Count undelivered event enqueues in HK. | Test | M4 | test_fsw_014_fault_events, test_fsw_014_overflow |
| FSW-015 | Emit ATT only in NOMINAL, at 1 Hz. | Test | M3 | test_fsw_015_att_modes, test_fsw_015_flush, test_fsw_015_link_backpressure |
| FSW-016 | Kestrel flight application code performs no dynamic allocation; tasks, queues and buffers use static storage. Host runtime allocations are outside this application guarantee. | Inspection | M5 | docs/verification/FSW-016.json |
| FSW-017 | Flight tasks exchange mutable application data only by copying messages through FreeRTOS queues; no mutex-protected shared application state. | Inspection | M5 | docs/verification/FSW-017.json |
| FSW-018 | Fault injection is compiled only into KESTREL_TEST builds and is absent from production command dispatch. | Inspection | M5 | docs/verification/FSW-018.json |
| FSW-019 | Flight code builds with -Wall -Wextra -Werror and cppcheck reports no enabled findings. | Inspection | M5 | docs/verification/FSW-019.json |
| FSW-020 | Ground station decodes all four telemetry types, sends all six commands in a test build, and logs every received telemetry packet to CSV. | Demo | M5 | docs/verification/FSW-020.json |

## Verification policy

Run `python3 tools/trace.py --milestone M0` to validate the registry alone.
Later, pass `--junit build/results.xml` (repeatable for C/Python suites) and advance
the milestone gate. `--milestone M5` requires all 20 requirements. A named test
must actually appear in supplied JUnit results without failure, error or skip.
All required names must pass. A missing result remains pending, never passed.

Inspection/demo records are JSON objects containing `id`, `result: "pass"`,
`reviewer`, `scope` (reviewed commit/build), and a nonempty `evidence` list of
repository-relative files. Each evidence file must exist and be nonempty. These
records document human/automated review; their existence is not a substitute for
performing it. Refresh them when their implementation changes. No such records
are pre-filled in M0. CI must produce test reports freshly for each run.

Timing is measured with a monotonic host clock, with the runtime environment and
load recorded. Timing tests must not silently relax limits or rerun until green.
The POSIX simulator is not evidence of a hardware hard-real-time guarantee.

Inspection records must include nonempty `sourceHashes`: SHA256 digests of reviewed
source and evidence files. A mismatch makes the inspection pending. Re-review
changed implementation before updating a record.
