#include "unity.h"
#include "kestrel_mode.h"
void setUp(void) {}
void tearDown(void) {}
static void prerequisites(void)
{
    TEST_ASSERT_TRUE(kestrel_can_enter_nominal(1, true, 20, false));
    TEST_ASSERT_FALSE(kestrel_can_enter_nominal(1, true, 19, false));
    TEST_ASSERT_FALSE(kestrel_can_enter_nominal(1, false, 80, false));
    TEST_ASSERT_FALSE(kestrel_can_enter_nominal(1, true, 80, true));
    TEST_ASSERT_FALSE(kestrel_can_enter_nominal(3, true, 80, false));
    TEST_ASSERT_FALSE(kestrel_can_enter_nominal(0, true, 80, false));
    TEST_ASSERT_TRUE(kestrel_can_enter_nominal(2, true, 80, false));
}
static void thresholds(void)
{
    TEST_ASSERT_EQUAL(2, kestrel_automatic_mode(2, true, 20, false));
    TEST_ASSERT_EQUAL(3, kestrel_automatic_mode(2, true, 19, false));
    TEST_ASSERT_EQUAL(3, kestrel_automatic_mode(3, true, 29, false));
    TEST_ASSERT_EQUAL(2, kestrel_automatic_mode(3, true, 30, false));
    TEST_ASSERT_EQUAL(1, kestrel_automatic_mode(1, true, 80, false));
    TEST_ASSERT_EQUAL(1, kestrel_automatic_mode(3, true, 80, true));
    TEST_ASSERT_EQUAL(0, kestrel_sensor_faults(0, true, 20, -2000, false));
    TEST_ASSERT_EQUAL(0, kestrel_sensor_faults(0, true, 20, 6000, false));
    TEST_ASSERT_EQUAL(1u<<1, kestrel_sensor_faults(0, true, 10, 2000, false));
    TEST_ASSERT_EQUAL((1u<<1)|(1u<<2), kestrel_sensor_faults(0, true, 9, 2000, false));
    TEST_ASSERT_EQUAL(1u<<1, kestrel_sensor_faults(1u<<1, true, 29, 2000, false));
    TEST_ASSERT_EQUAL(0, kestrel_sensor_faults(1u<<1, true, 30, 2000, false));
    TEST_ASSERT_EQUAL(1u<<3, kestrel_sensor_faults(0, true, 80, 6001, false));
    TEST_ASSERT_EQUAL(1u<<4, kestrel_sensor_faults(0, true, 80, -2001, false));
    TEST_ASSERT_EQUAL(1u<<5, kestrel_sensor_faults(0, false, 80, 2000, true));
    TEST_ASSERT_FALSE(kestrel_can_enter_nominal(2, true, 80, true));
}
int main(void) { UNITY_BEGIN(); RUN_TEST(prerequisites); RUN_TEST(thresholds); return UNITY_END(); }
