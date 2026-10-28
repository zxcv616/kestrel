#include "kestrel_runtime.h"
/* FreeRTOS TaskFunction_t requires void *, even though Context is immutable. */
// cppcheck-suppress constParameterPointer
void sensor_task(void *argument)
{
    const Context *c = argument;
    Injection injection = {0};
    uint64_t deadline = 0;
    for (;;) {
#ifdef KESTREL_TEST
        Injection update;
        if (xQueueReceive(c->injections[5], &update, 0) == pdPASS) injection = update;
        uint64_t now = elapsed(c);
        bool injected = now >= injection.start && now < injection.end;
        if (injected && injection.id == 4) { vTaskDelay(pdMS_TO_TICKS(10)); continue; }
#else
        (void)injection;
#endif
        checkin(c, 5);
        if (elapsed(c) >= deadline) {
            Sample sample = {.at = elapsed(c), .valid = true, .battery = 80, .temperature = 2000};
#ifdef KESTREL_TEST
            if (injected) {
                if (injection.id == 5) sample.battery = 15;
                if (injection.id == 6) sample.battery = 5;
                if (injection.id == 7) sample.temperature = 6100;
                if (injection.id == 8) sample.temperature = -2100;
                if (injection.id == 9) sample.valid = false;
            }
#endif
            configASSERT(xQueueOverwrite(c->samples, &sample) == pdPASS);
            deadline = elapsed(c) + 100;
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
