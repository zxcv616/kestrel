#include "kestrel_packet.h"
#include <limits.h>
#include <string.h>

static uint16_t read16(const uint8_t *p) { return (uint16_t)(((uint16_t)p[0] << 8) | p[1]); }
static uint32_t read32(const uint8_t *p) { return ((uint32_t)read16(p) << 16) | read16(p + 2); }
static void write16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v; }
static void write32(uint8_t *p, uint32_t v) { write16(p, (uint16_t)(v >> 16)); write16(p + 2, (uint16_t)v); }
/* Avoid implementation-defined unsigned-to-signed conversions at wire boundaries. */
static int16_t signed16(uint16_t v) { return v <= INT16_MAX ? (int16_t)v : (int16_t)(-(int32_t)(UINT16_MAX - v) - 1); }
static int32_t signed32(uint32_t v) { return v <= INT32_MAX ? (int32_t)v : -(int32_t)(UINT32_MAX - v) - 1; }
static int apid_index(uint16_t apid)
{
    if (apid >= KESTREL_APID_HK && apid <= KESTREL_APID_ACK) return (int)(apid - KESTREL_APID_HK);
    return apid == KESTREL_APID_CMD ? 4 : -1;
}
static KestrelStatus payload_length(uint16_t apid, uint8_t function, size_t *length)
{
    switch (apid) {
        case KESTREL_APID_HK: *length = 37; break;
        case KESTREL_APID_ATT: *length = 6; break;
        case KESTREL_APID_EVENT: *length = 11; break;
        case KESTREL_APID_ACK: *length = 3; break;
        case KESTREL_APID_CMD:
            if (function > 5) return KESTREL_UNKNOWN_FUNCTION;
            *length = function == 3 ? 3 : (function == 1 || function == 5 ? 2 : 1);
            break;
        default: return KESTREL_UNKNOWN_APID;
    }
    return KESTREL_OK;
}
static KestrelStatus validate(const KestrelPacket *p)
{
    if (p->sequence > 16383) return KESTREL_BAD_ARGUMENT;
    if (p->apid == KESTREL_APID_CMD) {
        uint16_t arg = p->payload.command.argument;
        switch (p->payload.command.function) {
            case 0: case 2: case 4: if (arg != 0) return KESTREL_BAD_ARGUMENT; break;
            case 1: if (arg != 1 && arg != 2) return KESTREL_BAD_ARGUMENT; break;
            case 3: if (arg < 250 || arg > 10000) return KESTREL_BAD_ARGUMENT; break;
            case 5: if (arg < 1 || arg > 10) return KESTREL_BAD_ARGUMENT; break;
            default: return KESTREL_UNKNOWN_FUNCTION;
        }
    }
    /* Telemetry codecs preserve every representable field value, including sentinels.
       Semantic health checks and mode/build authorization belong to their owners. */
    return KESTREL_OK;
}
KestrelStatus kestrel_packet_encode(const KestrelPacket *packet, uint8_t *output,
                                    size_t capacity, size_t *written)
{
    if (packet == NULL || output == NULL || written == NULL) return KESTREL_BAD_ARGUMENT;
    size_t payload = 0;
    uint8_t function = packet->apid == KESTREL_APID_CMD ? packet->payload.command.function : 0;
    KestrelStatus status = payload_length(packet->apid, function, &payload);
    if (status != KESTREL_OK) return status;
    status = validate(packet);
    if (status != KESTREL_OK) return status;
    size_t length = 12 + payload;
    if (capacity < length) return KESTREL_BAD_LENGTH;
    uint8_t encoded[49] = {0}; /* Largest current packet is HK; no heap storage. */
    write16(encoded, (uint16_t)(0x0800 | (packet->apid == KESTREL_APID_CMD ? 0x1000 : 0) | packet->apid));
    write16(encoded + 2, (uint16_t)(0xc000 | packet->sequence));
    write16(encoded + 4, (uint16_t)(length - 7));
    write32(encoded + 6, packet->time_ms);
    uint8_t *p = encoded + 10;
    switch (packet->apid) {
        case KESTREL_APID_HK:
            p[0] = packet->payload.hk.mode;
            write32(p + 1, packet->payload.hk.uptime_s);
            write16(p + 5, packet->payload.hk.battery_mv);
            p[7] = packet->payload.hk.battery_percent;
            write16(p + 8, (uint16_t)packet->payload.hk.temperature_centi_c);
            write32(p + 10, packet->payload.hk.accepted);
            write32(p + 14, packet->payload.hk.rejected);
            write16(p + 18, packet->payload.hk.last_fault);
            write32(p + 20, packet->payload.hk.dropped_events);
            p[24] = packet->payload.hk.task_stalled_mask;
            write16(p + 25, packet->payload.hk.stack_link);
            write16(p + 27, packet->payload.hk.stack_command);
            write16(p + 29, packet->payload.hk.stack_mode);
            write16(p + 31, packet->payload.hk.stack_telemetry);
            write16(p + 33, packet->payload.hk.stack_sensors);
            write16(p + 35, packet->payload.hk.stack_watchdog);

            break;
        case KESTREL_APID_ATT:
            write16(p, (uint16_t)packet->payload.att.x);
            write16(p + 2, (uint16_t)packet->payload.att.y);
            write16(p + 4, (uint16_t)packet->payload.att.z);
            break;
        case KESTREL_APID_EVENT:
            write16(p, packet->payload.event.id); p[2] = packet->payload.event.severity;
            write32(p + 3, (uint32_t)packet->payload.event.parameter_1);
            write32(p + 7, (uint32_t)packet->payload.event.parameter_2);
            break;
        case KESTREL_APID_ACK:
            write16(p, packet->payload.ack.command_sequence); p[2] = packet->payload.ack.status;
            break;
        case KESTREL_APID_CMD:
            p[0] = function;
            if (payload == 2) p[1] = (uint8_t)packet->payload.command.argument;
            if (payload == 3) write16(p + 1, packet->payload.command.argument);
            break;
        default: return KESTREL_UNKNOWN_APID;
    }
    write16(encoded + length - 2, kestrel_crc16(encoded, length - 2));
    memcpy(output, encoded, length);
    *written = length;
    return KESTREL_OK;
}
KestrelStatus kestrel_packet_decode(const uint8_t *data, size_t length, KestrelPacket *packet)
{
    if (data == NULL || packet == NULL) return KESTREL_BAD_ARGUMENT;
    if (length < 12 || length > KESTREL_MAX_PACKET) return KESTREL_BAD_LENGTH;
    if ((size_t)read16(data + 4) + 7 != length) return KESTREL_BAD_LENGTH;
    uint16_t first = read16(data);
    uint16_t apid = first & 0x07ff;
    if ((first & 0xe800) != 0x0800 || (read16(data + 2) & 0xc000) != 0xc000)
        return KESTREL_BAD_HEADER;
    if (apid_index(apid) >= 0 && ((first >> 12) & 1) != (apid == KESTREL_APID_CMD))
        return KESTREL_BAD_HEADER;
    if (kestrel_crc16(data, length - 2) != read16(data + length - 2)) return KESTREL_BAD_CRC;
    if (apid == KESTREL_APID_CMD && length < 13) return KESTREL_BAD_LENGTH;
    size_t payload = 0;
    uint8_t function = apid == KESTREL_APID_CMD ? data[10] : 0;
    KestrelStatus status = payload_length(apid, function, &payload);
    if (status != KESTREL_OK) return status;
    if (length != payload + 12) return KESTREL_BAD_LENGTH;
    KestrelPacket decoded = {0};
    decoded.apid = apid; decoded.sequence = read16(data + 2) & 0x3fff;
    decoded.time_ms = read32(data + 6);
    const uint8_t *p = data + 10;
    switch (apid) {
        case KESTREL_APID_HK:
            decoded.payload.hk.mode = p[0]; decoded.payload.hk.uptime_s = read32(p + 1);
            decoded.payload.hk.battery_mv = read16(p + 5); decoded.payload.hk.battery_percent = p[7];
            decoded.payload.hk.temperature_centi_c = signed16(read16(p + 8));
            decoded.payload.hk.accepted = read32(p + 10); decoded.payload.hk.rejected = read32(p + 14);
            decoded.payload.hk.last_fault = read16(p + 18);
            decoded.payload.hk.dropped_events = read32(p + 20);
            decoded.payload.hk.task_stalled_mask = p[24];
            decoded.payload.hk.stack_link = read16(p + 25);
            decoded.payload.hk.stack_command = read16(p + 27);
            decoded.payload.hk.stack_mode = read16(p + 29);
            decoded.payload.hk.stack_telemetry = read16(p + 31);
            decoded.payload.hk.stack_sensors = read16(p + 33);
            decoded.payload.hk.stack_watchdog = read16(p + 35);
            break;
        case KESTREL_APID_ATT:
            decoded.payload.att.x = signed16(read16(p)); decoded.payload.att.y = signed16(read16(p + 2));
            decoded.payload.att.z = signed16(read16(p + 4)); break;
        case KESTREL_APID_EVENT:
            decoded.payload.event.id = read16(p); decoded.payload.event.severity = p[2];
            decoded.payload.event.parameter_1 = signed32(read32(p + 3));
            decoded.payload.event.parameter_2 = signed32(read32(p + 7)); break;
        case KESTREL_APID_ACK:
            decoded.payload.ack.command_sequence = read16(p); decoded.payload.ack.status = p[2]; break;
        case KESTREL_APID_CMD:
            decoded.payload.command.function = function;
            decoded.payload.command.argument = payload == 3 ? read16(p + 1) : (payload == 2 ? p[1] : 0);
            break;
        default: return KESTREL_UNKNOWN_APID;
    }
    status = validate(&decoded);
    if (status == KESTREL_OK) *packet = decoded;
    return status;
}
KestrelStatus kestrel_sequence_take(KestrelSequences *state, uint16_t apid, uint16_t *sequence)
{
    if (state == NULL || sequence == NULL) return KESTREL_BAD_ARGUMENT;
    int index = apid_index(apid);
    if (index < 0) return KESTREL_UNKNOWN_APID;
    if (state->next[index] > 16383) return KESTREL_BAD_ARGUMENT;
    *sequence = state->next[index];
    state->next[index] = (uint16_t)((*sequence + 1) & 0x3fff);
    return KESTREL_OK;
}
const char *kestrel_status_name(KestrelStatus status)
{
    switch (status) {
        case KESTREL_OK: return "OK";
        case KESTREL_BAD_LENGTH: return "BAD_LENGTH";
        case KESTREL_BAD_HEADER: return "BAD_HEADER";
        case KESTREL_BAD_CRC: return "BAD_CRC";
        case KESTREL_UNKNOWN_APID: return "UNKNOWN_APID";
        case KESTREL_UNKNOWN_FUNCTION: return "UNKNOWN_FUNCTION";
        case KESTREL_BAD_ARGUMENT: return "BAD_ARGUMENT";
        default: return "UNKNOWN_STATUS";
    }
}
