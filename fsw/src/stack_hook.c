#include "FreeRTOS.h"
#include "task.h"
#include <stdlib.h>
/* Fail closed; phase 2 replaces host termination with hardware reset. */
void vApplicationStackOverflowHook(TaskHandle_t task, char *name)
{
    (void)task; (void)name; abort();
}
