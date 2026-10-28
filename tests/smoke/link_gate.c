#define _POSIX_C_SOURCE 200809L
#include "kestrel_runtime.h"
#include "kestrel_link.h"
/* Test fixture state only: the fake transport deliberately returns backpressure. */
static Context context;
static unsigned phase, attempts, delivered_att, delivered_hk;
int kestrel_link_open(uint16_t a, uint16_t b) { (void)a; (void)b; return 1; }
void kestrel_link_close(void) {}
int kestrel_link_receive(uint8_t *b, size_t c, size_t *n) { (void)b;(void)c;(void)n;return 0; }
int kestrel_link_send(const uint8_t *bytes, size_t n)
{
    (void)n;
    if (bytes[1] == KESTREL_APID_ATT) {
        if (!phase) { ++attempts; return 0; }
        configASSERT(phase == 3);
        ++delivered_att;
    } else ++delivered_hk;
    return 1;
}
static void drive(void *arg)
{
    (void)arg;
    ModeGate gate = {.mode=NOMINAL,.epoch=1};
    Datagram att = {.mode_epoch=1,.length=2,.bytes={8,KESTREL_APID_ATT}};
    Datagram hk = {.length=2,.bytes={8,KESTREL_APID_HK}};
    xQueueOverwrite(context.link_mode,&gate);
    xQueueSend(context.periodic,&att,0);
    xQueueSend(context.periodic,&hk,0);
    vTaskDelay(pdMS_TO_TICKS(20));
    configASSERT(attempts > 0); /* Link has retained an unsent ATT. */
    phase=1;gate.mode=SAFE;gate.epoch=2;xQueueOverwrite(context.link_mode,&gate);
    vTaskDelay(pdMS_TO_TICKS(20));
    configASSERT(delivered_att==0 && delivered_hk==1);
    /* A rapid return to NOMINAL still must not release the old epoch. */
    phase=2;gate.mode=NOMINAL;gate.epoch=3;xQueueOverwrite(context.link_mode,&gate);
    xQueueSend(context.periodic,&att,0);
    vTaskDelay(pdMS_TO_TICKS(20));
    configASSERT(delivered_att==0);
    phase=3;att.mode_epoch=3;xQueueSend(context.periodic,&att,0);
    vTaskDelay(pdMS_TO_TICKS(20));
    configASSERT(delivered_att==1);
    vTaskEndScheduler();
    for (;;) {}
}
int main(void)
{
    clock_gettime(CLOCK_MONOTONIC,&context.epoch);
#define Q(field,count,type) do { static StaticQueue_t q; static uint8_t s[(count)*sizeof(type)]; context.field=xQueueCreateStatic(count,sizeof(type),s,&q); } while(0)
    Q(incoming,32,Datagram);Q(outgoing,32,Datagram);Q(periodic,2,Datagram);
    Q(link_mode,1,ModeGate);Q(checkins[1],1,Checkin);
    static StaticTask_t t[2];static StackType_t stacks[2][configMINIMAL_STACK_SIZE];
    configASSERT(xTaskCreateStatic(link_task,"Link",configMINIMAL_STACK_SIZE,&context,3,stacks[0],&t[0]));
    configASSERT(xTaskCreateStatic(drive,"Fixture",configMINIMAL_STACK_SIZE,NULL,4,stacks[1],&t[1]));
    vTaskStartScheduler();return 0;
}
