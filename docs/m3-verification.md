# M3 flight-mode verification

Executed October 27, 2026 (America/Los_Angeles). The local simulator implements
four static FreeRTOS tasks, all five production commands, mode-specific HK/ATT,
mode-change events, complete ground CSV logging and updated browser controls.
The M3 gate covers 11/20 requirements. Sensor and fault integration is M4.

## Scope of mode authorization

M3 Mode uses a clearly labeled healthy fixture, not simulated sensor measurements.
The actual authorization predicate is tested against stale data, battery below
20%, active critical faults, BOOT and LOW_POWER. Integration tests exercise ground
command authorization and transitions against the real FreeRTOS process. M4 must
replace the fixture with sensor/fault messages and repeat prerequisite tests end
to end. HK/ATT sensor fields still contain unavailable sentinels.

## Acceptance checks

- Boot SAFE within two seconds; independent packet sequences and valid CRCs.
- SAFE persists without SET_MODE. SAFE → NOMINAL → SAFE emits exactly one event
  per actual transition. Idempotent NOMINAL requests produce no extra event.
- NOMINAL HK defaults to one second, with every measured host interval within
  50 ms. Immediate mode-entry HK is excluded from the periodic timing sample.
- HK periods 250, 1000 and 10000 ms are accepted and observed. Values 0, 249,
  10001 and 65535 are rejected. SAFE rate changes are denied; stored nominal
  configuration survives SAFE and re-entry.
- Reset sets accepted=1 and rejected=0. The subsequent REQUEST_HK reports
  accepted=2; sequences, clock and mode remain intact.
- SAFE allowlist and validation precedence; production injection remains rejected.
- ATT is absent in SAFE, emitted at one second in NOMINAL, and suppressed again
  on SAFE entry. All three rates remain unavailable, never fabricated zeros.
- Prior malformed-input, ACK burst/deadline, queue, codec and browser checks pass.
- HTTP mode/reset/rate actions retain Host/Origin/token checks. Real HTTP tests
  verify transitions, CSV contents, stop/restart and owned-child cleanup.

## Browser review

Tested local start, NOMINAL entry, HK period 250 ms, SAFE return, counter reset
and REQUEST_HK. Observed approximately 250 ms HK and 1000 ms ATT intervals;
mode-entry and requested HK are explicitly distinguished from periodic timing.
Desktop 1440×1000 and mobile 390×844 layouts reviewed. Downloaded a 247-row CSV
containing HK, ATT, EVENT and ACK, and decoded every saved hex packet to verify
its fields against the CSV. This exceeds the 100-row packet-display history.
Mode events have a separate bounded history. Sensor readings remain unavailable.
At high rates, animation samples recent packets and prioritizes control traffic;
CSV logging retains all accepted telemetry regardless of animation sampling.

## Evidence and limitations

Fresh JUnit reports live in build/results.xml and build-release/results.xml.
All four configurations passed 22/22 suites:

| Environment | Boot SAFE | Maximum tested ACK round trip | Largest nominal HK interval error |
| --- | --- | --- | --- |
| macOS AppleClang 16 Debug | 173.095 ms | 11.329 ms | 0.535 ms |
| macOS AppleClang 16 Release | 126.027 ms | 11.107 ms | 0.715 ms |
| Ubuntu 24.04 / GCC 13.3 Debug | 2.361 ms | 18.287 ms | 2.256 ms |
| Ubuntu 24.04 / GCC 13.3 Release | 2.601 ms | 18.187 ms | 1.394 ms |

Ubuntu reports: build/verification/ubuntu-m3-debug.xml and
build/verification/ubuntu-m3-release.xml. Both passed cppcheck and the M3 trace
gate. The CI source filter was corrected to match relative as well as absolute
compilation-database paths. An intermediate Release dashboard check ran before
the newly referenced verification document existed; after adding the document,
the complete Release suite passed. No timing limits were relaxed or retried to
obtain a pass.
Checks are local and container-based; no hosted GitHub CI result is claimed.
Timing describes the POSIX simulator on an otherwise idle loopback link, not a
hardware real-time guarantee. The hosted progress site is unchanged.
