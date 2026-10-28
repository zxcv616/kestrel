#ifndef KESTREL_LINK_H
#define KESTREL_LINK_H
#include <stddef.h>
#include <stdint.h>
/* Transport owns its handles. Tasks see only nonblocking packet operations.
 * Return 1 for success, 0 for retry/no data, -1 for permanent failure. */
int kestrel_link_open(uint16_t local_port, uint16_t ground_port);
int kestrel_link_send(const uint8_t *bytes, size_t length);
int kestrel_link_receive(uint8_t *bytes, size_t capacity, size_t *length);
void kestrel_link_close(void);
#endif
