# Modular flight source inspection

Reviewed authored flight sources for this hardening revision. The accompanying
FSW-016 through FSW-020 records bind the reviewed files with SHA256 hashes.

- Startup creates six static tasks and every queue with distinct static storage.
  Message structs contain values/arrays, not pointers to another task's data.
  No application heap calls or variable-length allocations were introduced.
- Each task is a separate translation unit. Context is initialized before the
  scheduler and immutable afterward. Link alone calls the transport adapter;
  the adapter's private socket/destination state is accessed only by Link.
- Checkin copies timestamp and each task's own stack mark. Watchdog owns aggregate
  health; separate overwrite queues deliver health to Mode and Telemetry. Mode
  owns dropped-event counts and publishes them in copied State messages.
- Mode owns the mode epoch. Link consumes its copied gate, purges obsolete ATT
  without purging HK, and checks retained ATT before retrying. Scheduler suspension
  covers only a final gate check plus nonblocking transport submission. The
  adapter contract prohibits blocking waits; no shared mutable task state is used.
- Stack checking mode 2 and the fatal hook are compiled into demo and flight
  executables. POSIX pthread execution stacks are separate from FreeRTOS backing
  storage; no embedded stack-headroom claim is made from host values.
- Production excludes injection activation, observer and overflow fixture CLI.
  Test Mode-stall injection pauses work/check-ins; it tests detection through HK,
  not recovery of a permanently stalled Mode. Hardware watchdog reset is phase 2.
- Cppcheck covers production and test flight source. Six narrow inline suppressions
  cover constParameterPointer on FreeRTOS task entry points: TaskFunction_t requires
  void *, so changing these to const void * violates the callback signature.
  System include lookup is suppressed; other enabled findings remain fatal.
- Static checks and preprocessing supplement this review; they are not proofs
  of all future behavior. Fresh CI binds reports to source hashes and a Git commit.

## First-HK readiness review

Telemetry's new local `hk_started` boolean gates first HK on the existing
fresh copied sensor snapshot. No allocations, shared state, task priorities,
queue sizes, wire formats or production injection guards changed. The existing
bounded decision wait and watchdog check-ins remain active while waiting.
EVENT draining resumes after 500 ms even if sensors never initialize. Later
sensor loss still uses existing HK sentinels. The boot test now requires valid
battery/voltage/temperature in the first datagram and zero command counters;
the controller test also asserts an empty TX history. Fresh build inspection
and cppcheck passed for this revision.
