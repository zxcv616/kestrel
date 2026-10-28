#include "kestrel_runtime.h"
/* FreeRTOS TaskFunction_t requires void *, even though Context is immutable. */
// cppcheck-suppress constParameterPointer
void watchdog_task(void *argument)
{
    const Context *c = argument;
    Health health = {0};
    for (unsigned i = 1; i <= 6; ++i) health.stack_free[i] = UINT16_MAX;
    uint64_t deadline = 1000;
    for (;;) {
        checkin(c, 6);
        uint64_t now = elapsed(c);
        for (unsigned i = 1; i <= 6; ++i) {
            Checkin stamp;
            if (xQueueReceive(c->checkins[i], &stamp, 0) == pdPASS) {
                health.last[i] = stamp.at;
                health.stack_free[i] = stamp.stack_free;
                health.stalled &= ~(1u << i);
                health.misses[i] = 0;
            }
        }
        if (now >= deadline) {
            for (unsigned i = 1; i <= 6; ++i) {
                if (now - health.last[i] > 500) {
                    if (health.misses[i] < 3) ++health.misses[i];
                    if (health.misses[i] == 3) health.stalled |= 1u << i;
                } else health.misses[i] = 0;
            }
            deadline += 1000;
            if (deadline <= now) deadline = now + 1000;
        }
        configASSERT(xQueueOverwrite(c->health, &health) == pdPASS);
        configASSERT(xQueueOverwrite(c->telemetry_health, &health) == pdPASS);
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
