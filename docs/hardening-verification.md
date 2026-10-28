# Simulator hardening verification

This revision splits flight startup/runtime, six tasks, packet codecs and a
nonblocking UDP adapter. HK revision 2 adds dropped events, watchdog stall flags
and six FreeRTOS stack-buffer high-water marks. Stack checking mode 2 and the
fatal hook are enabled. The host stack measurement limitation is documented in
the README, ICD and live interface.

## Targeted evidence

- test_fsw_012_mode_health: real five-second Mode stall; received HK independently
  reports bit 3 while Mode observation stops. All six stack marks become available.
  After Mode resumes, request fresh HK to verify cleared health.
- test_fsw_014_overflow: deterministic test-only event burst exceeds the 64-slot
  queue; a requested HK carries the nonzero dropped-event count in SAFE.
- test_fsw_015_flush: real Link outage creates a telemetry backlog, Mode enters
  SAFE, and no retained ATT is delivered when the Link resumes.
- test_fsw_015_link_backpressure: real scheduler plus fake nonblocking HAL forces
  a retained ATT; SAFE discards it and preserves HK. A rapid NOMINAL return cannot
  revive an old epoch; a newly generated ATT can pass.
- Source/report provenance unit tests reject edited source, substituted reports
  and missing reports. CI fingerprints source before tests, checks it after them,
  binds report hashes and passes the manifest to the trace gate.

The full local Debug suite passes 32/32 CTest entries. The seven live-scenario
checks also pass, cppcheck passes, and the source-bound trace gate verifies all 20
requirements. GitHub Ubuntu Debug and Release also passed all 32 tests, 7 scenarios, cppcheck
and the source-bound trace gate in [the first green hosted run](https://github.com/zxcv616/kestrel/actions/runs/40754440100),
commit 9166539. The Actions page records subsequent commits separately.
The current source-bound inspection records replace the earlier single-file
inspection baseline; older reports remain historical.

## UI verification

The new received-HK health disclosure was exercised against a real local test
flight: Request HK populated six marks and zero dropped events. Desktop and a
390-pixel embedded viewport were reviewed. Missing fields render blank. Mode
stall injection is labeled detection-only. The preview flight/server were stopped;
the user's console was not taken over. No hosted dashboard was updated.

## Limits

POSIX stack marks do not measure pthread execution stacks. A Mode stall can be
detected but a permanently stalled Mode cannot commit SAFE; phase 2 supplies an
independent hardware watchdog reset. Dropped-event counts cover failed event
queue enqueues, not UDP network loss. Already submitted datagrams cannot be recalled.
