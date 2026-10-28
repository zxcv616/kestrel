# M4 sensor and fault-recovery verification

Executed October 27, 2026 (America/Los_Angeles). Six static FreeRTOS application
tasks now implement sensor sampling, watchdog check-ins, fault-driven modes and
recovery. Both production and KESTREL_TEST executables are built. M4 requires
15/20 requirements; the remaining five inspection/demo requirements are M5.

## Acceptance evidence

- Real baseline samples (80%, 3800 mV, 20 °C, stationary angular rates) replace
  the healthy prerequisite fixture. Sensor messages update every 100 ms.
- The real Mode policy has unit checks at 9/10%, 19/20%, 29/30%, and thermal
  endpoints -20/60 °C and adjacent invalid values. Stale/critical conditions
  prevent SAFE recovery. LOW_POWER cannot be selected as a ground target.
- All nine fixed-duration test injections are exercised against the real
  FreeRTOS process and loopback UDP. Injection is denied in SAFE; an overlapping
  injection is BUSY while outside SAFE. Each activation spans exactly 5000 ms
  after a 100 ms arming interval, and samples/check-ins recover automatically.
- Battery 15% enters LOW_POWER, suppresses ATT, and returns to NOMINAL on healthy
  battery recovery. Critical battery, both thermal faults, and sensor dropout
  enter SAFE within one second. SAFE persists after fault clearance until an
  accepted ground command. Attempts to recover during active faults are denied.
- Link, Command, Telemetry and Sensors are cooperatively stalled. Watchdog
  observations show three missed windows, a TASK_STALL edge, then a clear edge
  when check-ins return. SAFE commits within four seconds. Sensor stall also
  triggers dropout protection earlier. Mode/Watchdog/scheduler stay operational.
- A separate nonblocking Mode observation pipe proves committed mode/timestamps
  during Link and Telemetry outages. Delayed flight EVENT timestamps match the
  internal mode-transition timestamp; packet receipt is not used as proof of
  the internal transition deadline. No flight events were dropped in these runs.
- Every tested fault has one detected and one cleared event; repeated thermal
  injection after clearance produces a second pair. Counter reset preserves the
  sticky last_fault, while a fresh requested HK verifies reset command counts.
- Existing codecs, sequence tests, malformed-input rejection, ACK deadline,
  mode/rate controls, timing, dashboard integrity and ground security tests remain.
  HTTP tests include Start test flight and actual injection plus observation.

## Issues found and corrected

Initial Linux burst runs exceeded the unchanged 100 ms ACK limit because Mode
and Telemetry slept after work in addition to waiting on their input queues.
They now block on input queues for idle yielding and wake immediately for queued
work. A recovery-test race accepted an old HK with coincidentally matching counts;
it now requires a new HK sequence before checking post-reset telemetry. No timing
limits or traffic envelope were relaxed to obtain a pass.

## UI review

Used an isolated local preview on TCP 8766 and UDP 5500/5501, leaving the user's
console session alone. Browser tests covered Start test flight, NOMINAL entry,
15% battery automatic recovery, 5% battery SAFE persistence, and a Telemetry
stall. The latter recorded SAFE 3374 ms after injection began through the test
observation channel. Desktop 1440×1000 and mobile 390×844 views were reviewed;
mobile page width remains 390 px, with wide history tables scrolling internally.
No browser errors were reported. Sensor gaps remain unavailable rather than
being filled with synthetic readings; the plots use received HK. The watchdog
and recovery timeline explicitly identify their separate internal test source.

## Limits

These are measured POSIX simulator properties, not hardware hard-real-time
bounds. Arbitrarily stalled Mode, Watchdog or scheduler are outside the watchdog
protection claim. Injection models cooperative outages, not memory corruption or
arbitrary deadlock. Bounded event queues and a nonblocking observer can lose
records during sustained overload; event-loss count and observation freshness
are exposed. The hosted progress site is unchanged and no hosted GitHub CI result
is claimed. Complete M5 inspection/demo records are not pre-filled.

## Final reports

All four final configurations passed 26/26 suites and the M4 trace gate:

| Environment | Maximum tested ACK round trip | Maximum critical-sensor SAFE delay | Maximum stall-scenario SAFE delay |
| --- | --- | --- | --- |
| macOS AppleClang 16 Debug | 11.230 ms | 390 ms | 2792 ms |
| macOS AppleClang 16 Release | 11.052 ms | 493 ms | 2801 ms |
| Ubuntu 24.04 / GCC 13.3 Debug | 18.007 ms | 402 ms | 2796 ms |
| Ubuntu 24.04 / GCC 13.3 Release | 18.066 ms | 401 ms | 2798 ms |

ACK samples cover 100 sequential commands plus a 64-command burst. Fault delays
start at injection activation, after its explicit arming delay. A Link stall can
reach SAFE through queue congestion before the watchdog triggers; a Sensors stall
can reach SAFE through dropout first. Every stall case separately verifies three
missed watchdog windows and detection within four seconds. This table reports
committed SAFE time, not delayed telemetry receipt.

Reports: build/results.xml, build-release/results.xml,
build/verification/ubuntu-m4-debug.xml and
build/verification/ubuntu-m4-release.xml. Linux Debug and Release passed cppcheck
for both production and KESTREL_TEST translation units with no enabled findings.
The five M5 inspection/demo requirements remain pending: 15/20 are verified.
