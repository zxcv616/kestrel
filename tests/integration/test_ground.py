import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ground.link import GroundLink
from ground.ccsds import Packet, encode, decode
from tools.dashboard import DashboardServer
from tools.flight_control import FlightController

BINARY = Path(sys.argv.pop(1)) if len(sys.argv)>1 else ROOT/'build/kestrel_flight'


def available_port():
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


class GroundTests(unittest.TestCase):
    def test_timeout_late_ack_unexpected_source_and_no_retry(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as peer:
            peer.bind(('127.0.0.1',0))
            with GroundLink(peer.getsockname()[1],0) as link:
                result=link.command('noop',timeout=0.05)
                self.assertEqual(result['state'],'timeout')
                peer.settimeout(0.1)
                wire,address=peer.recvfrom(257)
                command=decode(wire)
                with self.assertRaises(socket.timeout):
                    peer.recvfrom(257)
                ack=encode(Packet(0x13,0,0,{'command_sequence':command.sequence,'status':0}))
                with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as foreign:
                    foreign.sendto(ack,address)
                peer.sendto(ack,address)
                deadline=time.monotonic()+1
                while time.monotonic()<deadline and link.snapshot()['history'][0]['state']!='late':
                    time.sleep(.01)
                self.assertEqual(link.snapshot()['history'][0]['state'],'late')
                self.assertEqual(link.snapshot()['invalidPackets'],1)
                events=link.snapshot()['events']
                self.assertEqual([e['direction'] for e in events],['tx','rx'])
                self.assertEqual(events[0]['hex'],wire.hex())
                self.assertEqual(events[1]['hex'],ack.hex())
                self.assertEqual(events[1]['commandSequence'],command.sequence)
                self.assertEqual(events[1]['status'],'OK')
                self.assertIsNotNone(events[1]['rttMs'])
                self.assertLess(events[0]['id'],events[1]['id'])
                with link.lock:
                    link.last_packet=time.monotonic()-16
                self.assertEqual(link.snapshot()['state'],'stale')
                with self.assertRaises(ValueError):
                    link.command('set_mode')

    def test_live_hk_fields_safe_nominal_low_power(self):
        controller=FlightController(BINARY,available_port(),available_port())
        try:
            controller.start(test_build=True)
            first=controller.snapshot()
            fields=first['hk']['packet']['fields']
            self.assertEqual(fields['mode'],1)
            self.assertEqual(fields['battery_percent'],80)
            self.assertEqual(fields['temperature_centi_c'],2000)
            self.assertEqual(fields['accepted'],0)
            self.assertEqual(fields['rejected'],0)
            self.assertEqual(first['history'],[])
            self.assertFalse(any(e['direction']=='tx' for e in first['events']))
            time.sleep(1.1)
            def fresh_hk(mode,battery):
                previous=controller.snapshot()['hk']['packet']['sequence']
                self.assertEqual(controller.command('request_hk')['status'],'OK')
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    snapshot=controller.snapshot()
                    packet=snapshot['hk']['packet']
                    fields=packet['fields']
                    if packet['sequence']!=previous and fields['mode']==mode and fields['battery_percent']==battery:
                        break
                    time.sleep(.01)
                self.assertEqual(fields['mode'],mode)
                self.assertEqual(fields['battery_percent'],battery)
                self.assertEqual(fields['temperature_centi_c'],2000)
                self.assertGreaterEqual(fields['uptime_s'],1)
                self.assertGreaterEqual(packet['time_ms'],1000)
                raw=next(e['hex'] for e in reversed(snapshot['events']) if e['label']=='HK' and e['sequence']==packet['sequence'])
                self.assertEqual(decode(bytes.fromhex(raw)).fields,fields)
            fresh_hk(1,80)
            self.assertEqual(controller.command('set_mode',2)['status'],'OK')
            fresh_hk(2,80)
            self.assertEqual(controller.command('inject_fault',5)['status'],'OK')
            time.sleep(.3)
            fresh_hk(3,15)
        finally:
            controller.stop()

    def test_http_real_session_security_and_owned_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            server=DashboardServer(0,Path(directory),[],Path(directory)/'missing',{},BINARY)
            server.flight=FlightController(BINARY,available_port(),available_port())
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            base=f'http://127.0.0.1:{server.server_port}'
            def post(action,origin=base,token=server.token,body=None):
                req=Request(base+'/api/flight/'+action,method='POST',data=json.dumps(body).encode() if body else None,headers={'Origin':origin,'X-Kestrel-Token':token})
                with urlopen(req,timeout=5) as response:
                    return json.load(response)
            try:
                for action in ('start','stop','noop','request_hk','nominal','safe','reset_counters','set_hk_rate','start_test','inject_fault'):
                    for origin,token in [('https://example.com',server.token),(base,'')]:
                        with self.assertRaises(HTTPError) as e:
                            post(action,origin,token)
                        self.assertEqual(e.exception.code,403)
                started=post('start');self.assertEqual(started['hk']['packet']['fields']['mode'],1)
                process=server.flight.process
                initial_session=started['sessionId']
                self.assertEqual(post('noop')['status'],'OK')
                self.assertEqual(post('request_hk')['status'],'OK')
                deadline=time.monotonic()+1
                while time.monotonic()<deadline and server.flight.snapshot()['hk']['packet']['fields']['accepted']!=2:
                    time.sleep(.01)
                self.assertEqual(server.flight.snapshot()['hk']['packet']['fields']['accepted'],2)
                self.assertEqual(post('nominal')['status'],'OK')
                time.sleep(1.1)
                self.assertEqual(post('safe')['status'],'OK')
                self.assertEqual(post('reset_counters')['status'],'OK')
                with urlopen(base+'/api/flight/log.csv') as response:
                    import csv, io
                    rows=list(csv.DictReader(io.StringIO(response.read().decode())))
                self.assertTrue({'HK','ATT','EVENT','ACK'} <= {r['type'] for r in rows})
                for row in rows:
                    self.assertEqual(decode(bytes.fromhex(row['hex'])).fields,json.loads(row['fields_json']))
                self.assertEqual(len(rows),server.flight.snapshot()['loggedPackets'])
                with self.assertRaises(HTTPError) as e:
                    post('start')
                self.assertEqual(e.exception.code,409)
                self.assertEqual(post('stop')['state'],'stopped')
                self.assertIsNotNone(process.poll())
                restarted=post('start');self.assertEqual(restarted['hk']['packet']['fields']['accepted'],0)
                self.assertNotEqual(restarted['sessionId'],initial_session)
                self.assertTrue(all(e['label'] in ('HK','EVENT') for e in restarted['events']))
                post('stop')
                test=post('start_test');self.assertTrue(test['testBuild'])
                self.assertEqual(post('nominal')['status'],'OK')
                self.assertEqual(post('inject_fault',body={'faultId':5})['status'],'OK')
                deadline=time.monotonic()+1
                while time.monotonic()<deadline and (server.flight.snapshot().get('observation') or {}).get('mode')!=3:
                    time.sleep(.01)
                self.assertEqual(server.flight.snapshot()['observation']['mode'],3)
                self.assertGreater(len(server.flight.snapshot()['recoveryTimeline']),1)
                process=server.flight.process
            finally:
                server.shutdown();worker.join();server.server_close()
            self.assertIsNotNone(process.poll())
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as check:
                check.bind(('127.0.0.1',server.flight.ground_port))


if __name__=='__main__':
    unittest.main()
