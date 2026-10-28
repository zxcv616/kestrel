# Kestrel

Flight software for a simulated CubeSat: C11 on FreeRTOS, binary commands and
telemetry, fault-driven operating modes, and requirements tied to verification.
The MVP runs on a laptop. A board/UART/IMU port follows after the software MVP.

**Current state: modular simulator with stack and watchdog diagnostics.** Six
FreeRTOS tasks, all commands and telemetry, fault protection and live scenarios
run locally. Hosted CI runs Debug/Release build, cppcheck, tests and source-bound
trace verification on every push and pull request.

The local interface includes live flight controls and a separate **Recorded
mission** page with playback of a real fault/recovery sequence. **Verification →
Download verification bundle** exports the recording, telemetry CSV, inspection
records, supplied test reports and a SHA256 manifest. Playback never controls the
live flight. See [release instructions](docs/release.md) and
[M5 verification](docs/m5-verification.md).

## Run a live scenario

Start the local console, open Simulator and find **Live scenarios**. Stop any
existing flight, choose a scenario, then click **Run scenario**. The runner starts
a real test flight and checks every step. Try **Critical battery protection** to
watch NOMINAL → SAFE, fault clearance, and deliberate recovery to NOMINAL.
Four scenarios cover low battery, critical battery, high temperature and a telemetry
stall. Manual commands lock during a run; **Cancel scenario** stops its flight.
Successful runs leave the flight in NOMINAL for manual use. Download the result
with **Download scenario report**. Reports also remain in output/scenarios.
Restart the Python console after updating to M6. See [M6 checks](docs/m6-verification.md).

## Build and run

Prerequisites: CMake >=3.24, Git, a C11 GCC/Clang compiler, Python >=3.9, and Node.js >=18 (browser-codec tests).
On macOS install Apple's command-line developer tools; on Ubuntu install
`build-essential cmake git python3 nodejs`. The first configure needs network access to
fetch the pinned FreeRTOS kernel and Unity C test framework. No Python packages are needed.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel
./build/kestrel_m0
ctest --test-dir build --output-on-failure --output-junit results.xml
```

A successful run prints one JSON line with `messages: 20`, `checksum: 2870`,
`result: "pass"`, and an advancing `elapsed_ticks` value. Tasks and the queue use
static storage. The FreeRTOS POSIX implementation also uses its own host threads
and allocations; those are outside the application's static-memory guarantee.

For Release, use a separate directory:

```sh
cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --parallel
ctest --test-dir build-release --output-on-failure
```

Application assertions remain enabled in both configurations. All compiled C
sources, including the pinned kernel/port, build with `-Wall -Wextra -Werror`.

## Verification and CI

The [GitHub Actions workflow](.github/workflows/ci.yml) runs Debug and Release on
Ubuntu 24.04. It calls the same local script, which also requires `cppcheck`:

```sh
tools/ci.sh build Debug
```

CTest covers C/Python codecs, direct cross-language comparison, sequence rollover,
the browser inspector, a real scheduler/queue smoke test, dashboard integrity,
the trace checker and the 20-row requirements register. Cppcheck analyzes Kestrel C sources using
the build's compilation database; third-party sources are excluded from static
analysis. System-header lookup diagnostics and the required non-const FreeRTOS callback
signatures are narrowly suppressed; other enabled findings are fatal.

The trace tool distinguishes planned checks from passing evidence:

```sh
python3 tools/trace.py --milestone M5 --junit build/results.xml --provenance build/provenance.json
# Expected with passing tests and unchanged reviewed sources: 20/20 verified.
```

As milestones land, advance the gate in `tools/ci.sh` and supply their fresh
JUnit reports. Inspection/demo evidence has a separate documented record format.
Never label a requirement complete because its ID appears in a test name.

Local macOS checks and Ubuntu container checks are recorded in
[the M5 verification note](docs/m5-verification.md). The repository is https://github.com/zxcv616/kestrel. Check its Actions page for
the result for the exact commit; a local pass is not a hosted pass.

## Visual mission console

Use the [local simulator](http://127.0.0.1:8765/) after starting the Python server below.
The hosted progress site is no longer the primary interface and is not updated automatically.

The project now includes a milestone-aware GUI with an overview, real M0 runtime
receipt, roadmap, searchable requirements, task architecture, mode rules and
an interactive packet lab. The lab decodes pasted hex, checks CRCs and explores
48 shared valid/invalid vectors on both the hosted and local console. Open the local version after building:

```sh
python3 tools/dashboard.py serve --run-demo
```

Then visit http://127.0.0.1:8765. In Simulator, select **Start flight**, then **Enter NOMINAL**. Watch HK and ATT
arrive every second. Set the HK period to **250** and click **Apply period** to
speed up housekeeping. **Enter SAFE** stops ATT and restores 10-second HK.
Use **Request HK** for an immediate snapshot and **Download telemetry CSV** for the session log.
For faults, stop the current flight, choose **Start test flight**, enter NOMINAL,
and select **Battery 15%** under Fault testing. **Inject for 5 seconds** shows
LOW_POWER then automatic recovery. Try **Battery 5%** to see SAFE persist after
recovery; select **Enter NOMINAL** only after active faults clear.
Restart your Python console after upgrading so it loads the new backend.
The M0 demonstration remains available separately.
The private hosted version displays a clearly labeled recorded M2 session and
cannot control your laptop. See [dashboard maintenance](docs/dashboard.md) for exports and the GUI
deliverables required at each milestone. CI generates a fresh snapshot after
checks pass; hosted publication remains a separate step.

## Design and roadmap

- [Requirements register](docs/requirements.md): all 20 IDs, acceptance rules,
  planned tests/inspections, and the milestone at which evidence is required.
- [Design decisions](docs/design.md): ownership, modes, watchdog limits, fault
  injection/recovery, memory policy, and explicit changes from the original PDF.
- [Packet contract](docs/icd.md): exact headers, payload widths/units, CRC,
  commands, ACK semantics, and event/fault identifiers for M1.
- [Milestones](docs/milestones.md): delivery sequence and acceptance gates.

The final architecture uses six application tasks with queue-only communication.
M0 deliberately uses two demonstration tasks plus the kernel idle task to prove
build, scheduler, and queue integration first. The original planning PDF is
retained unchanged as the source proposal; the documents above are the clarified
implementation baseline.

FreeRTOS V11.3.2 is pinned to commit
`8a59a4b19bf72977819feddef87d41163ced7004`. Its upstream MIT license is retained
in the fetched source under `build/_deps/freertos_kernel-src/LICENSE.md`.
The POSIX simulator is useful for functional and measured timing tests; it does
not establish hard-real-time guarantees on embedded hardware.

## Packet library

The C API is in `fsw/include/kestrel_packet.h`; link `kestrel_packets`.
Encoding and decoding use bounded caller-owned buffers and allocate no memory.
Sequence state belongs to one sender; take a count once when committing a packet
for transmission. M2 integrates this library with the UDP flight runtime.

```python
from ground.ccsds import Packet, encode, decode
wire = encode(Packet(0x100, 0, 0, {"function": 0, "argument": 0}))
assert wire.hex() == "1900c00000060000000000967f"
assert decode(wire).fields == {"function": 0, "argument": 0}
```

Unity C v2.6.1 is pinned to `cbcd08fa7de711053a3deec6339ee89cad5d2697`;
its MIT license remains in the fetched source. `tests/vectors/README.md` explains
the independent reference packet construction. Optional codec sanitizer checks:

```sh
cmake -S . -B build-sanitize -DCMAKE_BUILD_TYPE=Debug -DKESTREL_SANITIZERS=ON
cmake --build build-sanitize --parallel
ctest --test-dir build-sanitize -R 'test_fsw_00[56]' --output-on-failure
```

## Standalone flight and ground tools

The easiest path is the local console above. For separate terminals instead:

```sh
./build/kestrel_flight
python3 -m ground.cli noop
python3 -m ground.cli request_hk
python3 -m ground.cli listen --seconds 11
```

Run the flight process in one terminal and one ground command at a time in
another; stop flight with Ctrl-C. The GUI receiver and CLI cannot both own UDP
5001. Flight owns UDP 5000 and always sends to ground at 5001, all on loopback.
An initial SAFE HK is followed by a ten-second periodic stream; REQUEST_HK
returns immediately without resetting that cadence. ACKs have a 100 ms target
under the tested traffic envelope and a one-second ground timeout. No automatic
retries. Occupied ports fail visibly rather than sharing sockets.

The implemented flow adds Mode, Sensors and Watchdog around Link → Command → Telemetry → Link. C task/queue/packet
storage is static; the POSIX kernel uses host threads. SET_HK_RATE is denied in SAFE; production INJECT_FAULT returns UNKNOWN_FUNCTION
after packet validation. Use `python3 -m ground.cli set_mode --argument 2` for
NOMINAL or `--argument 1` for SAFE. In NOMINAL, use
`python3 -m ground.cli set_hk_rate --argument 250`. Ground logs are retained under
`output/telemetry/`; each CLI invocation creates its own session log. Prefer the
console for a continuous receiver and complete session history.

## Task and transport layout

```text
Ground <-> hal/udp_link.c <-> Link -> Command -> Mode
                              ^         |       ^
                              |         v       | samples
                              +---- Telemetry  Sensors
                                      ^         |
                                      +-- Watchdog <- check-ins from all six tasks
```

Task implementations live in fsw/src/tasks; packet codecs in fsw/src/ccsds;
transport in fsw/src/hal. Startup and static queues are in fsw/src/flight.c.
The HAL is nonblocking and task-independent; phase 2 adds UART framing and hardware
sensor drivers. The local console's **Stack & watchdog health · received HK**
panel shows six stack marks, stall flags and dropped-event counts.

`configCHECK_FOR_STACK_OVERFLOW=2` and an aborting hook are enabled. **POSIX caveat:**
FreeRTOS high-water marks describe backing buffers, not the separate pthread stacks
actually executing host tasks. On the embedded port they measure task stack usage.
Mode participates in check-ins and its stall is visible through an independent
Watchdog-to-Telemetry queue. A permanently stalled Mode cannot transition to SAFE;
a stalled watchdog cannot supervise itself. **Phase 2 adds a hardware watchdog
timer to reset the MCU independently of the software scheduler.**

HK revision 2 is 49 bytes. Restart the Python console after rebuilding so the
flight, ground decoder and browser use the same format. Old HK recordings use the
previous ICD and are not accepted by the current packet inspector.
