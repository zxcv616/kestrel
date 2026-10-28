# M5 source inspection

Reviewed by Codex against the source hashes in FSW-016 through FSW-019.json.
Scope: authored C application, configuration, packet library, and CMake build.
The regex/preprocessor checks in tools/release_check.py supplement this ownership
review; they are not a proof of arbitrary future C program behavior.

## FSW-016: application memory

flight.c main allocates six StaticTask_t objects and fixed StackType_t arrays.
Each queue uses xQueueCreateStatic with a distinct control object and byte array.
The QUEUE macro's do/while block gives each invocation its own static objects.
Check-in, congestion and injection channels use six distinct array slots.
Datagrams, packets, observer text, sequence state and working variables live in
fixed-size local buffers on those statically provided task stacks. There are no
application heap calls, variable-length arrays or recursive task functions.
main.c's two-task foundation demo follows the same storage policy. Packet encode,
decode and CRC operate on bounded caller-owned buffers; encode uses 32 local bytes.
FreeRTOSConfig.h disables dynamic allocation and uses kernel-provided static idle
memory. No FreeRTOS heap implementation is linked. POSIX threads, libc, sockets,
Python and the browser can allocate; the guarantee excludes the host runtime.

## FSW-017: mutable state ownership

Context is initialized before vTaskStartScheduler and thereafter passed as const.
It contains queue handles and immutable ports/epoch/observer configuration, not
pointers to shared mutable flight payloads. Message structs contain values and
fixed arrays, not pointers to another task's working state. Ownership reviewed:

| Owner | Private working state | Copied queue messages |
| --- | --- | --- |
| Link | Socket, retained outgoing datagram, injection timer | incoming, outgoing, periodic; check-in/congestion |
| Command | Counts, decoded command | incoming → requests/replies → decisions; check-in/congestion |
| Mode | Mode, faults, sample, health, injection schedule | requests/replies, samples, health, congestion → state/events/injections |
| Telemetry | APID counters, deadlines, current snapshot | decisions/state/events → outgoing/periodic; check-in/congestion |
| Sensors | Current injection and sample deadline | injections → samples/check-in |
| Watchdog | Check-in timestamps and missed-window counters | checkins → health |

All runtime payload transfer uses FreeRTOS queue copying. No mutexes, shared
mutable globals, task notifications or stream buffers implement application IPC.
Queue implementation internals and host-library state are outside this ownership
contract. The test observer writes from Mode only; it does not share state with
another flight task. Ground Python locks are outside the flight-task requirement.

## FSW-018: production/test separation

CMake builds the same source into two separately named targets; only
kestrel_flight_test receives KESTREL_TEST=1. Preprocessed translation units are
checked for the injection activation assignment and observer implementation/CLI.
They must occur in the test unit and be absent in production. Production still
understands the wire function code for validation but its Mode dispatch returns
UNKNOWN_FUNCTION. Inert Injection type/queue storage in production does not provide
an activation path. Production malformed/unsupported command tests verify rejection;
the recorded test mission verifies real injection acceptance and expiry.

## FSW-019: warnings and analysis

Every authored application translation unit is checked in compile_commands.json
for -Wall -Wextra -Werror. The same flags apply to the pinned kernel and POSIX port
in CMake. Debug and Release builds retain configASSERT regardless of NDEBUG.
The retained Linux cppcheck transcript covers production and KESTREL_TEST paths
with warning, style, performance and portability enabled; only missing system
include lookup is suppressed. Build/test and analysis evidence is retained with
the release records. This inspection does not claim a hosted GitHub Actions run.
