#include "kestrel_runtime.h"
/* FreeRTOS TaskFunction_t requires void *, even though Context is immutable. */
// cppcheck-suppress constParameterPointer
void command_task(void *argument)
{
    const Context *c = argument;
    uint32_t accepted = 0, rejected = 0;
    Injection injection = {0};
    for (;;) {
        if (!ready(c, 2, &injection)) continue;
        Datagram in;
        if (xQueueReceive(c->incoming, &in, pdMS_TO_TICKS(10)) != pdPASS) continue;
        KestrelPacket packet;
        uint8_t status = (uint8_t)kestrel_packet_decode(in.bytes, in.length, &packet);
        bool request_hk = false;
        if (status == KESTREL_OK && packet.apid != KESTREL_APID_CMD) status = KESTREL_UNKNOWN_APID;
        if (status == KESTREL_OK) {
            ModeRequest request = {.function = packet.payload.command.function,
                                   .argument = packet.payload.command.argument};
            while (xQueueSend(c->requests, &request, pdMS_TO_TICKS(10)) != pdPASS) {
                checkin(c, 2); congestion(c, 2, true);
            }
            ModeReply reply;
            while (xQueueReceive(c->replies, &reply, pdMS_TO_TICKS(10)) != pdPASS) checkin(c, 2);
            congestion(c, 2, false);
            status = reply.status;
            request_hk = status == KESTREL_OK && packet.payload.command.function == 4;
        }
        if (status == KESTREL_OK) {
            if (packet.payload.command.function == 2) { accepted = 0; rejected = 0; }
            ++accepted;
        } else ++rejected;
        Decision decision = {
            .echo = in.length >= 4 ? (uint16_t)((((uint16_t)in.bytes[2] << 8) | in.bytes[3]) & 0x3fff) : UINT16_MAX,
            .status = status, .request_hk = request_hk, .accepted = accepted, .rejected = rejected
        };
        while (xQueueSend(c->decisions, &decision, pdMS_TO_TICKS(10)) != pdPASS) {
            checkin(c, 2); congestion(c, 2, true);
        }
        congestion(c, 2, false);
    }
}
