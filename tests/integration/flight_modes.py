"""M3 acceptance against the real flight binary, using host and packet clocks."""
import json
import socket
import sys
import time
from flight_link import Flight
from ground.ccsds import Packet, encode, crc16


def run(binary, suite):
    f = Flight(binary)
    sequence = 0
    seen = []
    def receive(timeout=1):
        packet=f.receive(timeout)
        seen.append((time.monotonic(),packet))
        return packet
    def cmd(function, argument=0, status=0, raw_argument=None):
        nonlocal sequence
        wire=encode(Packet(0x100,sequence,0,{'function':function,'argument':argument}))
        if raw_argument is not None:
            wire=wire[:11]+raw_argument.to_bytes(2,'big')+wire[-2:]
            wire=wire[:-2]+crc16(wire[:-2]).to_bytes(2,'big')
        f.send(wire)
        while True:
            p=receive()
            if p.apid==0x13:
                assert p.fields=={'command_sequence':sequence,'status':status}, p
                sequence+=1
                return p
    def hk():
        cmd(4)
        while True:
            p=receive()
            if p.apid==0x10:return p
    def collect(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            try:receive(max(.001,end-time.monotonic()))
            except socket.timeout:break
    def enter():
        cmd(1,2)
        while receive().apid!=0x10:pass
    try:
        if suite=='safe':
            cmd(0);assert hk().fields['mode']==1
            collect(.15)
            assert not any(p.apid==0x12 for _,p in seen)
            enter();assert seen[-1][1].fields['mode']==2
            cmd(1,2);collect(.15)
            assert len([p for _,p in seen if p.apid==0x12])==1
            cmd(1,1);assert hk().fields['mode']==1
            collect(.15)
            events=[p.fields for _,p in seen if p.apid==0x12]
            assert [(e['parameter_1'],e['parameter_2']) for e in events]==[(1,2),(2,1)]
        elif suite=='timing':
            enter();seen.clear();collect(4.2)
            hk_packets=[(t,p) for t,p in seen if p.apid==0x10]
            assert len(hk_packets)==4, hk_packets
            intervals=[(b[0]-a[0])*1000 for a,b in zip(hk_packets,hk_packets[1:])]
            assert all(abs(v-1000)<=50 for v in intervals), intervals
            print(json.dumps({'nominalHKHostIntervalsMs':intervals}))
        elif suite=='rate':
            cmd(3,250,7);enter()
            for period in (250,1000,10000):
                cmd(3,period);seen.clear();collect(period/1000+.12)
                packets=[p for _,p in seen if p.apid==0x10]
                assert len(packets)==1, (period,packets)
            for invalid in (0,249,10001,65535):cmd(3,250,6,invalid)
            cmd(3,250);seen.clear();collect(1.1)
            packets=[p for _,p in seen if p.apid==0x10]
            assert len(packets)==4
            assert all(abs(b.time_ms-a.time_ms-250)<=50 for a,b in zip(packets,packets[1:]))
            cmd(1,1);collect(.05);seen.clear();collect(.6)
            assert not any(p.apid in (0x10,0x11) for _,p in seen)
            # SAFE rejects a rate change and preserves the stored nominal period.
            cmd(3,1000,7);enter();seen.clear();collect(.6)
            assert len([p for _,p in seen if p.apid==0x10])==2
        elif suite=='counts':
            cmd(0);cmd(3,1000,7)
            p=hk();assert (p.fields['accepted'],p.fields['rejected'])==(2,1),p
            before=p.sequence;uptime=p.time_ms
            cmd(2);p=hk();assert (p.fields['accepted'],p.fields['rejected'])==(2,0),p
            assert p.sequence>before and p.time_ms>=uptime
            enter();cmd(2);p=hk();assert p.fields['mode']==2 and p.fields['accepted']==2
        elif suite=='allowlist':
            cmd(0);cmd(2);cmd(4)
            while receive().apid!=0x10:pass
            cmd(3,1000,7);cmd(5,1,5)
            cmd(3,250,6,249) # validation precedes mode permission
            assert hk().fields['mode']==1
            enter();cmd(3,250);cmd(2);cmd(0);assert hk().fields['mode']==2
        elif suite=='att':
            collect(1.15);assert not any(p.apid==0x11 for _,p in seen)
            enter();seen.clear();collect(3.2)
            packets=[(t,p) for t,p in seen if p.apid==0x11]
            assert len(packets)==3
            assert all(p.fields=={'x':0,'y':0,'z':0} for _,p in packets)
            assert all(abs((b[0]-a[0])*1000-1000)<=50 for a,b in zip(packets,packets[1:]))
            cmd(1,1);collect(.05);seen.clear();collect(1.2)
            assert not any(p.apid==0x11 for _,p in seen)
        print('M3 '+suite+' passed')
    finally:f.close()

if __name__=='__main__':run(sys.argv[1],sys.argv[2])
