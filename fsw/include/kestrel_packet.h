#ifndef KESTREL_PACKET_H
#define KESTREL_PACKET_H
#include <stddef.h>
#include <stdint.h>

enum { KESTREL_MAX_PACKET = 256, KESTREL_APID_HK = 0x010,
       KESTREL_APID_ATT = 0x011, KESTREL_APID_EVENT = 0x012,
       KESTREL_APID_ACK = 0x013, KESTREL_APID_CMD = 0x100 };
typedef enum {
    KESTREL_OK = 0, KESTREL_BAD_LENGTH, KESTREL_BAD_HEADER,
    KESTREL_BAD_CRC, KESTREL_UNKNOWN_APID, KESTREL_UNKNOWN_FUNCTION,
    KESTREL_BAD_ARGUMENT
} KestrelStatus;
typedef struct {
    uint16_t apid;
    uint16_t sequence;
    uint32_t time_ms;
    union {
        struct { uint8_t mode; uint32_t uptime_s; uint16_t battery_mv;
                 uint8_t battery_percent; int16_t temperature_centi_c;
                 uint32_t accepted, rejected; uint16_t last_fault;
                 uint32_t dropped_events; uint8_t task_stalled_mask;
                 uint16_t stack_link, stack_command, stack_mode, stack_telemetry, stack_sensors, stack_watchdog; } hk;
        struct { int16_t x, y, z; } att;
        struct { uint16_t id; uint8_t severity; int32_t parameter_1, parameter_2; } event;
        struct { uint16_t command_sequence; uint8_t status; } ack;
        struct { uint8_t function; uint16_t argument; } command;
    } payload;
} KestrelPacket;
/* Caller-owned; single task owns and commits counts when enqueuing for send. */
typedef struct { uint16_t next[5]; } KestrelSequences;

uint16_t kestrel_crc16(const uint8_t *data, size_t length);
/* No allocation; no output modification on failure. Encoding is transactional. */
KestrelStatus kestrel_packet_encode(const KestrelPacket *packet, uint8_t *output,
                                    size_t capacity, size_t *written);
KestrelStatus kestrel_packet_decode(const uint8_t *data, size_t length, KestrelPacket *packet);
KestrelStatus kestrel_sequence_take(KestrelSequences *state, uint16_t apid, uint16_t *sequence);
const char *kestrel_status_name(KestrelStatus status);
#endif
