# M2 ground-link verification

Executed October 27, 2026 (America/Los_Angeles). M2 is complete with a local
three-task FreeRTOS flight process, Python ground receiver/CLI, and live local
console controls. FSW-001, 005, 006, 007 and 008 pass: **5/20 requirements**.

## Executed gates

| Environment | Suites | Boot to first SAFE HK | Largest measured ACK round trip | SAFE periodic HK timestamp |
| --- | --- | --- | --- | --- |
| macOS, AppleClang 16, Debug | 15/15 | 165.029 ms | 13.549 ms | 10000 ms |
| macOS, AppleClang 16, Release | 15/15 | 119.209 ms | 10.905 ms | 10000 ms |
| Ubuntu 24.04 container, GCC 13.3, Debug | 15/15 | 2.346 ms | 18.026 ms | 10000 ms |
| Ubuntu 24.04 container, GCC 13.3, Release | 15/15 | 1.830 ms | 18.041 ms | 10000 ms |

These are measured POSIX simulator results, not embedded hard-real-time bounds.
Boot measurement includes host process launch and first telemetry receipt. ACK
round trip includes ground send/receive overhead, so it is stricter than measuring
only the flight's receive-to-send interval. The reported maximum covers 100
sequential NOOPs and every ACK in a 64-command instantaneous burst. Two additional
commands exercise destination routing and REQUEST_HK (166 accepted commands).
The 100 ms assertion applies to each measured command, including those two.

Ubuntu Debug and Release also passed cppcheck and the M2 trace gate through
`tools/ci.sh`. An initial cppcheck redundant-assignment finding was corrected;
all four final configurations were rebuilt and retested afterward. macOS does
not have cppcheck installed; static-analysis evidence is from Ubuntu.

Reports: `build/results.xml`, `build-release/results.xml`,
`build/verification/ubuntu-m2-debug.xml`, and
`build/verification/ubuntu-m2-release.xml`. CTest output retains the measured
values above. Build artifacts are ignored; README commands reproduce the tests.

## Integration evidence

- A real FreeRTOS child and loopback sockets, with isolated test ports. Initial
  HK proves SAFE within two seconds; a second process cannot reuse its port.
- 38 malformed/unsupported datagrams: the 32 frozen invalid fixtures, valid
  telemetry sent to the command port, four unavailable commands, and an
  oversized datagram over 8 KiB. Each yields exactly one expected rejection ACK.
  Short datagrams use sequence sentinel 65535; other invalid datagrams echo
  the low 14 input sequence bits. No rejected command changes SAFE or accepted
  counts; the subsequent REQUEST_HK includes its own accepted count.
- Every received flight packet is decoded, re-encoded byte-for-byte, and checked
  for independent per-APID sequence progression. ACK envelope sequence and
  echoed command sequence are checked separately.
- Replies go to the configured ground port even when a command originates from
  a different source port. No arbitrary-source ACK reflection.
- Initial SAFE HK, immediate requested HK, and periodic HK at ten seconds. A
  request around 200 ms does not move the periodic deadline. Sensor fields use
  the specified unavailable sentinels; no dummy sensor values are substituted.
- Ground timeout, late ACK correlation, unexpected-source rejection, stale state,
  no automatic retry, and unsupported ground command rejection.
- Actual HTTP start/NOOP/REQUEST_HK/stop/restart round trip. Every flight action
  rejects a foreign Origin or missing token. Duplicate start fails; stop and
  server shutdown reap only their owned child and release the receiver port.
- Existing codecs, reference vectors, browser packet inspector, scheduler demo,
  trace checker and dashboard regression suites remain passing.

## GUI review and publication

The local Runtime view was exercised in the browser: start into actual SAFE,
NOOP ACK, REQUEST_HK ACK and counts, stop with cleared live fields, then restart
with reset process state. Desktop 1440×1000 and narrow 390×844 layouts were
inspected. Sensor/ATT fields stay blank, future mode controls remain disabled,
and received HK has its own freshness indicator independent of ACK traffic.

The private Site is updated at the existing URL and audience. Its Runtime view
shows a clearly labeled recorded local session with disabled flight controls.
Packet inspection remains interactive in the browser. `tools/record_m2.py`
captures the real session; no live data is fabricated in the hosted snapshot.

## Remaining boundaries

The tested command envelope is 100 sequential commands plus a 64-command burst
on loopback. Sustained overload, OS suspension and unavailable destinations are
outside the deadline guarantee. Bounded queues retain serviced control traffic;
kernel UDP drops under overload cannot be inferred from application counters.
See design.md for capacities and backpressure policy.

M2 stays SAFE and supports only NOOP/REQUEST_HK execution. Mode transitions,
RESET_COUNTERS, final command permissions, ATT and event/CSV logging belong to
M3; sensors/watchdog belong to M4. No FSW-009/013 or hardware timing claim is made.

Hosted GitHub CI still awaits a repository destination. Local Ubuntu container
checks do not satisfy M0's pending hosted-CI gate.
