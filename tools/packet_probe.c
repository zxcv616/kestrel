/* Host-only diagnostic: stdin hex lines -> JSON records. No transport or execution. */
#include "kestrel_packet.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

static int nibble(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}
static void print_fields(const KestrelPacket *p)
{
    switch (p->apid) {
        case KESTREL_APID_HK:
            printf("\"mode\":%u,\"uptime_s\":%" PRIu32 ",\"battery_mv\":%u,\"battery_percent\":%u,"
                   "\"temperature_centi_c\":%d,\"accepted\":%" PRIu32 ",\"rejected\":%" PRIu32 ",\"last_fault\":%u",
                   p->payload.hk.mode, p->payload.hk.uptime_s, p->payload.hk.battery_mv,
                   p->payload.hk.battery_percent, p->payload.hk.temperature_centi_c,
                   p->payload.hk.accepted, p->payload.hk.rejected, p->payload.hk.last_fault);
            printf(",\"dropped_events\":%" PRIu32 ",\"task_stalled_mask\":%u", p->payload.hk.dropped_events, p->payload.hk.task_stalled_mask);
            printf(",\"stack_link\":%u", p->payload.hk.stack_link);
            printf(",\"stack_command\":%u", p->payload.hk.stack_command);
            printf(",\"stack_mode\":%u", p->payload.hk.stack_mode);
            printf(",\"stack_telemetry\":%u", p->payload.hk.stack_telemetry);
            printf(",\"stack_sensors\":%u", p->payload.hk.stack_sensors);
            printf(",\"stack_watchdog\":%u", p->payload.hk.stack_watchdog);
            break;
        case KESTREL_APID_ATT:
            printf("\"x\":%d,\"y\":%d,\"z\":%d", p->payload.att.x, p->payload.att.y, p->payload.att.z); break;
        case KESTREL_APID_EVENT:
            printf("\"id\":%u,\"severity\":%u,\"parameter_1\":%" PRId32 ",\"parameter_2\":%" PRId32,
                   p->payload.event.id, p->payload.event.severity, p->payload.event.parameter_1, p->payload.event.parameter_2); break;
        case KESTREL_APID_ACK:
            printf("\"command_sequence\":%u,\"status\":%u", p->payload.ack.command_sequence, p->payload.ack.status); break;
        case KESTREL_APID_CMD:
            printf("\"function\":%u,\"argument\":%u", p->payload.command.function, p->payload.command.argument); break;
        default: break;
    }
}
int main(void)
{
    char line[1024];
    while (fgets(line, sizeof(line), stdin) != NULL) {
        size_t count = strcspn(line, "\r\n");
        uint8_t wire[257];
        if (count % 2 != 0 || count / 2 > sizeof(wire)) { puts("{\"error\":\"BAD_LENGTH\"}"); continue; }
        int valid = 1;
        for (size_t i = 0; i < count / 2; ++i) {
            int high = nibble(line[2 * i]), low = nibble(line[2 * i + 1]);
            if (high < 0 || low < 0) { valid = 0; break; }
            wire[i] = (uint8_t)((high << 4) | low);
        }
        if (!valid) { puts("{\"error\":\"BAD_HEX\"}"); continue; }
        KestrelPacket p;
        KestrelStatus status = kestrel_packet_decode(wire, count / 2, &p);
        if (status != KESTREL_OK) { printf("{\"error\":\"%s\"}\n", kestrel_status_name(status)); continue; }
        uint8_t encoded[256]; size_t length = 0;
        status = kestrel_packet_encode(&p, encoded, sizeof(encoded), &length);
        if (status != KESTREL_OK) return 1;
        printf("{\"apid\":%u,\"sequence\":%u,\"time_ms\":%" PRIu32 ",\"fields\":{", p.apid, p.sequence, p.time_ms);
        print_fields(&p); printf("},\"hex\":\"");
        for (size_t i = 0; i < length; ++i) printf("%02x", encoded[i]);
        puts("\"}");
    }
    return ferror(stdin) ? 1 : 0;
}
