#include "kestrel_runtime.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
static uint16_t port_number(const char *value)
{
    char *end;
    long n = strtol(value, &end, 10);
    if (*value == '\0' || *end != '\0' || n < 1024 || n > 65535) {
        fprintf(stderr, "Ports must be integers from 1024 through 65535.\n"); exit(EXIT_FAILURE);
    }
    return (uint16_t)n;
}
int main(int argc, char **argv)
{
    static Context c;
    configASSERT(clock_gettime(CLOCK_MONOTONIC, &c.epoch) == 0);
    c.flight_port = 5000; c.ground_port = 5001;
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 == argc) return EXIT_FAILURE;
        if (strcmp(argv[i], "--flight-port") == 0) c.flight_port = port_number(argv[i + 1]);
        else if (strcmp(argv[i], "--ground-port") == 0) c.ground_port = port_number(argv[i + 1]);
#ifdef KESTREL_TEST
        else if (strcmp(argv[i], "--event-burst") == 0 && strcmp(argv[i + 1], "1") == 0) c.event_burst = true;
        else if (strcmp(argv[i], "--observe") == 0 && strcmp(argv[i + 1], "1") == 0) c.observe = true;
#endif
        else return EXIT_FAILURE;
    }
#ifdef KESTREL_TEST
    if (c.observe) configASSERT(fcntl(STDOUT_FILENO, F_SETFL, O_NONBLOCK) == 0);
#endif
    if (c.flight_port == c.ground_port) return EXIT_FAILURE;
    /* Macros declare distinct static storage for every queue. */
#define QUEUE(field, count, type) do { \
    static StaticQueue_t control; static uint8_t storage[(count) * sizeof(type)]; \
    c.field = xQueueCreateStatic(count, sizeof(type), storage, &control); \
    configASSERT(c.field); } while (0)
    QUEUE(incoming, DEPTH, Datagram); QUEUE(decisions, DEPTH, Decision);
    QUEUE(outgoing, DEPTH, Datagram); QUEUE(periodic, 2, Datagram);
    QUEUE(requests, 1, ModeRequest); QUEUE(replies, 1, ModeReply);
    QUEUE(samples, 1, Sample); QUEUE(state, 1, State); QUEUE(health, 1, Health);
    QUEUE(events, 64, Event);
    QUEUE(link_mode, 1, ModeGate); QUEUE(telemetry_health, 1, Health);
    static StaticQueue_t check_controls[7], injection_controls[7], congestion_controls[7];
    static uint8_t check_storage[7][sizeof(Checkin)], injection_storage[7][sizeof(Injection)];
    static uint8_t congestion_storage[7][sizeof(bool)];
    for (unsigned i = 1; i <= 6; ++i) {
        c.checkins[i] = xQueueCreateStatic(1, sizeof(Checkin), check_storage[i], &check_controls[i]);
        c.injections[i] = xQueueCreateStatic(1, sizeof(Injection), injection_storage[i], &injection_controls[i]);
        c.congestion[i] = xQueueCreateStatic(1, sizeof(bool), congestion_storage[i], &congestion_controls[i]);
        configASSERT(c.checkins[i] && c.injections[i] && c.congestion[i]);
    }
    static StaticTask_t tasks[6];
    static StackType_t stacks[6][configMINIMAL_STACK_SIZE];
    configASSERT(xTaskCreateStatic(link_task, "Link", configMINIMAL_STACK_SIZE, &c, 3, stacks[0], &tasks[0]));
    configASSERT(xTaskCreateStatic(command_task, "Command", configMINIMAL_STACK_SIZE, &c, 2, stacks[1], &tasks[1]));
    configASSERT(xTaskCreateStatic(telemetry_task, "Telemetry", configMINIMAL_STACK_SIZE, &c, 1, stacks[2], &tasks[2]));
    configASSERT(xTaskCreateStatic(mode_task, "Mode", configMINIMAL_STACK_SIZE, &c, 3, stacks[3], &tasks[3]));
    configASSERT(xTaskCreateStatic(sensor_task, "Sensors", configMINIMAL_STACK_SIZE, &c, 1, stacks[4], &tasks[4]));
    configASSERT(xTaskCreateStatic(watchdog_task, "Watchdog", configMINIMAL_STACK_SIZE, &c, 4, stacks[5], &tasks[5]));
    vTaskStartScheduler();
    return EXIT_FAILURE;
}
