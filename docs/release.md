# Reproduce Kestrel 0.1.0

The software MVP runs on macOS or Ubuntu with CMake 3.24+, C11 compiler, Git,
Python 3.9+ and Node 18+. Ubuntu static analysis also requires cppcheck. FetchContent
resolves the pinned FreeRTOS and Unity commits on first configure; network access
is required. A copied clean source tree is supported without generated artifacts.

```sh
git clone https://github.com/zxcv616/kestrel.git
cd kestrel
tools/ci.sh build Debug
python3 tools/dashboard.py serve --run-demo
```

On a macOS host without cppcheck, use --skip-analysis for the inspection command
and retain a separate Linux analysis report. That option explicitly records that
analysis did not run; it is not an analysis pass. Repeat using build-release and
-DCMAKE_BUILD_TYPE=Release. tools/ci.sh performs the complete build/test/analysis/M5
gate/export sequence on a host with cppcheck.

The automated mission uses separate ephemeral loopback ports, runs all six command
types, receives HK/ATT/EVENT/ACK and verifies every CSV row against its raw packet.
It exercises Battery 15% → LOW_POWER → NOMINAL and Battery 5% → SAFE → deliberate
ground recovery. It always closes its own process and receiver. Run separately:

```sh
python3 tools/record_m5.py --output build/release/demo
```

The checked recording under docs/verification/m5-demo is the release reference.
New CTest runs write build/release/demo without replacing that reference. The
UI's Recorded mission page replays checkpoints from the reference, with recorded
timestamps and no commands to the running simulator. It holds values between
checkpoints rather than inventing interpolation. Verification's downloadable ZIP
contains the reference CSV, receipts, inspection records and supplied reports,
plus a SHA256 manifest. It contains evidence, not a compiled distributable binary.

For a live flight use Simulator → Start test flight → Enter NOMINAL, select a
condition and press Inject. The recorded mission is a separate, clearly labeled
view. Restart an existing Python console after upgrading the backend.

Inspection JSON records bind to SHA256 hashes of reviewed source and evidence.
Source edits invalidate affected records. Perform the review again before
refreshing hashes; never regenerate pass records solely to satisfy the gate.

GitHub Actions verifies a fresh checkout on every push and pull request in Debug
and Release. Each job builds with warnings as errors, runs CTest and live scenarios,
runs cppcheck, and binds source/report hashes before the trace gate. Download its
artifacts for the exact commit's results and provenance. Private repository access
is required; public publication and a demo GIF remain separate release work.
No hosted site publication is required or performed. POSIX timing is measured
behavior, not a hardware deadline guarantee. Mode-stall detection is available in
HK; independent hardware watchdog reset remains phase 2.
