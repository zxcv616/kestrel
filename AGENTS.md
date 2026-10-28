# Kestrel project instructions

Read README.md and the relevant docs before changing flight behavior. The original
PDF is preserved; docs/requirements.md, docs/design.md and docs/icd.md form the
clarified implementation baseline. Do not claim requirement verification from test
names alone, or hard-real-time behavior from the POSIX simulator.

## Milestone GUI requirement

The user requires the GUI to evolve with every milestone. Treat the dashboard as
part of each milestone's definition of done:

- Read docs/dashboard.md and the GUI deliverable for the milestone in
  dashboard/project.json. Implement the corresponding real UI/backend behavior.
- Update dashboard/project.json when milestone state or capabilities change.
  Keep unavailable telemetry blank and unsupported commands disabled. Label
  references, recorded data and live data distinctly.
- Generate fresh reports, export the console with tools/dashboard.py, and verify
  relevant interactions and responsive layouts. Do not edit generated data.json
  as a substitute for the source register, reports or project manifest.
- Focus on the local working simulator UI. The user has explicitly deprioritized
  the hosted progress site; do not update or publish it unless requested.
- Preserve the Kestrel logo and visual style. Use functional labels, prioritize
  simulator operations, and avoid slogans or marketing copy.
- A CI export is not hosted publication. Report any publication or live-data
  limitation explicitly. Never claim GitHub CI green without a hosted result.

Authored UI source: dashboard/web. Generated deployment checkout: sites/ (ignored).
The local runner binds to loopback and executes only its configured M0 or flight
binaries. Keep Host/Origin/token checks and operation locking. Stop only the
flight child owned by this console, clean it up on server exit, and never accept
shell commands or executable paths from HTTP requests.
