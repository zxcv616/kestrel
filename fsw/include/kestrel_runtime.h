#ifndef KESTREL_RUNTIME_H
#define KESTREL_RUNTIME_H
#define _POSIX_C_SOURCE 200809L
#include <stdbool.h>
#include <stdint.h>
#include <time.h>
#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"
#include "kestrel_packet.h"
#include "kestrel_mode.h"
enum { DEPTH = 32, BATCH = 8, SAFE = 1, NOMINAL = 2, LOW_POWER = 3,
       MODE_DENIED = 7, UNKNOWN_FUNCTION = 5, BUSY = 8 };
typedef struct { uint32_t mode_epoch; size_t length; uint8_t bytes[KESTREL_MAX_PACKET + 1]; } Datagram;
typedef struct { uint16_t echo; uint8_t status; bool request_hk;
                 uint32_t accepted, rejected; } Decision;
typedef struct { uint8_t mode; uint32_t epoch; } ModeGate;
typedef struct { uint8_t function; uint16_t argument; } ModeRequest;
typedef struct { uint8_t status; } ModeReply;
typedef struct { uint8_t id; uint64_t start, end; } Injection;
typedef struct { uint64_t at; bool valid; uint8_t battery; int16_t temperature; } Sample;
typedef struct { uint64_t at; uint16_t stack_free; } Checkin;
typedef struct { uint16_t stack_free[7]; uint8_t misses[7]; uint64_t last[7]; uint32_t stalled; } Health;
typedef struct {
    uint8_t mode; uint16_t period, last_fault; uint32_t faults, stalled, revision, mode_epoch;
    uint64_t changed_at; Sample sample; uint32_t dropped_events;
} State;
typedef struct { uint16_t id; uint8_t severity; int32_t a, b; uint32_t at; } Event;
typedef struct {
    QueueHandle_t requests, replies, incoming, decisions, outgoing, periodic;
    QueueHandle_t samples, state, health, events, link_mode, telemetry_health;
    QueueHandle_t checkins[7], injections[7], congestion[7];
    uint16_t flight_port, ground_port;
    struct timespec epoch;
#ifdef KESTREL_TEST
    bool observe, event_burst;
#endif
} Context;
uint64_t elapsed(const Context *c);
void checkin(const Context *c, unsigned id);
void congestion(const Context *c, unsigned id, bool active);
bool ready(const Context *c, unsigned id, Injection *injection);
void link_task(void *argument);
void command_task(void *argument);
void mode_task(void *argument);
void telemetry_task(void *argument);
void sensor_task(void *argument);
void watchdog_task(void *argument);
#endif
