# M6 live scenario verification

M6 extends the laptop simulator with fixed, repeatable scenarios. Seven scenario integration checks pass in the retained M6 reports and were rerun
successfully during hardening; no new flight behavior or packet contract is introduced. The original
20 flight requirements remain the baseline; scenario acceptance adds integration
coverage without relabeling M5's separate public-release condition.

Scenarios: low battery (15%), critical battery (5%), over-temperature (61 C), and
Telemetry task stall. Each starts a fresh test flight, enters NOMINAL, injects for
five seconds, checks protection and clearance, performs deliberate ground recovery
where needed, and confirms NOMINAL through a new received HK. Protection time uses
the independent test observation. The telemetry-stall scenario also checks three
missed watchdog windows within four seconds.

Only one operation owns the flight. A scenario will not replace an existing
session. All manual HTTP mutations and competing scenario starts are rejected
while the worker owns the operation lock; status reads and authorized cancellation
remain available. Cancellation/failure stop the owned flight. A pass leaves it in
NOMINAL for manual use. Server shutdown cancels and joins the worker before closing
its flight. There are no arbitrary scripts, shell commands, executable paths or
user-defined step payloads exposed through HTTP.

Each completed/cancelled/failed run retains JSON under output/scenarios with step
results, command receipts, final observation and received telemetry CSV where
available. The UI downloads the latest report. These are measured scenario results,
not replacement verification of all 20 requirements or hardware timing guarantees.
