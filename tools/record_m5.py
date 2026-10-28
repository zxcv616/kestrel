"""Record and verify a real six-command/four-telemetry mission on isolated ports."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.flight_control import FlightController
from ground.ccsds import decode


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def record(binary, output):
    output.mkdir(parents=True, exist_ok=True)
    flight_port, ground_port = free_port(), free_port()
    while ground_port == flight_port:
        ground_port = free_port()
    controller = FlightController(binary, flight_port, ground_port)
    frames, commands = [], []
    def capture(label):
        snap = controller.snapshot()
        o = snap.get('observation')
        frames.append({'label': label, 'timeMs': o['timeMs'] if o else 0,
                       'mode': o['mode'] if o else 1, 'battery': o['battery'] if o else None,
                       'faultMask': o['faultMask'] if o else 0,
                       'packets': snap['loggedPackets']})
        return snap
    def wait(predicate, timeout=8):
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            snap = controller.snapshot()
            if predicate(snap):
                return snap
            time.sleep(.02)
        raise AssertionError('Mission condition timed out')
    def command(name, argument=0):
        reply = controller.command(name, argument)
        assert reply['status'] == 'OK', reply
        commands.append(reply)
    try:
        controller.start(test_build=True)
        wait(lambda s: s.get('observation') and s['observation']['sensorValid'])
        capture('Boot in SAFE')
        command('noop')
        command('request_hk')
        command('set_mode', 2)
        wait(lambda s: s['observation']['mode'] == 2 and any(p['packet']['apid']==17 for p in s['samples']))
        capture('NOMINAL: HK and ATT received')
        command('set_hk_rate', 250)
        command('reset_counters')
        capture('250 ms HK configured; counters reset')
        command('inject_fault', 5)
        wait(lambda s: s['observation']['mode'] == 3)
        capture('Battery 15%: LOW_POWER')
        wait(lambda s: s['observation']['mode'] == 2 and s['observation']['battery'] == 80)
        capture('Battery restored: automatic NOMINAL')
        command('inject_fault', 6)
        changed = wait(lambda s: s['observation']['mode'] == 1)['observation']
        assert 0 <= changed['changedAtMs']-changed['injectionStartMs'] <= 1000
        capture('Battery 5%: SAFE')
        wait(lambda s: not s['observation']['faultMask'] and s['observation']['battery']==80)
        assert controller.snapshot()['observation']['mode'] == 1
        capture('Fault cleared: SAFE retained')
        command('set_mode', 2)
        wait(lambda s: s['observation']['mode'] == 2)
        capture('Ground recovery: NOMINAL')
        # Freeze receive/log state under its lock, so counts and CSV share a cutoff.
        with controller.link.lock:
            snap = capture('Mission complete')
            raw = controller.csv_log()
        rows = list(csv.DictReader(io.StringIO(raw.decode())))
        assert len(rows) == snap['loggedPackets'] and rows
        types = set()
        for row in rows:
            packet = decode(bytes.fromhex(row['hex']))
            assert packet.apid == int(row['apid']) and packet.sequence == int(row['sequence'])
            assert packet.time_ms == int(row['mission_ms'])
            assert packet.fields == json.loads(row['fields_json'])
            types.add(packet.apid)
        assert types == {16,17,18,19}, types
        assert {c['command'] for c in commands} == {'noop','request_hk','set_mode','set_hk_rate','reset_counters','inject_fault'}
        assert snap['invalidPackets'] == 0 and snap['error'] is None
        (output/'mission.csv').write_bytes(raw)
        result = {'schemaVersion':1, 'result':'pass', 'recordedAt':datetime.now(timezone.utc).isoformat(),
                  'source':'Actual local test flight over loopback UDP; playback never sends commands',
                  'binarySha256':hashlib.sha256(controller.test_binary.read_bytes()).hexdigest(),
                  'commands':commands, 'telemetryTypes':['HK','ATT','EVENT','ACK'],
                  'loggedPackets':len(rows), 'criticalSafeDelayMs':changed['changedAtMs']-changed['injectionStartMs'],
                  'frames':frames}
        (output/'mission.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'result':'pass','commands':len(commands),'packets':len(rows),'criticalSafeDelayMs':result['criticalSafeDelayMs']}))
        return result
    finally:
        controller.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,default=ROOT/'build/kestrel_flight')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/verification/m5-demo')
    args=parser.parse_args()
    record(args.binary.resolve(),args.output.resolve())
