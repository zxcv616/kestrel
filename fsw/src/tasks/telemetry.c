#include "kestrel_runtime.h"
static Datagram serialize(const Context *c, KestrelSequences *sequences, KestrelPacket *packet)
{
    Datagram d = {0};
    if (packet->apid != KESTREL_APID_EVENT) packet->time_ms = (uint32_t)elapsed(c);
    configASSERT(kestrel_sequence_take(sequences, packet->apid, &packet->sequence) == KESTREL_OK);
    configASSERT(kestrel_packet_encode(packet, d.bytes, sizeof(d.bytes), &d.length) == KESTREL_OK);
    return d;
}
static bool sensor_fresh(const Context *c, const State *state)
{
    return state->sample.valid && elapsed(c) - state->sample.at < 500;
}
static KestrelPacket housekeeping(const Context *c, uint32_t accepted, uint32_t rejected, const State *state, const Health *health)
{
    KestrelPacket p = {.apid = KESTREL_APID_HK};
    p.payload.hk.mode = state->mode;
    p.payload.hk.uptime_s = (uint32_t)(elapsed(c) / 1000);
    bool valid = sensor_fresh(c, state);
    p.payload.hk.battery_mv = valid ? 3800 : UINT16_MAX;
    p.payload.hk.battery_percent = valid ? state->sample.battery : UINT8_MAX;
    p.payload.hk.temperature_centi_c = valid ? state->sample.temperature : INT16_MIN;
    p.payload.hk.accepted = accepted; p.payload.hk.rejected = rejected;
    p.payload.hk.last_fault = state->last_fault;
    p.payload.hk.dropped_events = state->dropped_events;
    p.payload.hk.task_stalled_mask = (uint8_t)health->stalled;
    p.payload.hk.stack_link = health->stack_free[1];
    p.payload.hk.stack_command = health->stack_free[2];
    p.payload.hk.stack_mode = health->stack_free[3];
    p.payload.hk.stack_telemetry = health->stack_free[4];
    p.payload.hk.stack_sensors = health->stack_free[5];
    p.payload.hk.stack_watchdog = health->stack_free[6];

    return p;
}
static void send_control(const Context *c, const Datagram *d, Injection *injection)
{
    for (;;) {
        if (!ready(c, 4, injection)) continue;
        if (xQueueSend(c->outgoing, d, pdMS_TO_TICKS(10)) == pdPASS) break;
        congestion(c, 4, true);
    }
    congestion(c, 4, false);
}
static uint16_t hk_period(const State *state)
{
    return state->mode == SAFE ? 10000 : state->mode == LOW_POWER ? 5000 : state->period;
}
/* FreeRTOS TaskFunction_t requires void *, even though Context is immutable. */
// cppcheck-suppress constParameterPointer
void telemetry_task(void *argument)
{
    const Context *c = argument;
    KestrelSequences sequences = {{0}};
    uint32_t accepted = 0, rejected = 0;
    State state = {.mode = SAFE, .period = 1000};
    Health health = {0};
    for (unsigned i = 1; i <= 6; ++i) health.stack_free[i] = UINT16_MAX;
    Injection injection = {0};
    (void)xQueueReceive(c->state, &state, 0);
    KestrelPacket hk;
    bool hk_started = false;
    uint64_t deadline = elapsed(c) + 10000, att_deadline = elapsed(c) + 1000;
    for (;;) {
        if (!ready(c, 4, &injection)) continue;
        (void)xQueueReceive(c->telemetry_health, &health, 0);
        State update;
        bool changed = false;
        if (xQueueReceive(c->state, &update, 0) == pdPASS) {
            changed = state.mode != update.mode;
            if (state.revision != update.revision) deadline = elapsed(c) + hk_period(&update);
            if (changed) att_deadline = elapsed(c) + 1000;
            state = update;
        }
        /* First HK must describe a real sensor sample. Keep servicing commands
         * and check-ins while waiting; a failed sensor cannot wedge Telemetry. */
        if (!hk_started && sensor_fresh(c, &state)) {
            hk = housekeeping(c, accepted, rejected, &state, &health);
            Datagram first = serialize(c, &sequences, &hk);
            send_control(c, &first, &injection);
            hk_started = true;
            deadline = elapsed(c) + hk_period(&state);
            changed = false;
        }
        /* Normally HK precedes the boot event. After the sensor freshness
         * deadline, allow fault events through even if no valid sample arrived. */
        /* Bound event work; a fault history must not starve command ACKs. */
        for (unsigned i = 0; i < BATCH && (hk_started || elapsed(c) >= 500); ++i) {
            Event event;
            if (xQueueReceive(c->events, &event, 0) != pdPASS) break;
            KestrelPacket packet = {.apid = KESTREL_APID_EVENT, .time_ms = event.at};
            packet.payload.event.id = event.id; packet.payload.event.severity = event.severity;
            packet.payload.event.parameter_1 = event.a; packet.payload.event.parameter_2 = event.b;
            Datagram out = serialize(c, &sequences, &packet);
            send_control(c, &out, &injection);
        }
        Decision decision;
        bool request_hk = false;
        if (xQueueReceive(c->decisions, &decision, pdMS_TO_TICKS(1)) == pdPASS) {
            accepted = decision.accepted; rejected = decision.rejected;
            KestrelPacket ack = {.apid = KESTREL_APID_ACK};
            ack.payload.ack.command_sequence = decision.echo; ack.payload.ack.status = decision.status;
            Datagram out = serialize(c, &sequences, &ack);
            send_control(c, &out, &injection);
            request_hk = decision.request_hk;
        }
        if (hk_started && (request_hk || changed)) {
            hk = housekeeping(c, accepted, rejected, &state, &health);
            Datagram out = serialize(c, &sequences, &hk);
            send_control(c, &out, &injection);
        }
        if (state.mode == NOMINAL && elapsed(c) >= att_deadline) {
            if (uxQueueSpacesAvailable(c->periodic) > 0) {
                KestrelPacket att = {.apid = KESTREL_APID_ATT};
                int16_t rate = sensor_fresh(c, &state) ? 0 : INT16_MIN;
                att.payload.att.x = rate; att.payload.att.y = rate; att.payload.att.z = rate;
                Datagram out = serialize(c, &sequences, &att);
                out.mode_epoch = state.mode_epoch;
                configASSERT(xQueueSend(c->periodic, &out, 0) == pdPASS);
            } else congestion(c, 4, true);
            att_deadline += 1000;
            if (att_deadline <= elapsed(c)) att_deadline = elapsed(c) + 1000;
        }
        if (hk_started && elapsed(c) >= deadline) {
            if (uxQueueSpacesAvailable(c->periodic) > 0) {
                hk = housekeeping(c, accepted, rejected, &state, &health);
                Datagram out = serialize(c, &sequences, &hk);
                configASSERT(xQueueSend(c->periodic, &out, 0) == pdPASS);
                congestion(c, 4, false);
            } else congestion(c, 4, true);
            deadline += hk_period(&state);
            if (deadline <= elapsed(c)) deadline = elapsed(c) + hk_period(&state);
        }
        /* Input queue wait above supplies the idle yield; pending work runs immediately. */
    }
}

