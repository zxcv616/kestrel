#include "unity.h"
#include "kestrel_packet.h"
#include <string.h>
#include "packet_vectors.h"
#define COUNT(a) (sizeof(a) / sizeof((a)[0]))
void setUp(void) {}
void tearDown(void) {}

static void same_fields(const KestrelPacket *expected, const KestrelPacket *actual)
{
    TEST_ASSERT_EQUAL_UINT16(expected->apid, actual->apid);
    TEST_ASSERT_EQUAL_UINT16(expected->sequence, actual->sequence);
    TEST_ASSERT_EQUAL_UINT32(expected->time_ms, actual->time_ms);
#define SAME(member) TEST_ASSERT_EQUAL_INT64(expected->payload.member, actual->payload.member)
    switch (expected->apid) {
        case KESTREL_APID_HK:
            SAME(hk.mode); SAME(hk.uptime_s); SAME(hk.battery_mv); SAME(hk.battery_percent);
            SAME(hk.temperature_centi_c); SAME(hk.accepted); SAME(hk.rejected); SAME(hk.last_fault); SAME(hk.dropped_events); SAME(hk.task_stalled_mask);
            SAME(hk.stack_link); SAME(hk.stack_command); SAME(hk.stack_mode); SAME(hk.stack_telemetry); SAME(hk.stack_sensors); SAME(hk.stack_watchdog); break;
        case KESTREL_APID_ATT: SAME(att.x); SAME(att.y); SAME(att.z); break;
        case KESTREL_APID_EVENT: SAME(event.id); SAME(event.severity); SAME(event.parameter_1); SAME(event.parameter_2); break;
        case KESTREL_APID_ACK: SAME(ack.command_sequence); SAME(ack.status); break;
        case KESTREL_APID_CMD: SAME(command.function); SAME(command.argument); break;
        default: TEST_FAIL_MESSAGE("Unexpected fixture APID");
    }
#undef SAME
}
static void test_crc_reference(void)
{
    TEST_ASSERT_EQUAL_HEX16(0x29b1, kestrel_crc16((const uint8_t *)"123456789", 9));
    TEST_ASSERT_EQUAL_HEX16(0xffff, kestrel_crc16(NULL, 0));
}
static void test_shared_valid_vectors(void)
{
    for (size_t i = 0; i < COUNT(valid_vectors); ++i) {
        const ValidVector *v = &valid_vectors[i];
        uint8_t output[256] = {0}; size_t written = 0; KestrelPacket decoded;
        TEST_ASSERT_EQUAL_MESSAGE(KESTREL_OK, kestrel_packet_encode(&v->packet, output, sizeof(output), &written), v->name);
        TEST_ASSERT_EQUAL(v->length, written);
        TEST_ASSERT_EQUAL_UINT8_ARRAY(v->wire, output, written);
        TEST_ASSERT_EQUAL_MESSAGE(KESTREL_OK, kestrel_packet_decode(v->wire, v->length, &decoded), v->name);
        same_fields(&v->packet, &decoded);
    }
}
static void test_shared_invalid_vectors(void)
{
    for (size_t i = 0; i < COUNT(invalid_vectors); ++i) {
        const InvalidVector *v = &invalid_vectors[i];
        KestrelPacket decoded; memset(&decoded, 0xa5, sizeof(decoded));
        uint8_t before[sizeof(decoded)]; memcpy(before, &decoded, sizeof(decoded));
        TEST_ASSERT_EQUAL_MESSAGE(v->expected, kestrel_packet_decode(v->wire, v->length, &decoded), v->name);
        TEST_ASSERT_EQUAL_MEMORY(before, &decoded, sizeof(decoded));
    }
}
static void test_output_bounds_and_arguments(void)
{
    uint8_t output[64]; memset(output, 0xa5, sizeof(output));
    uint8_t before[64]; memcpy(before, output, sizeof(output));
    size_t written = 999;
    TEST_ASSERT_EQUAL(KESTREL_BAD_LENGTH, kestrel_packet_encode(&valid_vectors[0].packet, output, 31, &written));
    TEST_ASSERT_EQUAL_UINT8_ARRAY(before, output, sizeof(output));
    TEST_ASSERT_EQUAL(999, written);
    TEST_ASSERT_EQUAL(KESTREL_BAD_ARGUMENT, kestrel_packet_encode(NULL, output, sizeof(output), &written));
    KestrelPacket p = valid_vectors[0].packet; p.sequence = 16384;
    TEST_ASSERT_EQUAL(KESTREL_BAD_ARGUMENT, kestrel_packet_encode(&p, output, sizeof(output), &written));
    p.apid = 2047;
    TEST_ASSERT_EQUAL(KESTREL_UNKNOWN_APID, kestrel_packet_encode(&p, output, sizeof(output), &written));
    TEST_ASSERT_EQUAL(KESTREL_BAD_ARGUMENT, kestrel_packet_decode(NULL, 0, &p));
    TEST_ASSERT_EQUAL(KESTREL_BAD_ARGUMENT, kestrel_packet_decode(output, sizeof(output), NULL));
    for (size_t i = 0; i < COUNT(valid_vectors); ++i) {
        const ValidVector *v = &valid_vectors[i];
        TEST_ASSERT_EQUAL(KESTREL_OK, kestrel_packet_encode(&v->packet, output, v->length, &written));
        TEST_ASSERT_EQUAL_HEX8(0xa5, output[63]);
    }
}
static void test_all_apid_sequences(void)
{
    KestrelSequences state = {{0}};
    const uint16_t apids[] = {16,17,18,19,256};
    for (uint32_t n = 0; n < 16386; ++n) {
        for (size_t i = 0; i < COUNT(apids); ++i) {
            uint16_t result = 65535;
            TEST_ASSERT_EQUAL(KESTREL_OK, kestrel_sequence_take(&state, apids[i], &result));
            TEST_ASSERT_EQUAL_UINT16(n & 16383, result);
        }
    }
    uint16_t result = 65535;
    TEST_ASSERT_EQUAL(KESTREL_UNKNOWN_APID, kestrel_sequence_take(&state, 0, &result));
    TEST_ASSERT_EQUAL_UINT16(65535, result);
    TEST_ASSERT_EQUAL(KESTREL_OK, kestrel_sequence_take(&state, 16, &result));
    TEST_ASSERT_EQUAL_UINT16(2, result);
    TEST_ASSERT_EQUAL(KESTREL_OK, kestrel_sequence_take(&state, 17, &result));
    TEST_ASSERT_EQUAL_UINT16(2, result);
    TEST_ASSERT_EQUAL(KESTREL_OK, kestrel_sequence_take(&state, 16, &result));
    TEST_ASSERT_EQUAL_UINT16(3, result);
}
int main(int argc, char **argv)
{
    UNITY_BEGIN();
    if (argc == 2 && strcmp(argv[1], "sequences") == 0) {
        RUN_TEST(test_all_apid_sequences);
    } else {
        RUN_TEST(test_crc_reference);
        RUN_TEST(test_shared_valid_vectors);
        RUN_TEST(test_shared_invalid_vectors);
        RUN_TEST(test_output_bounds_and_arguments);
    }
    return UNITY_END();
}
