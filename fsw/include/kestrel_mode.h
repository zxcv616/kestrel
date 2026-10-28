#ifndef KESTREL_MODE_H
#define KESTREL_MODE_H
#include <stdbool.h>
#include <stdint.h>
static inline bool kestrel_can_enter_nominal(uint8_t mode, bool fresh,
                                            uint8_t battery_percent, bool critical)
{
    return !critical && fresh && (mode == 2 || (mode == 1 && battery_percent >= 20));
}
static inline uint8_t kestrel_automatic_mode(uint8_t mode, bool fresh,
                                           uint8_t battery, bool critical)
{
    if (critical) return 1;
    if (fresh && mode == 2 && battery < 20) return 3;
    if (fresh && mode == 3 && battery >= 30) return 2;
    return mode;
}
static inline uint32_t kestrel_sensor_faults(uint32_t previous, bool valid,
                                           uint8_t battery, int16_t temperature, bool dropout)
{
    uint32_t faults = previous & ((1u<<1) | (1u<<2) | (1u<<3) | (1u<<4));
    if (valid) {
        bool low = battery < 20 || ((previous & (1u<<1)) && battery < 30);
        faults = (low ? 1u<<1 : 0) | (battery < 10 ? 1u<<2 : 0)
            | (temperature > 6000 ? 1u<<3 : 0) | (temperature < -2000 ? 1u<<4 : 0);
    }
    if (dropout) faults |= 1u<<5;
    return faults;
}
#endif
