# M0 design decisions

Status: implementation baseline, 2026-10-27. These decisions refine the original
MVP PDF; they do not claim M1-M5 behavior is implemented. Major scope changes are
called out below so they remain reviewable.

## Scope and ownership

The MVP is C11 on the FreeRTOS POSIX port, Python ground tools, and loopback UDP.
No hardware, radio, encryption, attitude control, file transfer, or time-tagging.
M0 runs two demonstration tasks plus FreeRTOS's idle task. The final six
application tasks are link, command, mode, telemetry, sensors and watchdog.

| Owner | Mutable state | Inputs / outputs |
| --- | --- | --- |
| Link | UDP socket and fixed receive/transmit buffers | Command datagrams to command; serialized packets from telemetry |
| Command | Accepted/rejected counts; validation | Datagrams from link; requests to mode/sensors/telemetry; ACK descriptors to telemetry |
| Mode | Current mode and active fault set | Commands, sensor/fault events; decisions back to command; mode snapshots/events to telemetry |
| Telemetry | Per-APID sequences, HK configuration and latest snapshots | Snapshots, ACK/event descriptors, requests; serialized packets to link |
| Sensors | Simulated sensor state and test injections | Test requests; timestamped samples to mode/telemetry |
| Watchdog | Per-task liveness windows | Check-ins; fault messages to mode |

IPC copies fixed-size messages through bounded FreeRTOS queues. Queue handles and
immutable configuration may be passed to tasks at startup. No pointers to mutable
payloads cross task boundaries. ACKs, like all packets, are serialized by telemetry
so one owner controls each outgoing APID counter. A command ACK follows its
owner's acceptance/rejection decision; it is not an optimistic receipt ACK.

Separate control/event traffic from periodic telemetry. Periodic snapshots may
use a one-element overwrite queue; commands/events must not silently overwrite.
Queue saturation uses bounded waits, records a dropped-message/overflow count,
and requests SAFE when the mode path remains available. Deadline claims assume
no injected outage or sustained overload of the relevant path. M2 must select
queue capacities and verify this policy under bursts before claiming deadlines.
The mode task checks both faults and commands each cycle, prioritizing faults;
command floods must not starve fault handling. Link uses nonblocking I/O and
bounded work batches so receive traffic cannot starve outgoing ACKs or check-ins.

## Mode contract

Mode IDs: BOOT=0, SAFE=1, NOMINAL=2, LOW_POWER=3.

| Current state | Trigger | Next state / result |
| --- | --- | --- |
| BOOT | Initialization complete | SAFE |
| BOOT | Any ground command | Not accepted; link is not servicing commands yet |
| SAFE | SET_MODE NOMINAL; sensors fresh, battery >=20%, no active critical/stall fault | NOMINAL |
| SAFE | Any automatic sensor recovery | Remain SAFE |
| NOMINAL | Battery <20% and >=10% | LOW_POWER |
| LOW_POWER | Battery >=30%, sensors fresh, no active critical/stall fault | NOMINAL |
| Any initialized mode | Battery <10%, temperature out of bounds, sensor dropout or supported task stall | SAFE |
| Any initialized mode | SET_MODE SAFE | SAFE |
| LOW_POWER | SET_MODE NOMINAL | Reject; use automatic recovery at >=30% |
| NOMINAL | SET_MODE NOMINAL | Accept as idempotent; no transition EVENT |

Only SAFE and NOMINAL are legal SET_MODE targets. BOOT and LOW_POWER cannot be
selected by ground. Critical faults take precedence over low battery or commands.
Temperature endpoints -20 and 60 C are valid. Battery percentages 10, 20 and 30
have the exact inclusive/exclusive behavior above. Invalid commands are rejected,
not spacecraft faults. Low battery is a LOW_POWER condition, not a SAFE fault.

SAFE accepts NOOP, SET_MODE, REQUEST_HK and RESET_COUNTERS. Other initialized modes
accept all commands subject to build, argument and transition checks. HK is every
10 s in SAFE, every 5 s in LOW_POWER, and at the configured period in NOMINAL
(default 1000 ms). SET_HK_RATE changes the stored NOMINAL period only, even when
issued in LOW_POWER. Mode entry resets periodic deadlines; immediate REQUEST_HK
does not shift them. ATT is 1 Hz only in NOMINAL. BOOT sends no telemetry.

Faults are edge-triggered: record an EVENT once when a fault becomes active, and
again only if it clears then recurs. A fault that changes mode produces both a
fault EVENT and a transition EVENT. Leaving SAFE never happens automatically.
`last_fault` remains the most recent fault code after recovery and counter reset.

## Watchdog and recoverable injections

**Deliberate narrowing of FSW-012:** M4 guarantees SAFE for stalls of link,
command, telemetry and sensors while mode, watchdog and scheduler stay healthy.
A mode task stalled forever cannot process a SAFE request. A watchdog stalled
forever cannot detect itself. Recovering those failures needs an independent
supervisor/reset path, deferred to the hardware phase. Do not advertise protection
against every possible task/scheduler failure.

Each application task checks in at least every 250 ms, including idle event-driven
tasks. Use bounded queue waits; do not confuse lack of incoming work with a stall.
The watchdog first evaluates at 1 s (startup grace), then every 1 s. At each
evaluation a check-in older than 500 ms counts as a miss; a fresh check-in resets
the consecutive-miss counter. Three consecutive misses trigger a fault. This
leaves a nominal budget of at most 3.5 s from the last check-in to detection and
250 ms for mode processing, within the 4 s simulator requirement. Verify the
full deadline against host time in M4. A returning task clears its active stall
condition but leaves the spacecraft in SAFE. Reserve enough check-in capacity
that normal producers cannot lose a window because another producer filled it.

M4 test-only injections last 5 s of monotonic elapsed time, then restore normal
behavior automatically. Stall injection suspends work/check-ins cooperatively
without starving the scheduler; it does not simulate arbitrary deadlock or
memory corruption. It targets only link, command, telemetry or sensors. On
recovery, fresh sensor data/check-ins clear active faults; a ground command can
then request NOMINAL. This avoids adding a seventh command to clear faults or
weakening SAFE's command allowlist.

Battery injections hold at 15% or 5%, thermal injections at 61 C or -21 C, and
dropout marks sensor samples unavailable. Normal baseline: 80%, 3800 mV, 20 C,
zero angular rates. Sensors update every 100 ms. A missing/invalid sample lasting
500 ms is a dropout fault; SAFE must follow within 1 s of loss. Stalling sensors
can therefore reach SAFE before the watchdog's own stall threshold. While the
link or telemetry task is stalled, EVENTS can be retained only within bounded
queue capacity and cannot be delivered until the path recovers. Verify SAFE
independently of packet receipt in those scenarios; delayed packets alone cannot
prove the transition deadline.

## Memory and host constraints

**FSW-016 clarification:** all Kestrel task, queue and packet storage is static;
Kestrel application code does not allocate dynamically. The POSIX port uses
pthread/malloc internally, including per-thread initialization, so this is not a
claim of a process with zero host allocations. FreeRTOS heap support is disabled.
FSW-017 adopts the stricter queues-only architecture, removing the PDF's optional
mutex-protected shared application state.

M0 pins FreeRTOS V11.3.2 at commit
`8a59a4b19bf72977819feddef87d41163ced7004`. The upstream POSIX port owns scheduler
threads/signals. Only one application task uses stdio during the demo. The demo
is finite and ends the scheduler; the eventual flight binary will run continuously.

Ubuntu 24.04 CI is the reference build environment, macOS is the local development
platform. Timing is a measured simulator property, not a hardware guarantee.
FreeRTOS explains the simulator limitations in its
[official documentation](https://freertos.org/Documentation/02-Kernel/03-Supported-devices/04-Demos/03-Emulation-and-simulation/Linux/FreeRTOS-simulator-for-Linux).

## Known follow-on decisions

M2 sets queue capacities and measures ACK budget under bounded traffic. M3 defines
the request/response messages that serialize command decisions with mode updates.
M4 adds an independent test observation point for internal SAFE timestamps when
the telemetry path is deliberately stalled. Hardware reset/watchdog supervision
and transport-independent sensor drivers belong to phase 2.

## M2 implementation decisions

M2 runs Link (priority 3), Command (2), and Telemetry (1), plus kernel idle.
Context contains immutable startup configuration and queue handles only. The
mode is fixed SAFE after initialization; no mutable mode state is shared.
Mode, Sensors and Watchdog arrive in M3/M4. HK uses unavailable-sensor sentinels.
There is one initial SAFE HK, then one every 10 seconds. REQUEST_HK does not
reset that deadline. Clock fields use host CLOCK_MONOTONIC elapsed from main.

Only NOOP and REQUEST_HK are executable in M2. Other valid normal commands return
MODE_DENIED during this incremental milestone. Production INJECT_FAULT returns
UNKNOWN_FUNCTION after wire validation. The final SAFE allowlist and reset
semantics remain M3 work; no FSW-009/013 claim is made in M2.

Incoming datagrams, command decisions and control output each use a 32-entry
static copy queue. Periodic telemetry has a separate single-entry queue. Link
services up to eight outputs and eight inputs per 1 ms cycle, output first.
When the ingress queue is full, Link stops reading until capacity returns. Once
received, a datagram is retained through bounded 10 ms enqueue retries; control
traffic is never overwritten. Telemetry counts queue wait timeouts, Command
reports its wait timeouts through decisions, and HK last_fault becomes
QUEUE_OVERFLOW (7) when a retry or skipped periodic enqueue is recorded. SAFE
is already enforced; dynamic SAFE requests and fault events await Mode in M3/M4.
These are congestion observations, not counts of kernel-dropped UDP datagrams.

The verified traffic envelope is 100 sequential commands followed by an
instantaneous burst of 64 commands on otherwise idle loopback. No 100 ms or
lossless-delivery guarantee is made for sustained overload, host suspension or
an unavailable UDP destination. Kernel receive buffers can drop unserviced
traffic under overload. Temporary send backpressure retains one outgoing packet;
permanent socket errors fail the process visibly rather than silently claiming
successful service. No automatic ground retransmission occurs.

Flight defaults to 127.0.0.1:5000 and sends only to 127.0.0.1:5001. Startup-only
port flags (1024..65535, distinct) support isolated tests. Ports cannot be changed
through the browser. There is no socket address reuse; an occupied port fails.
The ground receiver validates source address and CRC, retains 100 command
records, correlates ACKs, marks timeouts at one second and stale HK after 15
seconds. A late ACK is labeled late. ACK freshness never refreshes HK freshness.

## M3 implementation decisions

Four static application tasks now run: Link and Mode at priority 3, Command at 2,
and Telemetry at 1. Command sends one validated request through a single-entry
Mode queue and waits for a copied reply before updating counts or issuing its ACK
descriptor. Mode owns current mode and the committed nominal HK period; Telemetry
uses copied decisions to schedule output. No mutable task state is shared.
A BOOT → SAFE event follows initial HK. Actual transitions emit one EVENT and an
immediate HK. Idempotent SET_MODE does not emit a transition event or reset deadlines.
Mode entry and accepted rate changes reset the relevant periodic deadline;
REQUEST_HK does not. ATT contains unavailable sentinels until M4. Periodic output
has two slots so simultaneous HK and ATT deadlines do not compete for one slot.

M3 explicitly uses a healthy prerequisite fixture (fresh=true, battery=80%,
critical=false) for Mode authorization. This is a milestone dependency, not sensor
telemetry: HK/ATT retain unavailable sentinels. The authorization predicate is
unit-tested with stale, low-battery, critical, BOOT and LOW_POWER cases. M4 must
replace the fixture with queue-delivered sensor/fault state and verify those
conditions end to end. No fault detection/recovery claim is made in M3.

Every valid telemetry datagram received from the configured flight endpoint is
flushed to a uniquely named CSV under output/telemetry, with receipt time, type,
APID, sequence, flight timestamp, decoded fields and original hex. No truncated
in-memory history is used as the CSV source. Logging errors mark the receiver
failed. The console can download the active or most recently stopped session;
older sessions remain on disk. UI timing plots use packet timestamps and retain
240 samples total; the displayed series is bounded to 60 samples per type.

## M4 implementation decisions

Six static application tasks now run: Watchdog priority 4; Link and Mode 3;
Command 2; Telemetry and Sensors 1. Sensors publish a copied sample every 100 ms.
Each task has a separate one-entry overwrite check-in queue; Watchdog drains
these every 10 ms and evaluates one-second windows. More than 500 ms without a
check-in misses a window; three consecutive misses assert that task's stall.
New check-ins clear the stall. Mode evaluates sensor and watchdog faults before
command requests, holds the current mode and sticky last_fault, and publishes
copied state for Telemetry. No healthy fixture remains.

Sensor faults are edge-triggered, with LOW_BATTERY hysteresis and the exact
battery/temperature boundaries in the contract. SAFE never automatically exits.
LOW_POWER returns to NOMINAL only on a fresh sample at least 30% with no critical
fault. Voltage is a fixed simulated 3800 mV baseline, independent of injected
battery percentage. Nominal angular rates are a simulated stationary zero.
Missing/invalid/stale samples produce sentinels in HK/ATT, not invented readings.

Mode never blocks on Telemetry: a 64-entry event queue records fault/clear/mode
edges, and an overwrite state queue retains the latest state. A full event queue
increments droppedEvents and requests SAFE through the queue-overflow condition.
Other producers signal congestion to Mode through separate overwrite channels.
Control output remains bounded and retained through short enqueue retries with
check-ins. Protection does not guarantee event delivery during sustained overload.
Events retain their occurrence timestamp even if transport resumes later.

Both kestrel_flight (production) and kestrel_flight_test (KESTREL_TEST=1) are built.
Only the latter compiles injection dispatch and --observe. An accepted injection
is armed for 100 ms so its ACK can traverse the operational path, then remains
active for exactly 5000 ms of monotonic time. One injection owns the slot until
expiry; another is BUSY unless SAFE permission rejects it first. Stalls are
cooperative: Link, Command, Telemetry or Sensors stop work and check-ins while
allowing the scheduler and protection tasks to run. Samples and check-ins restore
automatically. Ground commands are never retried automatically.

The test-only Mode observer emits fixed-size JSON lines through nonblocking
stdout, separate from Link and Telemetry. It includes committed mode/timestamp,
active fault masks, task check-in ages and missed windows, sensor state, injection
start/end and dropped event count. A blocked observer cannot block protection;
observation lines can be lost if its pipe fills, and the UI marks an old observer
stale. It is an internal test instrument, not a fifth flight packet or a hardware
independent watchdog. The local bridge saves observations beside the session CSV,
keeps 600 snapshots and 100 change rows in memory, and labels this source in the UI.

## Simulator hardening revision

Startup/queue creation remains in fsw/src/flight.c; each task is in tasks/.
Shared message definitions are in kestrel_runtime.h, and runtime.c provides clock,
check-in and injection helpers. Socket APIs exist only in hal/udp_link.c behind
kestrel_link.h. A UART adapter must implement the same nonblocking packet contract
and its framing; replacing the transport does not require editing task sources.
HAL private socket state is owned exclusively by Link.

Stack checking mode 2 is enabled with an aborting overflow hook. Each task measures
its own FreeRTOS stack high-water mark; copied check-ins carry it to Watchdog and
HK. POSIX pthread stacks remain outside that measurement. Mode already checked in;
a dedicated test now stalls it and verifies independent watchdog detection in HK.
The watchdog cannot reset itself or a permanently stalled Mode. Phase 2 adds an
independent hardware watchdog timer whose expiry resets the MCU.

Mode sends a copied mode/epoch gate to Link. Link purges obsolete ATT while retaining
HK, and rechecks its retry slot. A scheduler suspension spans only the final gate
check and nonblocking HAL submission, ordering submission with Mode commits;
no queue wait or blocking I/O is allowed there. A transport must preserve this
nonblocking contract. Epoch comparison handles SAFE followed by NOMINAL before
Link resumes. A deterministic fake-HAL test covers actual send backpressure;
a separate real UDP test covers Link stall and SAFE recovery.

Events use 64 slots; failed enqueues increment a Mode-owned counter copied to HK.
A test-only startup burst fills the queue deterministically and verifies that the
counter reaches received HK. This fixture is absent from production parsing.
CI fingerprints source before tests, checks it again afterward and binds JUnit
hashes to it. The trace gate rejects source/report changes when --provenance is
supplied; hosted CI always supplies it. Historical reports remain historical.

## First housekeeping readiness

Telemetry defers its first HK until the Mode-owned sensor snapshot is valid and
less than 500 ms old. This uses the existing copied state queue and adds only a
local boolean; no new synchronization or allocation is introduced. Command
processing and check-ins continue while waiting. Boot EVENT normally follows HK;
after 500 ms, events are drained even without valid sensors, so startup sensor
failure does not hide fault reporting. Requested/periodic HK remains gated until
the first valid sample; subsequent sensor loss uses the existing sentinels.
The console never issues an automatic startup REQUEST_HK. The normal first HK
remains within the tested two-second boot limit, with zero command counters.
