#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"

enum { MESSAGE_COUNT = 20, PERIOD_MS = 20, QUEUE_LENGTH = 4 };

/* Values are copied into the queue; no task shares mutable application state. */
typedef struct {
    uint32_t sequence;
    uint32_t value;
    TickType_t sent_at;
} DemoMessage;

static void producer(void *argument)
{
    QueueHandle_t queue = (QueueHandle_t)argument;
    TickType_t wake = xTaskGetTickCount();

    for (uint32_t sequence = 1; sequence <= MESSAGE_COUNT; ++sequence) {
        (void)xTaskDelayUntil(&wake, pdMS_TO_TICKS(PERIOD_MS));
        const DemoMessage message = {
            .sequence = sequence,
            .value = sequence * sequence,
            .sent_at = xTaskGetTickCount(),
        };
        configASSERT(xQueueSend(queue, &message, pdMS_TO_TICKS(100)) == pdPASS);
    }
    for (;;) {
        vTaskSuspend(NULL);
    }
}

static void consumer(void *argument)
{
    QueueHandle_t queue = (QueueHandle_t)argument;
    TickType_t first_tick = 0;
    TickType_t last_tick = 0;
    uint32_t checksum = 0;

    for (uint32_t expected = 1; expected <= MESSAGE_COUNT; ++expected) {
        DemoMessage message;
        configASSERT(xQueueReceive(queue, &message, pdMS_TO_TICKS(1000)) == pdPASS);
        configASSERT(message.sequence == expected);
        configASSERT(message.value == expected * expected);
        configASSERT(message.sent_at >= last_tick);
        if (expected == 1) {
            first_tick = message.sent_at;
        }
        last_tick = message.sent_at;
        checksum += message.value;
    }
    configASSERT(last_tick > first_tick);
    /* Only this task uses stdio while the POSIX scheduler is active. */
    printf("{\"milestone\":\"M0\",\"messages\":%u,\"checksum\":%" PRIu32
           ",\"elapsed_ticks\":%lu,\"result\":\"pass\"}\n",
           (unsigned)MESSAGE_COUNT, checksum, (unsigned long)(last_tick - first_tick));
    configASSERT(fflush(stdout) == 0);
    vTaskEndScheduler();
    abort(); /* A FreeRTOS task must never return. */
}

int main(void)
{
    static StaticQueue_t queue_control;
    static uint8_t queue_storage[QUEUE_LENGTH * sizeof(DemoMessage)];
    static StaticTask_t producer_control;
    static StaticTask_t consumer_control;
    static StackType_t producer_stack[configMINIMAL_STACK_SIZE];
    static StackType_t consumer_stack[configMINIMAL_STACK_SIZE];

    QueueHandle_t queue = xQueueCreateStatic(QUEUE_LENGTH, sizeof(DemoMessage),
                                            queue_storage, &queue_control);
    configASSERT(queue != NULL);
    configASSERT(xTaskCreateStatic(producer, "producer", configMINIMAL_STACK_SIZE,
                                  queue, 1, producer_stack, &producer_control) != NULL);
    configASSERT(xTaskCreateStatic(consumer, "consumer", configMINIMAL_STACK_SIZE,
                                  queue, 2, consumer_stack, &consumer_control) != NULL);
    vTaskStartScheduler();
    return EXIT_SUCCESS;
}
