# Kestrel interface control document (HK revision 2)

C and Python implement this wire contract. M4 adds real simulated sensors,
fault protection and a separate KESTREL_TEST build with fault injection.
Production command dispatch rejects INJECT_FAULT after wire validation.
One UDP datagram contains exactly one complete packet, never a fragment or batch.
Flight receives on 127.0.0.1:5000; ground receives on 127.0.0.1:5001. Flight sends
only to that configured loopback endpoint, not the source address of arbitrary
input. The maximum accepted datagram/packet size is 256 bytes; detect truncation
and reject oversized datagrams rather than interpreting their first 256 bytes.
All multibyte fields are big-endian. Signed integers use two's complement.

## Envelope

| Offset | Width | Field |
| --- | --- | --- |
| 0 | 2 bytes | Version=0 (bits 15..13), type TM=0/TC=1 (bit 12), secondary-header flag=1 (bit 11), APID (bits 10..0) |
| 2 | 2 bytes | Sequence flags=3 (bits 15..14), sequence count (bits 13..0) |
| 4 | 2 bytes | Total packet bytes minus 7 (bytes after primary header minus 1) |
| 6 | 4 bytes | Sender mission elapsed milliseconds, uint32, modulo 2^32 |
| 10 | Variable | Payload described below |
| Last 2 | 2 bytes | CRC over every preceding byte, excluding CRC itself |

CRC-16/CCITT-FALSE: width=16, polynomial=0x1021, init=0xFFFF, refin=false,
refout=false, xorout=0x0000. Check value for ASCII `123456789` is 0x29B1.
The timestamp is each sender's monotonic elapsed time since process start;
command timestamps do not schedule execution. EVENT timestamps record the event
occurrence, which can precede transmission during a link/telemetry outage. Each sender initializes each APID
sequence at 0 and increments modulo 16384 once a packet is committed for sending.
A UDP send failure can produce an observable sequence gap; never reuse that
sequence. ACK's envelope sequence belongs to APID 0x013, independent of the
command sequence echoed inside its payload. RESET_COUNTERS never resets packet
sequences or elapsed time. Duplicate commands are processed normally in the MVP;
there is no replay suppression or automatic ground retry.

## Telemetry payloads (offsets relative to byte 10)

| APID | Type | Payload fields in wire order | Payload / total bytes |
| --- | --- | --- | --- |
| 0x010 | HK | mode:u8, uptime_s:u32, battery_mV:u16, battery_percent:u8, temperature_centiC:i16, accepted:u32, rejected:u32, last_fault:u16, dropped_events:u32, task_stalled_mask:u8, stack_link:u16, stack_command:u16, stack_mode:u16, stack_telemetry:u16, stack_sensors:u16, stack_watchdog:u16 | 37 / 49 |
| 0x011 | ATT | rate_x_millideg_s:i16, rate_y_millideg_s:i16, rate_z_millideg_s:i16 | 6 / 18 |
| 0x012 | EVENT | event_id:u16, severity:u8, parameter_1:i32, parameter_2:i32 | 11 / 23 |
| 0x013 | ACK | command_sequence:u16, status:u8 | 3 / 15 |

For unavailable sensors: battery_mV=0xFFFF, battery_percent=0xFF,
temperature_centiC=-32768, and ATT rates=-32768. These sentinels are excluded
from valid simulator readings. Uptime seconds and command counters wrap modulo
2^32. Mode IDs and timing are defined in design.md.

## Command payloads (APID 0x100, type=1)

| Function | Command | Arguments after function:u8 | Payload / total bytes |
| --- | --- | --- | --- |
| 0x00 | NOOP | None | 1 / 13 |
| 0x01 | SET_MODE | target:u8 (SAFE=1 or NOMINAL=2) | 2 / 14 |
| 0x02 | RESET_COUNTERS | None | 1 / 13 |
| 0x03 | SET_HK_RATE | nominal_period_ms:u16, 250..10000 inclusive | 3 / 15 |
| 0x04 | REQUEST_HK | None | 1 / 13 |
| 0x05 | INJECT_FAULT | fault_id:u8, test build only | 2 / 14 |

Test injections: 1=stall link, 2=stall command, 3=stall telemetry, 4=stall sensors,
5=battery 15%, 6=battery 5%, 7=temperature 61 C, 8=temperature -21 C,
9=sensor dropout, 10=stall Mode (detection only). Fixed duration: 5 s, following a 100 ms arming delay to allow the acceptance ACK. Allow one injection at a time; another
returns BUSY. Production builds treat function 0x05 as UNKNOWN_FUNCTION.
No injection command is permitted in SAFE, including in test builds.

## Validation, ACKs, and counters

Statuses: 0=OK, 1=BAD_LENGTH, 2=BAD_HEADER, 3=BAD_CRC, 4=UNKNOWN_APID,
5=UNKNOWN_FUNCTION, 6=BAD_ARGUMENT, 7=MODE_DENIED, 8=BUSY.

Validation order: datagram bounds and declared total length; primary header fixed
bits/type; CRC; APID; function and exact payload length; arguments; mode/build
permissions and owner availability. The first failing check determines status.
Bad function-specific payload lengths use BAD_LENGTH even though they are checked
later. Header version/type/secondary-header/sequence flags must match the contract.

Return exactly one ACK for every datagram serviced after initialization, including
invalid packets. If at least four input bytes exist, echo the low 14 bits of
bytes 2..3 even if the CRC/header is invalid. Otherwise use 0xFFFF, which cannot
be a legitimate 14-bit sequence. This is an explicit exception to the PDF's
unqualified command-ACK wording. There is no BOOT ACK guarantee.

Rejected commands increment rejected once and have no other effect. Accepted
commands increment accepted once. RESET_COUNTERS sets rejected=0 and accepted=1
(the reset command itself); it clears no faults, modes, sequence counts or clock.
REQUEST_HK's response includes its own accepted count. Mode-sensitive commands
are accepted only after their owning task commits the decision. State transitions
and their events are serialized by mode; ACK and EVENT arrival order is not an
API guarantee. Ground correlates ACKs by echoed command sequence.

## Events and faults

Event IDs: 1=MODE_CHANGED (old mode, new mode); 2=FAULT_DETECTED (fault code,
source task ID); 3=FAULT_CLEARED (fault code, source task ID). Severity:
0=INFO, 1=WARNING, 2=ERROR. Mode/clear events are INFO, low battery is WARNING,
critical/stall/dropout/queue-overflow faults are ERROR.

Fault codes: 0=NONE, 1=LOW_BATTERY, 2=CRITICAL_BATTERY, 3=OVER_TEMPERATURE,
4=UNDER_TEMPERATURE, 5=SENSOR_DROPOUT, 6=TASK_STALL, 7=QUEUE_OVERFLOW.
Task IDs: 0=system, 1=link, 2=command, 3=mode, 4=telemetry, 5=sensors,
6=watchdog. Injection IDs and reported fault codes are distinct namespaces.
LOW_BATTERY clears at 30%; critical battery clears at 10%; thermal faults clear
inside the valid range; dropout clears on a fresh valid sample; stalls clear on
resumed check-ins. Critical faults still block mode recovery. Queue-overflow
clears after a successful enqueue on the affected queue. `last_fault` updates
when a newly active fault is detected; in a single sample, process noncritical
conditions first and critical faults last so the latter remain visible.

M1 added shared known-good binary vectors for every packet type and command,
CRC failure, malformed lengths, signed endpoints, and sequence rollover. C and
Python must agree byte-for-byte; at least one vector is checked independently
rather than generated by either implementation under test.

## HK revision 2 and diagnostics

The HK payload is now 37 bytes (49 total); the former 20-byte payload is rejected
by current codecs. Upgrade flight, Python and browser together. The unchanged
CCSDS version field remains zero; this is an application ICD revision.
`dropped_events` is a cumulative uint32 event-enqueue failure counter (modulo 2^32),
not reset by RESET_COUNTERS. It does not count UDP loss. `task_stalled_mask` uses
bits 1..6 for Link, Command, Mode, Telemetry, Sensors, Watchdog. Telemetry receives
watchdog health directly, independently of Mode. It reports detection, not proof
of SAFE entry. A permanently stalled Mode cannot commit SAFE.

The six stack fields are minimum unused FreeRTOS StackType_t elements since boot,
65535 when not yet available. Each task measures itself and copies the value with
its check-in; Watchdog aggregates it. On this POSIX port, pthread execution uses a
separate host stack: these marks describe the FreeRTOS backing buffers only, not
host stack headroom. Mode stall injection pauses Mode for five seconds; sensors
continue but Mode-owned sensor snapshots can become stale meanwhile.

Entering SAFE invalidates and discards unsent ATT, including the Link retry slot.
A mode epoch prevents pre-SAFE ATT from reappearing after a rapid return to NOMINAL.
Discarded already-serialized packets may leave ATT sequence gaps. Packets already
submitted to the transport cannot be recalled.

### First HK at startup

No packet format change: the first HK is held until a fresh valid sensor sample
is available. Later invalid sensor readings retain the established sentinels.
Uptime is whole elapsed seconds and can legitimately be zero on the first HK.
No ground command is required to obtain the initial housekeeping packet.
