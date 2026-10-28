#include "kestrel_runtime.h"
uint64_t elapsed(const Context *c)
{
    struct timespec now;
    configASSERT(clock_gettime(CLOCK_MONOTONIC, &now) == 0);
    return (uint64_t)((now.tv_sec - c->epoch.tv_sec) * INT64_C(1000)
                     + (now.tv_nsec - c->epoch.tv_nsec) / INT64_C(1000000));
}
void checkin(const Context *c, unsigned id)
{
    Checkin stamp = {.at = elapsed(c), .stack_free = (uint16_t)uxTaskGetStackHighWaterMark(NULL)};
    configASSERT(xQueueOverwrite(c->checkins[id], &stamp) == pdPASS);
}
void congestion(const Context *c, unsigned id, bool active)
{
    configASSERT(xQueueOverwrite(c->congestion[id], &active) == pdPASS);
}
bool ready(const Context *c, unsigned id, Injection *injection)
{
    (void)injection;
#ifdef KESTREL_TEST
    Injection update;
    if (xQueueReceive(c->injections[id], &update, 0) == pdPASS) *injection = update;
    uint64_t now = elapsed(c);
    if (injection->id && now >= injection->start && now < injection->end) {
        vTaskDelay(pdMS_TO_TICKS(10));
        return false;
    }
#endif
    checkin(c, id);
    return true;
}
