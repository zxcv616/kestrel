# M1 packet protocol verification

Executed October 27, 2026 (America/Los_Angeles).

M1 implements the wire contract in C and Python, independent of transport and
FreeRTOS tasks. It adds an interactive browser packet inspector and advances
the requirements gate to M1. FSW-005 and FSW-006 have passing codec evidence;
18 requirements remain pending. M2 must exercise these codecs through real UDP
senders and receivers, including one sequence increment per emitted packet.

## Executed checks

| Environment | Configuration | Result |
| --- | --- | --- |
| macOS, AppleClang 16 | Debug | 10/10 CTest suites passed |
| macOS, AppleClang 16 | Release | 10/10 CTest suites passed |
| Ubuntu 24.04 container, GCC 13.3 | Debug | 10/10 suites; cppcheck and M1 trace gate passed |
| Ubuntu 24.04 container, GCC 13.3 | Release | 10/10 suites; cppcheck and M1 trace gate passed |
| macOS, AddressSanitizer + UndefinedBehaviorSanitizer | Debug codec library, C tests and probe | 5/5 protocol suites passed; no sanitizer findings |

The full local CI script stopped at missing macOS cppcheck after its Debug
CTest pass. Release CTest and the combined M1 trace gate were run separately.
Static analysis was completed successfully in both Ubuntu configurations. These
container runs are local verification, not hosted GitHub Actions runs.

Reports: `build/results.xml`, `build-release/results.xml`,
`build/verification/ubuntu-m1-debug.xml`,
`build/verification/ubuntu-m1-release.xml`, and `build-sanitize/results.xml`.
Generated reports are ignored build artifacts; reproduce with README commands.

## Coverage

- Frozen independent corpus: 16 valid packets and 32 invalid packets. Every
  telemetry type and all six command formats are covered. Builds only translate
  those frozen literals into C fixtures; they do not calculate expected bytes.
- CRC check `123456789` → `0x29B1`; independently inspectable NOOP
  `1900c00000060000000000967f`. See `tests/vectors/README.md`.
- Explicit big-endian wire fields, signed extrema, sentinels, maximum timestamps,
  exact payload widths, command bounds, short buffers and unchanged C output on
  rejected input. No dynamic allocation in the packet library.
- Every APID's independent sequence state starts at zero and crosses 16383 → 0,
  including interleaved senders' packet types.
- Direct C/Python comparison: 1,148 cases (48 fixtures plus 1,100 deterministic
  generated valid/corrupt packets). All decoded fields, re-encoded bytes and
  rejection statuses agree.
- The actual browser codec passes all 48 fixtures under Node, plus malformed-hex
  and whitespace-input cases.
- Browser interaction: default NOOP valid; CRC-bit flip rejected with different
  received/computed CRC; signed ATT limits decoded correctly; non-hex input
  rejected. Desktop 1440×1000 and narrow 390×844 layouts inspected.
- Existing scheduler/queue, dashboard evidence, local-runner security and trace
  checker regression suites pass.

## Scope and remaining work

Encoding commands does not execute them or grant mode/test-build permission.
The runtime executable is still the M0 queue demo. UDP, live telemetry, command
ACKs and mode authorization start with M2 and M3. The hosted console computes
packet inspection in the browser; its verification records remain a published
snapshot. It cannot run local flight software.

The existing private Site receives the M1 GUI at the same URL and audience.
GitHub CI remains pending because no remote repository is configured. M0's
hosted-CI gate is still explicitly pending; no hosted result is inferred from
local or container checks.
