#define _POSIX_C_SOURCE 200809L
#include "kestrel_link.h"
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <sys/socket.h>
#include <unistd.h>
/* Private to the Link task; never accessed by other flight tasks. */
static int socket_fd = -1;
static struct sockaddr_in destination;
static bool retryable(void)
{
    return errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR || errno == ENOBUFS;
}
int kestrel_link_open(uint16_t local_port, uint16_t ground_port)
{
    struct sockaddr_in local = {0};
    socket_fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (socket_fd < 0) return -1;
    if (fcntl(socket_fd, F_SETFL, O_NONBLOCK) < 0) { kestrel_link_close(); return -1; }
    local.sin_family = AF_INET;
    if (inet_pton(AF_INET, "127.0.0.1", &local.sin_addr) != 1) { kestrel_link_close(); return -1; }
    local.sin_port = htons(local_port);
    destination = local; destination.sin_port = htons(ground_port);
    /* No reuse: a second instance cannot steal the endpoint. */
    if (bind(socket_fd, (struct sockaddr *)&local, sizeof(local)) < 0) {
        kestrel_link_close(); return -1;
    }
    return 1;
}
int kestrel_link_send(const uint8_t *bytes, size_t length)
{
    ssize_t n = sendto(socket_fd, bytes, length, 0, (struct sockaddr *)&destination, sizeof(destination));
    if (n < 0) return retryable() ? 0 : -1;
    return (size_t)n == length ? 1 : -1;
}
int kestrel_link_receive(uint8_t *bytes, size_t capacity, size_t *length)
{
    ssize_t n = recvfrom(socket_fd, bytes, capacity, 0, NULL, NULL);
    if (n < 0) return retryable() ? 0 : -1;
    *length = (size_t)n;
    return 1;
}
void kestrel_link_close(void)
{
    if (socket_fd >= 0) { close(socket_fd); socket_fd = -1; }
}
