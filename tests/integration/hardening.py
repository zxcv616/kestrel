"""Real UDP regression checks for task health, overflow and stale ATT suppression."""
import sys
import socket
import subprocess
import time
from pathlib import Path
from flight_link import free_port
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.flight_control import FlightController
from ground.ccsds import decode, encode, Packet

binary=Path(sys.argv[1])
def wait(c, predicate, timeout=8):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        s=c.snapshot()
        if predicate(s): return s
        time.sleep(.01)
    raise AssertionError({'observation':c.snapshot().get('observation'), 'hk':c.snapshot().get('hk')})
def command(c,name,arg=0):
    result=c.command(name,arg)
    assert result['status']=='OK',result

def health():
    c=FlightController(binary,free_port(),free_port())
    try:
        c.start(test_build=True)
        wait(c,lambda s:s['observation'] and s['observation']['sensorValid'])
        command(c,'set_mode',2)
        s=wait(c,lambda s:s['hk']['packet']['fields']['mode']==2 and
               all(0<s['hk']['packet']['fields']['stack_'+n]<65535 for n in
                   ('link','command','mode','telemetry','sensors','watchdog')))
        assert s['hk']['packet']['fields']['dropped_events']==0
        command(c,'inject_fault',10)
        # Telemetry receives watchdog health directly, even while Mode cannot publish.
        s=wait(c,lambda s:bool(s['hk']['packet']['fields']['task_stalled_mask'] & (1<<3)),4.2)
        print('Mode stall visible in received HK; all six stack marks present')
        wait(c,lambda s:s['observationAgeSeconds']<.5 and not s['observation']['stalledMask'])
        sequence=c.snapshot()['hk']['packet']['sequence']
        command(c,'request_hk')
        wait(c,lambda s:s['hk']['packet']['sequence']!=sequence and not s['hk']['packet']['fields']['task_stalled_mask'])
    finally:c.stop()

def overflow():
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as rx:
        rx.bind(('127.0.0.1',0));rx.settimeout(2)
        port=free_port()
        p=subprocess.Popen([str(binary.with_name('kestrel_flight_test')),'--flight-port',str(port),
            '--ground-port',str(rx.getsockname()[1]),'--event-burst','1'])
        try:
            rx.recv(1024)
            time.sleep(.05)
            rx.sendto(encode(Packet(256,0,0,{'function':4,'argument':0})), ('127.0.0.1',port))
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                packet=decode(rx.recv(1024))
                if packet.apid==16 and packet.fields['dropped_events']>0:
                    assert packet.fields['mode']==1
                    print('Overflow reported in HK:',packet.fields['dropped_events']);return
            raise AssertionError('No dropped-event HK')
        finally:p.terminate();p.wait(timeout=3)

def stale_att():
    c=FlightController(binary,free_port(),free_port())
    try:
        c.start(test_build=True)
        wait(c,lambda s:s['observation'] and s['observation']['sensorValid'])
        command(c,'set_mode',2)
        wait(c,lambda s:any(e['label']=='ATT' for e in s['events']))
        command(c,'inject_fault',1)
        s=wait(c,lambda s:s['observation']['mode']==1)
        cutoff=max(e['id'] for e in s['events'])
        end=s['observation']['injectionEndMs']
        s=wait(c,lambda s:s['observation']['timeMs']>end+500)
        assert not any(e['label']=='ATT' and e['id']>cutoff for e in s['events'])
        print('Queued ATT discarded across Link outage and SAFE transition')
    finally:c.stop()

{'health':health,'overflow':overflow,'att':stale_att}[sys.argv[2]]()
