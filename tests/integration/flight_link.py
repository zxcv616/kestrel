"""Real FreeRTOS process and UDP sockets; no transport mocks."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ground.ccsds import Packet, decode, encode


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Flight:
    def __init__(self, binary):
        self.rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx.bind(('127.0.0.1', 0))
        self.ground_port = self.rx.getsockname()[1]
        self.flight_port = free_port()
        self.start = time.monotonic()
        self.process = subprocess.Popen([binary, '--flight-port', str(self.flight_port),
            '--ground-port', str(self.ground_port)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.next_sequence = {}
        self.hk = self.receive(2)
        self.boot_ms = (time.monotonic() - self.start) * 1000
        assert self.hk.apid == 0x10 and self.hk.fields['mode'] == 1
        assert self.hk.sequence == 0 and self.hk.time_ms < 2000
        assert self.hk.fields['accepted'] == self.hk.fields['rejected'] == 0
        assert self.hk.fields['battery_percent'] == 80
        assert self.hk.fields['temperature_centi_c'] == 2000
        assert self.hk.fields['battery_mv'] == 3800
        assert self.boot_ms < 2000
        boot = self.receive()
        assert boot.apid == 0x12 and boot.fields['parameter_1'] == 0 and boot.fields['parameter_2'] == 1

    def receive(self, timeout=1):
        self.rx.settimeout(timeout)
        wire, sender = self.rx.recvfrom(2048)
        assert sender == ('127.0.0.1', self.flight_port)
        p = decode(wire)
        assert encode(p) == wire
        assert p.sequence == self.next_sequence.get(p.apid, 0)
        self.next_sequence[p.apid] = (p.sequence + 1) & 0x3fff
        return p

    def send(self, wire, sender=None):
        (sender or self.rx).sendto(wire, ('127.0.0.1', self.flight_port))

    def command(self, sequence, function=0):
        return encode(Packet(0x100, sequence, 0, {'function': function, 'argument': 0}))

    def ack(self, wire, status=0, sender=None):
        started = time.monotonic()
        self.send(wire, sender)
        p = self.receive()
        latency = (time.monotonic() - started) * 1000
        assert p.apid == 0x13 and p.fields['status'] == status, p
        expected = (int.from_bytes(wire[2:4], 'big') & 16383) if len(wire) >= 4 else 65535
        assert p.fields['command_sequence'] == expected, p
        assert latency < 100, latency
        return latency

    def close(self):
        self.process.terminate()
        try:
            self.process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.communicate()
        self.rx.close()


def run(binary, suite):
    f = Flight(binary)
    try:
        if suite == 'boot':
            # A second instance must fail; it cannot share the command endpoint.
            duplicate = subprocess.run([binary, '--flight-port', str(f.flight_port),
                       '--ground-port', str(f.ground_port)], capture_output=True, timeout=2)
            assert duplicate.returncode != 0
            print(json.dumps({'bootSafeMs': round(f.boot_ms, 3), 'mode': 'SAFE'}))
        elif suite == 'invalid':
            fixtures = json.loads((ROOT / 'tests/vectors/packets.json').read_text())
            statuses = ['OK','BAD_LENGTH','BAD_HEADER','BAD_CRC','UNKNOWN_APID',
                        'UNKNOWN_FUNCTION','BAD_ARGUMENT']
            for v in fixtures['invalid']:
                f.ack(bytes.fromhex(v['hex']), statuses.index(v['error']))
            # Valid telemetry is not a command; production injection is unavailable.
            f.ack(bytes.fromhex(fixtures['valid'][0]['hex']), 4)
            for function, argument, status in [(3,1000,7),(5,1,5)]:
                f.ack(encode(Packet(0x100, 123, 0, {'function':function,'argument':argument})), status)
            f.ack(f.command(44) + bytes(8192), 1)
            f.ack(f.command(45,4))
            hk = f.receive()
            assert hk.fields['accepted'] == 1 and hk.fields['rejected'] == 36, hk
            assert hk.fields['mode'] == 1
            try:
                f.receive(0.15)
                raise AssertionError('Duplicate/unexpected packet')
            except socket.timeout:
                pass
            print('36 invalid/unsupported datagrams rejected once; counters and SAFE preserved.')
        elif suite == 'deadline':
            latencies = [f.ack(f.command(i)) for i in range(100)]
            # Bounded 64-datagram instantaneous burst; exact ACK count/order/status.
            start = time.monotonic()
            for i in range(100,164):
                f.send(f.command(i))
            for i in range(100,164):
                p = f.receive()
                assert p.apid == 0x13 and p.fields == {'command_sequence':i,'status':0}, p
                latencies.append((time.monotonic()-start)*1000)
            assert max(latencies) < 100, max(latencies)
            # ACK destination is fixed even if a command comes from another source port.
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as other:
                other.bind(('127.0.0.1',0))
                f.ack(f.command(164),sender=other)
                other.settimeout(0.1)
                try:
                    other.recvfrom(1000)
                    raise AssertionError('Reflected ACK to arbitrary source')
                except socket.timeout:
                    pass
            f.ack(f.command(165,4))
            hk=f.receive()
            assert hk.fields['accepted']==166 and hk.fields['rejected']==0, hk
            assert hk.fields['last_fault']==0, hk
            print(json.dumps({'commands':166,'burst':64,'maxRoundTripMs':round(max(latencies),3)}))
        elif suite == 'periodic':
            time.sleep(0.2)
            f.ack(f.command(0,4))
            response=f.receive()
            assert response.fields['accepted']==1 and response.time_ms < 2000
            # Immediate HK must not move the boot-relative 10-second SAFE deadline.
            periodic=f.receive(11)
            assert periodic.apid==0x10 and 9800 <= periodic.time_ms <= 10500, periodic
            assert periodic.fields['mode']==1 and periodic.fields['uptime_s']>=9
            assert periodic.fields['accepted']==1
            print(json.dumps({'periodicHKTimeMs':periodic.time_ms,'immediateHKTimeMs':response.time_ms}))
    finally:
        f.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('binary'); parser.add_argument('suite')
    args=parser.parse_args()
    run(args.binary,args.suite)
