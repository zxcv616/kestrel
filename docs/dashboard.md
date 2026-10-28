# Kestrel simulator interface

The console is part of the project, and must evolve with every milestone. Its
source lives in `dashboard/web`; its delivery plan and curated capability labels
live in `dashboard/project.json`. Requirements come directly from the canonical
register, and verification states come from supplied JUnit/review evidence.

## Open locally

From the repository root, after building:

```sh
python3 tools/dashboard.py serve --run-demo
```

Open http://127.0.0.1:8765. The local server binds only to loopback. The runtime
button launches the fixed `build/kestrel_m0` executable; it accepts no shell
commands or paths from the browser. It requires a same-origin session token,
allows one run at a time, and has a 10-second process deadline. Ctrl-C stops it.
Use `--port 8766` if the default port is busy, or `--binary PATH` for another
locally built M0 configuration.

The Run button shows actual executable output: message count, checksum, elapsed
FreeRTOS ticks and host wall time. The task/queue graphic is a topology diagram,
not a fabricated per-message timing trace. M2 flight telemetry comes from the separate flight process. Sensors and attitude
remain unavailable; an empty field is never replaced with fabricated readings.

## Hosted snapshot

The private hosted console is an exported snapshot. It cannot launch a process on
your laptop or connect to loopback UDP. It displays the captured run and reports,
with timestamps, and disables the local Run button. Its Refresh button reloads
the published snapshot; it does not claim to run tests or synchronize your laptop.

Generate the publishable site:

```sh
python3 tools/dashboard.py build --run-demo
```

The default local output is `output/dashboard/local`. A deliberate hosted export
can use `--output sites/kestrel-console/dist`. The Sites deployment checkout
has its own managed source history and is ignored by the main repository; all
authored UI source, the exporter and the stable Site identity remain tracked in
the main repository. `dashboard/site.json` records the existing private Site.
Preserve its ID; do not register another Site on updates.

The static output contains no session tokens, local absolute paths or credentials.
It includes copies of the referenced Markdown documents. The original PDF
is not uploaded. Browser exports provide the requirements CSV and recorded-run
JSON. No user data is persisted by the UI.

## Update on every milestone

1. Implement the backend and the GUI capability listed for that milestone in
   `dashboard/project.json`. Keep commands disabled until their real backend is
   available; the M2 Python bridge owns loopback UDP; browsers do not access UDP directly.
2. Update the current milestone, deliverables, acceptance gate and hosted CI
   status only from actual evidence. A local pass does not imply hosted CI green.
3. Run the milestone's tests, with fresh JUnit reports. The shared `tools/ci.sh`
   exports a dashboard snapshot under the build directory after its checks pass.
4. Export the main console with the relevant reports and a real demo run. Defaults
   include local Debug/Release reports and the current Ubuntu M5 reports. Override
   them with repeated `--report 'Environment label=path/to/results.xml'` arguments
   as new reports arrive; keep labels and report provenance accurate.
5. Review desktop and narrow-screen views, requirement filters, details, downloads,
   and any newly enabled command path. Rebuild the export if source changed.
6. Keep changes local unless the user requests publication. The hosted progress
   site is no longer the primary interface and is not maintained automatically.

## Screen progression

- M0: verified foundation, actual queue-demo receipt, roadmap, requirement matrix,
  task/mode/packet contracts, and original implementation notes.
- M1: actual packet bytes, decoded fields, CRC validation and vector results.
- M2: live connection/HK state, real NOOP and REQUEST_HK, command ACK history.
- M3: live mode transitions, HK/ATT plots, mode/rate commands and event history.
- M4: test-build fault injection, watchdog health and measured fault recovery.
- M5: complete verification evidence, recorded demo and release exports.

The separate `docs/m0-verification.md` is the original M0 verification record.
New dashboard tests appear in subsequent reports; that historical record is not
retroactively relabeled as evidence for newly added functionality.

## M1 packet lab

System → Packet lab provides a hex editor, 48 shared reference vectors, colored
header/timestamp/payload/CRC bytes, decoded fields and received/calculated CRCs.
“Flip a CRC bit” flips the final bit to demonstrate rejection. The browser performs
this computation locally, including on the hosted site; it never transmits a
command. The vector table records Python checks at export time. C/Python and
browser checks also run in CTest. Live flight values remain unavailable until M2.

## M2 live flight controls

In Runtime, select **Start flight**, **Send NOOP**, then **Request HK**. The local
server starts its configured `build/kestrel_flight`, binds the ground receiver,
and waits for actual SAFE housekeeping. **Stop flight** stops only this server's
child and releases its receiver. Closing the server also cleans up that child.
Another simulator or ground client on ports 5000/5001 produces a visible startup
error; the console does not take over someone else's process.

The view polls once per second. Mode, uptime and counts come from received HK,
with a separate age and stale indicator; sensor fields stay blank in M2.
ACK rows report command sequence, returned status, measured round-trip time and
ACK packet sequence. HTTP control operations require the local Host, same Origin
and session token, and accept only four fixed actions (start, stop, noop,
request_hk). Actions are serialized and commands are never retried automatically.

The private Site has disabled flight controls and a clearly labeled recorded
session. Packet inspection remains interactive there. Capture and export with:

```sh
python3 tools/record_m2.py
python3 tools/dashboard.py build --run-demo --flight-record output/dashboard/m2-flight-record.json
```

Live operation requires the local console; a hosted static site cannot reach this
laptop's UDP sockets. No public bridge or tunnel is enabled by M2.

## Interface priorities

Open Simulator by default. Keep session controls, actual telemetry, freshness and
acknowledgements together. Packet inspector is a direct navigation destination.
Project status, verification, milestones and system documentation are secondary
reference tools. Keep the queue demonstration collapsed under Diagnostics.
Preserve the logo and instrument-style palette; use literal functional headings
instead of promotional slogans. Local console connection is distinct from a
running flight session. The hosted site is left unchanged unless requested.

## Live communication diagram

The simulator shows a ground station and satellite computer. Incoming and outgoing
pulses are driven by actual UDP packet records, never button clicks alone. The
ground receiver retains the latest 100 accepted packet records per session, with
a unique session ID and monotonic event IDs; the UI shows the latest eight.
Unexpected-source and invalid packets are counted but do not light up the satellite.
Click a packet chip or moving pulse to inspect an editable copy of its exact hex
bytes. Changes in the inspector never modify or retransmit the captured packet.

Animation is slowed to 850 ms per message for visibility; displayed round-trip
times remain measured values. Initial history is not replayed on page reload.
A new session resets animation state; queued animation is bounded to 24 messages
so a backlog cannot grow indefinitely. M3 samples recent periodic traffic and clears older animation backlog for control events. Recent packet chips remain independently
available. SAFE appears only from received HK, stale state is amber, and a stopped
flight is dimmed. This is a communication diagram, not orbital or attitude physics.
Reduce motion honors the operating-system preference and provides a manual toggle.
Restart the Python server after upgrading to enable raw packet capture.

## M3 local controls

Start flight, select **Enter NOMINAL**, and observe the current-mode highlight,
HK/ATT timing plots and mode events. Default NOMINAL telemetry is 1 Hz for both
HK and ATT. Enter an HK period of 250–10000 ms and select **Apply period** while
in NOMINAL. The command acknowledgement confirms acceptance; the plot shows the
measured packet intervals. **Enter SAFE** restores 10-second HK and suppresses ATT.
Mode changes also produce immediate HK; requested/immediate packets can shorten
plotted HK intervals. Plot axes use flight packet time, not animation time.

**Reset counters** sets accepted=1 and rejected=0; request HK to see the new counts
(the request increments accepted again). It does not reset mode, packet sequences,
or elapsed time. **Download telemetry CSV** saves all valid telemetry received in
the session, not just the bounded plot history. Logs persist in output/telemetry
and the most recent log remains downloadable after stopping. Mode events are
retained separately from the last 100 packet-animation records.

The healthy-system prerequisite fixture is labeled in the UI; actual sensor and
watchdog behavior is M4. Sensor readings remain unavailable. New actions retain
Host/Origin/token checks and serialized operation handling. Restart the local
Python server after updating. The hosted site is not part of this update.

## M4 sensor and fault controls

**Start flight** runs production sensor/protection logic without injection support.
**Start test flight** runs the separately compiled test executable and starts the
internal observation reader. Both are fixed configured local executables; HTTP
cannot submit an executable path. Stop the current flight before switching builds.

Enter NOMINAL, choose a condition under **Fault testing**, then **Inject for 5
seconds**. Battery 15% enters LOW_POWER and returns automatically after recovery.
Battery 5%, extreme temperature, dropout or a task stall enter SAFE. Wait for the
condition to expire and active faults to clear, then select **Enter NOMINAL**.
A second injection is blocked while one is armed/active; injection is denied in
SAFE. Real sensor/fault state now gates recovery; there is no healthy fixture.

Sensor history plots use received HK, with unavailable samples omitted. Task
check-ins and the recovery timeline use the explicitly labeled internal test
channel, so a stalled telemetry/link path can still be inspected. HK values
remain last-received readings and may lag the Mode owner during an outage.
Each observation has freshness, and the timeline records actual flight timestamps.
The complete .observations.jsonl log lives beside the telemetry CSV in
output/telemetry. All test actions retain the same Host, Origin, token and operation
locking rules. Restart the Python console after updating to M4.

## M5 recorded mission and release evidence

**Recorded mission** replays actual captured checkpoints with Play, Pause, Restart
and a flight-time slider. It is clearly separate from the live simulator; replay
never invokes a flight endpoint. Battery, mode and packet counts hold at the last
recorded checkpoint. A table gives the complete observed sequence.

**Verification** links to the evidence ZIP and shows inspection details, including
review scope and source hashes. The exporter bundles the recorded mission JSON
and CSV, inspection evidence, supplied JUnit reports and a SHA256 manifest. Missing
reports are not invented. Changed reviewed sources invalidate inspection evidence.
The release remains locally verified with hosted CI explicitly pending. Restart
the Python console after this backend update, then refresh the browser.

## Simulator interface cleanup

Flight controls and the live communication diagram share the top row on desktop.
Test flight is the primary start action; production remains explicitly available.
Mode controls, four received-HK readings and NOOP/Request HK stay visible. Fault
testing sits immediately below, with the exact readiness reason and a setup action.
Sensor history, telemetry settings/session counters, timing/events, command history
and task health/recovery details expand on demand. Open sections and form edits
persist across live polling; the existing DOM-preserving update retains native
select controls. Narrow layouts stack the controls and diagram without overflow.
All earlier controls and data remain available. This is a presentation update;
flight behavior, packet contracts and the M5 evidence scope are unchanged.

The user chose continued laptop-simulator development rather than the hardware
phase. Frontend cleanup is the first follow-on; future simulator milestones will
be scoped separately. The unresolved M5 hosted-CI condition remains explicit.

## M6 live scenarios

**Live scenarios** runs a fixed sequence against the real test flight while the
satellite and telemetry continue to update. Stop any manual flight first, select a
scenario and press **Run scenario**. Steps report actual results, including the
protection delay and its limit. Success leaves NOMINAL for manual operation;
**Cancel scenario** or failure stops that scenario's process. Manual controls are
locked during execution, enforced by the server as well as the UI. A report can
be downloaded after completion, cancellation or failure. Older reports persist in
output/scenarios. Restart the Python console after upgrading this backend.

## Hardening diagnostics

Stack & watchdog health displays received-HK stack marks, stall bits and cumulative
dropped events for production and test flights. Missing marks remain blank. The
POSIX backing-buffer limitation is visible beside the values. Test mode adds a
Mode-stall condition explicitly labeled detection-only. Refresh/restart both the
Python server and the flight for the 49-byte HK revision.
