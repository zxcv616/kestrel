#include "kestrel_runtime.h"
#include <stdio.h>
#include <unistd.h>
static void emit_event(const Context *c, uint16_t id, uint8_t severity,
                       int32_t a, int32_t b, uint32_t *dropped)
{
    Event event = {.id = id, .severity = severity, .a = a, .b = b, .at = (uint32_t)elapsed(c)};
    if (xQueueSend(c->events, &event, 0) != pdPASS) ++*dropped;
}
static void transition(const Context *c, State *state, uint8_t target, uint32_t *dropped)
{
    if (state->mode == target) return;
    emit_event(c, 1, 0, state->mode, target, dropped);
    ModeGate gate = {.mode = target, .epoch = ++state->mode_epoch};
    configASSERT(xQueueOverwrite(c->link_mode, &gate) == pdPASS);
    state->mode = target;
    state->changed_at = elapsed(c);
    ++state->revision;
}
#ifdef KESTREL_TEST
/* Test observation is independent of Link/Telemetry. Nonblocking writes cannot
 * hold Mode hostage if the observer stops reading. It is not a flight packet. */
static void observe(const Context *c, const State *state, const Health *health,
                    const Injection *injection, uint32_t dropped)
{
    if (!c->observe) return;
    char line[1024];
    uint64_t now = elapsed(c);
    int n = snprintf(line, sizeof(line),
        "{\"timeMs\":%llu,\"mode\":%u,\"changedAtMs\":%llu,\"faultMask\":%u,"
        "\"stalledMask\":%u,\"lastFault\":%u,\"sensorValid\":%s,\"battery\":%u,"
        "\"temperature\":%d,\"sensorAgeMs\":%llu,\"injection\":%u,"
        "\"injectionStartMs\":%llu,\"injectionEndMs\":%llu,\"droppedEvents\":%u,"
        "\"misses\":[%u,%u,%u,%u,%u,%u],\"checkinAgeMs\":[%llu,%llu,%llu,%llu,%llu,%llu]}\n",
        (unsigned long long)now, state->mode, (unsigned long long)state->changed_at,
        state->faults, health->stalled, state->last_fault,
        state->sample.valid && now - state->sample.at < 500 ? "true" : "false",
        state->sample.battery, state->sample.temperature,
        (unsigned long long)(now - state->sample.at), injection->id,
        (unsigned long long)injection->start, (unsigned long long)injection->end, dropped,
        health->misses[1], health->misses[2], health->misses[3], health->misses[4], health->misses[5], health->misses[6],
        (unsigned long long)(now-health->last[1]), (unsigned long long)(now-health->last[2]),
        (unsigned long long)(now-health->last[3]), (unsigned long long)(now-health->last[4]),
        (unsigned long long)(now-health->last[5]), (unsigned long long)(now-health->last[6]));
    if (n > 0 && (size_t)n < sizeof(line)) {
        ssize_t written = write(STDOUT_FILENO, line, (size_t)n);
        (void)written;
    }
}
#endif
/* FreeRTOS TaskFunction_t requires void *, even though Context is immutable. */
// cppcheck-suppress constParameterPointer
void mode_task(void *argument)
{
    const Context *c = argument;
    State state = {.mode = SAFE, .period = 1000};
    Health health = {0};
    uint64_t last_valid = 0;
    uint32_t dropped = 0;
    bool queue_fault[7] = {false};
#ifdef KESTREL_TEST
    Injection injection = {0}, mode_pause = {0};
    uint64_t observation_deadline = 0;
#endif
    emit_event(c, 1, 0, 0, SAFE, &dropped);
#ifdef KESTREL_TEST
    /* Deterministic overflow fixture: Mode outranks Telemetry, so the bounded
     * event queue must overflow before the consumer can drain it. */
    if (c->event_burst) for (unsigned i = 0; i < 80; ++i) emit_event(c, 2, 2, 7, 0, &dropped);
#endif
    for (;;) {
#ifdef KESTREL_TEST
        if (!ready(c, 3, &mode_pause)) continue;
#else
        checkin(c, 3);
#endif
        uint64_t now = elapsed(c);
        uint32_t previous_revision = state.revision;
        Sample sample;
        if (xQueueReceive(c->samples, &sample, 0) == pdPASS) {
            state.sample = sample;
            if (sample.valid) last_valid = sample.at;
        }
        (void)xQueueReceive(c->health, &health, 0);
        bool overflow = uxQueueSpacesAvailable(c->events) == 0;
        for (unsigned i = 1; i <= 6; ++i) {
            (void)xQueueReceive(c->congestion[i], &queue_fault[i], 0);
            overflow = overflow || queue_fault[i];
        }
        bool fresh = state.sample.valid && now - state.sample.at < 500;
        uint32_t faults = kestrel_sensor_faults(state.faults, state.sample.valid,
            state.sample.battery, state.sample.temperature, now - last_valid >= 500);
        if (overflow) faults |= 1u << 7;
        for (unsigned code = 1; code <= 7; ++code) {
            if (code == 6) continue;
            bool before = (state.faults & (1u << code)) != 0, after = (faults & (1u << code)) != 0;
            if (before != after) {
                emit_event(c, after ? 2 : 3, after ? (code == 1 ? 1 : 2) : 0, code,
                           code == 7 ? 0 : 5, &dropped);
                if (after) state.last_fault = (uint16_t)code;
            }
        }
        for (unsigned id = 1; id <= 6; ++id) {
            bool before = (state.stalled & (1u << id)) != 0, after = (health.stalled & (1u << id)) != 0;
            if (before != after) {
                emit_event(c, after ? 2 : 3, after ? 2 : 0, 6, id, &dropped);
                if (after) state.last_fault = 6;
            }
        }
        state.faults = faults; state.stalled = health.stalled;
        bool critical = (faults & ~((uint32_t)1u << 1)) != 0 || health.stalled != 0;
        uint8_t automatic = kestrel_automatic_mode(state.mode, fresh, state.sample.battery, critical);
        transition(c, &state, automatic, &dropped);
        ModeRequest request;
        bool have_request = xQueueReceive(c->requests, &request, pdMS_TO_TICKS(1)) == pdPASS;
        ModeReply reply = {.status = KESTREL_OK};
        if (have_request) {
            if (request.function == 5) {
#ifdef KESTREL_TEST
                if (state.mode == SAFE) reply.status = MODE_DENIED;
                else if (now < injection.end) reply.status = BUSY;
                else {
                    injection = (Injection){.id = (uint8_t)request.argument, .start = now + 100, .end = now + 5100};
                    unsigned target = request.argument == 3 ? 4 : request.argument == 4 ? 5 : request.argument;
                    if (request.argument >= 5) target = request.argument == 10 ? 3 : 5;
                    configASSERT(xQueueOverwrite(c->injections[target], &injection) == pdPASS);
                }
#else
                reply.status = UNKNOWN_FUNCTION;
#endif
            } else if (request.function == 1) {
                if (request.argument == NOMINAL && !kestrel_can_enter_nominal(state.mode, fresh, state.sample.battery, critical))
                    reply.status = MODE_DENIED;
                else transition(c, &state, (uint8_t)request.argument, &dropped);
            } else if (request.function == 3) {
                if (state.mode == SAFE) reply.status = MODE_DENIED;
                else { state.period = request.argument; ++state.revision; }
            }
        }
        state.dropped_events = dropped;
        configASSERT(xQueueOverwrite(c->state, &state) == pdPASS);
        if (have_request) configASSERT(xQueueSend(c->replies, &reply, 0) == pdPASS);
#ifdef KESTREL_TEST
        if (now >= observation_deadline || state.revision != previous_revision || have_request) {
            observe(c, &state, &health, &injection, dropped);
            observation_deadline = now + 100;
        }
#else
        (void)previous_revision;
#endif
        /* Input queue wait above supplies the idle yield; pending work runs immediately. */
    }
}

