"""M4 uses real tasks, real UDP, and a separate nonblocking Mode observation pipe."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.flight_control import FlightController
from flight_link import free_port
from ground.ccsds import decode


def wait(controller, predicate, timeout=7):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        snap=controller.snapshot()
        if predicate(snap):return snap
        time.sleep(.01)
    raise AssertionError(('timeout', controller.snapshot().get('observation')))


def command(c, name, argument=0, status='OK'):
    result=c.command(name,argument)
    assert result['status']==status, result
    return result


def scenario(binary, injection_id, event_check=False):
    c=FlightController(Path(binary).with_name('kestrel_flight'),free_port(),free_port())
    c.test_binary=Path(binary)
    try:
        c.start(test_build=True)
        wait(c,lambda s:s['observation'] and s['observation']['sensorValid'])
        command(c,'inject_fault',injection_id,'MODE_DENIED')
        command(c,'set_mode',2)
        wait(c,lambda s:s['observation']['mode']==2)
        command(c,'inject_fault',injection_id)
        # Before activation all paths are operational; ownership blocks a second injection.
        command(c,'inject_fault',5,'BUSY')
        armed=wait(c,lambda s:s['observation']['injection']==injection_id)['observation']
        start,end=armed['injectionStartMs'],armed['injectionEndMs']
        assert end-start==5000
        target=3 if injection_id==5 else 1
        changed=wait(c,lambda s:s['observation']['mode']==target)['observation']
        delay=changed['changedAtMs']-start
        limit=4000 if injection_id<=3 else 1000
        assert 0<=delay<=limit,(injection_id,delay)
        if injection_id in (6,7,8,9):command(c,'set_mode',2,'MODE_DENIED')
        if injection_id==5:command(c,'set_mode',2,'MODE_DENIED')
        if injection_id<=4:
            task={1:1,2:2,3:4,4:5}[injection_id]
            stalled=wait(c,lambda s:bool(s['observation']['stalledMask']&(1<<task)))['observation']
            assert stalled['misses'][task-1]==3, stalled
            assert stalled['timeMs']-start<=4000, stalled
            # Observe health without relying on a working UDP telemetry path.
            assert stalled['mode']==1
        cleared=wait(c,lambda s:s['observation']['timeMs']>=end+200 and
            not s['observation']['faultMask'] and not s['observation']['stalledMask'])
        final=cleared['observation']
        assert final['droppedEvents']==0
        assert final['sensorValid'] and final['battery']==80 and final['temperature']==2000
        assert final['mode']==(2 if injection_id==5 else 1), final
        records=cleared['modeEvents']
        # Backlogged events must arrive after link/telemetry resumes.
        expected_fault={1:6,2:6,3:6,4:5,5:1,6:2,7:3,8:4,9:5}[injection_id]
        seen=wait(c,lambda s:any(e['packet']['fields']['id']==3 and
            e['packet']['fields']['parameter_1']==expected_fault for e in s['modeEvents']))
        fields=[e['packet']['fields'] for e in seen['modeEvents']]
        for event_id in (2,3):
            matches=[e for e in fields if e['id']==event_id and e['parameter_1']==expected_fault]
            assert len(matches)==1,(injection_id,event_id,matches)
        transitions=[e['packet'] for e in seen['modeEvents'] if e['packet']['fields']['id']==1]
        entered=[e for e in transitions if e['fields']['parameter_1']==2 and e['fields']['parameter_2']==target]
        assert len(entered)==1
        assert entered[0]['time_ms']==changed['changedAtMs'], (entered,changed)
        previous_hk=seen['hk']['packet']['sequence']
        command(c,'reset_counters')
        command(c,'request_hk')
        snap=wait(c,lambda s:s['hk']['packet']['sequence']>previous_hk and s['hk']['packet']['fields']['accepted']==2)
        assert snap['hk']['packet']['fields']['last_fault']!=0
        assert snap['hk']['packet']['fields']['battery_percent']==80
        if injection_id!=5:
            command(c,'set_mode',2)
            wait(c,lambda s:s['observation']['mode']==2)
        if event_check:
            command(c,'inject_fault',injection_id)
            repeated=wait(c,lambda s:len([e for e in s['modeEvents'] if
                e['packet']['fields']['id']==2 and e['packet']['fields']['parameter_1']==expected_fault])==2)
            assert repeated['observation']['mode']==1
            wait(c,lambda s:len([e for e in s['modeEvents'] if
                e['packet']['fields']['id']==3 and e['packet']['fields']['parameter_1']==expected_fault])==2)
        for row in seen['events']:
            assert decode(bytes.fromhex(row['hex']))
        print(json.dumps({'injection':injection_id,'mode':target,'transitionDelayMs':delay,
                          'expiryMs':end-start,'events':len(records),'observerDroppedEvents':final['droppedEvents']}))
    finally:c.stop()


def run(binary,suite):
    ids={'battery':[5], 'critical':[6,7,8,9], 'watchdog':[1,2,3,4], 'events':[7]}
    for injection in ids[suite]:scenario(binary,injection,suite=='events')

if __name__=='__main__':run(sys.argv[1],sys.argv[2])
