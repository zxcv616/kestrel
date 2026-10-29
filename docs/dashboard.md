# Kestrel local console

The console has two views: **Main** for live operation and **Diagnostics** for
packet inspection and supporting measurements. Authored assets are in
`dashboard/web`; `tools/dashboard.py` exports them to `output/dashboard/local`.
The logo, palette variables and DM Sans / IBM Plex Mono fonts are unchanged.

## Run and demonstrate

Build the binaries, then run `python3 tools/dashboard.py serve --run-demo` and
open http://127.0.0.1:8765. Stop an old console with Ctrl-C before restarting.

1. Start test flight. Flight waits for fresh sensor data before its first HK.
   The console sends no commands automatically. Select SET_MODE NOMINAL,
   Review & send, then confirm.
2. Inject **Stall command**. Received EVENT/HK show the task fault and SAFE.
3. Wait for the received **FAULT CLEARED · Command** event (the injection lasts
   five seconds). Confirm SET_MODE NOMINAL to recover.

All five main sections fit at 1440×900: mode/mission time, link freshness,
health strip, newest-first events and command panel. Long event and command
histories scroll inside their panels. Health values occupy four labeled cards.
Events are single lines: time, transition/fault and one category badge. SAFE is
amber, NOMINAL green, LOW_POWER yellow-lime, and BOOT/awaiting gray, using existing
palette colors. Active fault rows use the critical color; FAULT CLEARED uses success color. Smaller screens stack the sections.

## Data rules

Spacecraft mode comes only from received HK or a newer received mode-transition
EVENT. Internal test observations never drive this console. Until telemetry
arrives, show Awaiting telemetry; do not invent a BOOT state. Mission elapsed
time is the latest received packet timestamp, held between packets.

Link age uses the backend's monotonic age of the last valid received packet,
advanced locally between polls. Yellow begins at 1.5× and red at 3× the expected
HK period: NOMINAL 1 s by default, SAFE 10 s, LOW_POWER 5 s. An acknowledged
SET_HK_RATE updates the NOMINAL expectation for the session. Outgoing commands
and invalid packets do not refresh link age. Age continues increasing if HTTP
polling fails. The failed operation is shown separately.

Battery, temperature and accepted/rejected counts come from decoded HK. They
gray out when HK reaches 1.5× the expected period or the flight stops; a fresh
ACK cannot make an old HK reading fresh. Invalid sensor sentinels stay blank.
Battery below 20% is amber and below 10% red; temperature outside −20…60 °C is
red. Rejected-command counts are amber when nonzero. Color is reserved for status
and limits. Unknown values remain an em dash, never zero substitutes.

SET_MODE requires confirmation. Commands show pending until their result arrives;
ACK OK means ACCEPTED, other ACK codes mean REJECTED. Missing ACKs and send
failures have separate labels, not fabricated rejection codes. Session controls
and pending actions are local control state, not spacecraft telemetry.

## Diagnostics

Battery/temperature and HK/ATT interval charts use received samples. Stack marks,
watchdog stall flags, dropped events, last fault and voltage use HK. Stack marks
are minimum unused FreeRTOS buffer elements, **not host pthread stack usage**.
The packet inspector opens captured TX/RX bytes or user-pasted hex, displaying
CRC, primary header, timestamp and decoded payload. It never transmits edits.
HK-rate/reset commands, command receipt details and telemetry CSV remain here.

Project reference pages, decorative animation, internal-observer health/timelines,
scenario controls and recorded playback are absent from the console. Tests,
scenario CLI tools and shared vectors are retained. `dashboard/archive` preserves
the earlier console/playback code for future portfolio use; it is not loaded by
the console. Recorded evidence remains in `docs/verification/m5-demo`.

## Maintenance and safety

Update `dashboard/project.json` as capabilities change. Export fresh assets and
reports; never hand-edit generated data.json. Verify live interactions and desktop
and narrow layouts. A static export is not a live flight and must not substitute
recorded readings. Do not publish the hosted progress site unless requested.

The local runner binds to loopback, retains Host/Origin/token checks and operation
locking, runs only its configured binaries and cleans up only its owned child.
HTTP requests cannot supply shell commands or executable paths.

## Simplification verification

Automated display tests cover exact thresholds in all three operational modes,
independent HK staleness, no internal-observer mode override, advancing age during
connection loss, newer versus older EVENT ordering, acknowledged HK rate changes,
and pending/accepted/rejected/timeout distinctions. Browser verification exercised
the real Command-stall sequence, confirmation cancellation, captured-packet decode
and invalid bytes, with no browser exceptions. Main measured 1440×900 with no page
scroll; a 390-pixel view had no horizontal overflow. Screenshots are under
`output/dashboard/console-*.png`. These checks are local, not a hosted CI result.

### SAFE startup regression

Flight now waits for a fresh sensor sample before emitting its first HK. While
waiting, Telemetry continues to service commands and check-ins; after 500 ms it
allows fault events through even without a valid sensor sample. Subsequent HK
continues to use unavailable sentinels for genuinely invalid/stale sensors.
The first packet may correctly report uptime zero (whole seconds) when boot
finishes within a second. Mission time always reflects received packet time.

The console sends no commands on start, reload, polling or navigation. Every
command requires an operator action. REQUEST_HK remains an explicit button.
The dev server sends Cache-Control: no-store on assets and API responses.

Regression checks assert first SAFE HK has valid battery, voltage and temperature,
zero accepted/rejected commands and no ground TX/history. Independent wire tests
cover HK in all four modes (BOOT is decoder-only); live tests cover SAFE, NOMINAL
and LOW_POWER. Browser verification also checks no POST except the requested
start during initial loading, polling and reload, followed by the complete
Command-stall recovery and success-colored fault-clear event. Static asset
responses are tested for no-store headers.
