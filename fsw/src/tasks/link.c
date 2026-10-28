#include "kestrel_runtime.h"
#include "kestrel_link.h"
static bool is_attitude(const Datagram *packet)
{
    return packet->length >= 2 &&
        ((((uint16_t)packet->bytes[0] << 8) | packet->bytes[1]) & 0x7ff) == KESTREL_APID_ATT;
}
static void refresh_gate(const Context *c, ModeGate *gate)
{
    ModeGate update;
    if (xQueueReceive(c->link_mode, &update, 0) != pdPASS) return;
    *gate = update;
    /* Queue-only critical section: preserve HK while removing obsolete ATT.
     * The epoch also catches SAFE -> NOMINAL before Link resumes. */
    taskENTER_CRITICAL();
    UBaseType_t count = uxQueueMessagesWaiting(c->periodic);
    for (UBaseType_t i = 0; i < count; ++i) {
        Datagram packet;
        configASSERT(xQueueReceive(c->periodic, &packet, 0) == pdPASS);
        if (!is_attitude(&packet) || (gate->mode == NOMINAL && packet.mode_epoch == gate->epoch))
            configASSERT(xQueueSend(c->periodic, &packet, 0) == pdPASS);
    }
    taskEXIT_CRITICAL();
}
static int transmit_current(const Context *c, ModeGate *gate, const Datagram *packet)
{
    /* The HAL operation must be nonblocking. Prevent a Mode commit between the
     * final gate check and submission; never suspend scheduling across a wait. */
    vTaskSuspendAll();
    refresh_gate(c, gate);
    int result = 1; /* Obsolete ATT is deliberately discarded, not retried. */
    if (!is_attitude(packet) || (gate->mode == NOMINAL && packet->mode_epoch == gate->epoch))
        result = kestrel_link_send(packet->bytes, packet->length);
    (void)xTaskResumeAll();
    return result;
}
/* FreeRTOS TaskFunction_t requires void *, even though Context is immutable. */
// cppcheck-suppress constParameterPointer
void link_task(void *argument)
{
    const Context *c = argument;
    configASSERT(kestrel_link_open(c->flight_port, c->ground_port) == 1);
    ModeGate gate = {.mode = SAFE};
    Datagram outgoing;
    bool pending = false;
    Injection injection = {0};
    for (;;) {
        if (!ready(c, 1, &injection)) continue;
        /* Drain control first. One retained packet survives transient send failures. */
        for (unsigned i = 0; i < BATCH; ++i) {
            refresh_gate(c, &gate);
            if (!pending && xQueueReceive(c->outgoing, &outgoing, 0) != pdPASS &&
                xQueueReceive(c->periodic, &outgoing, 0) != pdPASS) break;
            int sent = transmit_current(c, &gate, &outgoing);
            configASSERT(sent >= 0);
            if (!sent) { pending = true; break; }
            pending = false;
        }
        for (unsigned i = 0; i < BATCH && uxQueueSpacesAvailable(c->incoming) > 0; ++i) {
            Datagram in = {0};
            /* 257-byte buffer distinguishes all oversized UDP datagrams from 256 bytes. */
            int received = kestrel_link_receive(in.bytes, sizeof(in.bytes), &in.length);
            configASSERT(received >= 0);
            if (!received) break;
            /* Link is the sole producer; the capacity reservation cannot be lost. */
            configASSERT(xQueueSend(c->incoming, &in, 0) == pdPASS);
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}
