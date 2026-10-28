#ifndef KESTREL_FREERTOS_CONFIG_H
#define KESTREL_FREERTOS_CONFIG_H

#include <stdlib.h>

#define configUSE_PREEMPTION                     1
#define configUSE_TIME_SLICING                   1
#define configCPU_CLOCK_HZ                      100000000UL
#define configTICK_RATE_HZ                       1000U
#define configMAX_PRIORITIES                     5U
#define configMINIMAL_STACK_SIZE                4096U
#define configMAX_TASK_NAME_LEN                 16U
#define configTICK_TYPE_WIDTH_IN_BITS           TICK_TYPE_WIDTH_64_BITS
#define configIDLE_SHOULD_YIELD                  1
#define configUSE_IDLE_HOOK                     0
#define configUSE_TICK_HOOK                     0
#define configUSE_TIMERS                        0
#define configUSE_MUTEXES                       0
#define configUSE_RECURSIVE_MUTEXES             0
#define configUSE_COUNTING_SEMAPHORES           0
/* Required by the upstream stream-buffer compilation unit; app IPC uses queues. */
#define configUSE_TASK_NOTIFICATIONS            1
#define configSUPPORT_STATIC_ALLOCATION         1
#define configSUPPORT_DYNAMIC_ALLOCATION        0
#define configKERNEL_PROVIDED_STATIC_MEMORY      1
#define configCHECK_FOR_STACK_OVERFLOW           2
#define INCLUDE_uxTaskGetStackHighWaterMark       1
#define INCLUDE_vTaskDelay                      1
#define INCLUDE_xTaskDelayUntil                 1
#define INCLUDE_vTaskSuspend                    1
#define INCLUDE_xTaskGetCurrentTaskHandle       1

/* Unlike assert(), this remains active in Release builds. */
#define configASSERT(condition) do { if (!(condition)) { abort(); } } while (0)

#endif
