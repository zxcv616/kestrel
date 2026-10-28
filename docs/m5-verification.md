# M5 local release verification — 0.1.0

Historical baseline before modular hardening. See [current verification](hardening-verification.md) for the newer implementation and GitHub CI status.

M5's local implementation is delivered. **The overall release gate remains open:**
no GitHub repository destination is configured, so hosted CI and reproduction from
a published commit are pending. No hosted site has been published or updated.

## Build results

All 28 CTest suites pass in each environment below. The two new suites run the
real recorded mission and inspect the actual production/test compilation units.
The full earlier packet, mode, timing, watchdog, fault and console coverage remains.

| Environment | CTest | Recorded-demo critical SAFE delay |
| --- | --- | --- |
| macOS Debug | 28/28 | 85 ms |
| macOS Release | 28/28 | 95 ms |
| Ubuntu 24.04 container Debug | 28/28 | 88 ms |
| Ubuntu 24.04 container Release | 28/28 | 94 ms |

The final inspection/CSV reference recording entered SAFE in 96 ms. These are
measured host results with a 1-second critical-fault limit, not hardware guarantees.
JUnit reports are retained in docs/verification/reports. Linux cppcheck production
and KESTREL_TEST translation units have no enabled findings in both configurations;
transcripts are retained beside the inspection records. macOS compilation checks
use the same warning-as-error flags; Linux provides the static-analysis evidence.
The updated trace and bundle tests also pass after the final UI/export changes.

## Review and recorded evidence

FSW-016 through FSW-019 contain the source/configuration/build review and exact
SHA256 source/evidence bindings. The ownership audit explains each task and queue,
the application-only static allocation scope, and the production injection guard.
The preprocessing check proves the activation/observer code is absent in the
production translation unit and present in the test unit. It supplements, rather
than substitutes for, source review. Source changes invalidate the records.

FSW-020 contains a real UDP recording of eight accepted commands covering all six
command types, with HK/ATT/EVENT/ACK received and decoded. Every CSV row is decoded
again from its raw hex and compared with its stored fields, APID, sequence and
timestamp; CSV row count equals the receiver count at a locked recording cutoff.
The mission uses isolated ports and stops only its own child. The reference JSON
and CSV are under docs/verification/m5-demo; CTest writes fresh build-local copies.
All 20 requirements pass the M5 evidence gate with the supplied reports.

## Interface review

Recorded mission is a separate page with explicit recorded-data labels, Play,
Pause, Restart and a time slider. Playback holds actual checkpoint values and
never sends commands. The 7-second checkpoint shows recorded SAFE and battery 5%;
playback completion shows deliberate ground recovery to NOMINAL. Verification
shows review scope/hashes and exports a ZIP with records, CSV, reports and a
SHA256 manifest. The bundle's contents and hashes are tested automatically.
Browser playback, scrubbing, restart, inspection details, ZIP download and console
errors were checked. Desktop and a 390-pixel embedded viewport were reviewed; the
narrow document measured 390 pixels with no horizontal overflow.

## Reproduction and remaining limits

A separate clean source copy passed tools/ci.sh build Release on Ubuntu 24.04:
28/28 suites, cppcheck, all 20 requirements and console export, with no copied
build/dependency directories. Its report is retained as clean-source-release.xml.
This is not a Git checkout: project files are untracked in the user's original workspace and
no commit/push has been performed. Published-commit reproduction and hosted Actions
must be verified after a repository is supplied. The milestone stays active.
