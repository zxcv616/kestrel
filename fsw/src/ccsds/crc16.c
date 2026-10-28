#include "kestrel_packet.h"

uint16_t kestrel_crc16(const uint8_t *data, size_t length)
{
    uint16_t crc = UINT16_C(0xffff);
    for (size_t i = 0; i < length; ++i) {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (unsigned bit = 0; bit < 8; ++bit) {
            crc = (uint16_t)((crc & UINT16_C(0x8000)) != 0
                  ? ((uint32_t)crc << 1) ^ UINT32_C(0x1021) : (uint32_t)crc << 1);
        }
    }
    return crc;
}
