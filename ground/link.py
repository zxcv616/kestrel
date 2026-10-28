"""One loopback UDP owner, bounded ACK history, and measured receive timestamps."""
from collections import deque
from dataclasses import asdict
import csv
import json
from pathlib import Path
import socket
import threading
import time
import uuid
from ground.ccsds import Packet, PacketError, Sequences, decode, encode, COMMANDS

STATUS = ('OK', 'BAD_LENGTH', 'BAD_HEADER', 'BAD_CRC', 'UNKNOWN_APID',
          'UNKNOWN_FUNCTION', 'BAD_ARGUMENT', 'MODE_DENIED', 'BUSY')


class GroundLink:
    def __init__(self, flight_port=5000, ground_port=5001, log_directory=None):
        self.destination = ('127.0.0.1', flight_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(('127.0.0.1', ground_port))
            self.socket.settimeout(0.1)
        except OSError:
            self.socket.close()
            raise
        self.lock = threading.RLock()
        self.command_lock = threading.Lock()
        self.stop = threading.Event()
        self.sequences = Sequences()
        self.epoch = time.monotonic()
        self.history = deque(maxlen=100)
        self.session_id = uuid.uuid4().hex
        self.events = deque(maxlen=100)
        self.event_id = 0
        self.samples = deque(maxlen=240)
        self.mode_events = deque(maxlen=100)
        self.received_count = 0
        directory = Path(log_directory) if log_directory else Path(__file__).resolve().parents[1] / 'output/telemetry'
        try:
            directory.mkdir(parents=True, exist_ok=True)
            self.log_path = directory / (self.session_id + '.csv')
            self.log_file = self.log_path.open('x', newline='')
            self.csv = csv.writer(self.log_file)
            self.csv.writerow(['received_at', 'type', 'apid', 'sequence', 'mission_ms', 'fields_json', 'hex'])
            self.log_file.flush()
        except OSError:
            self.socket.close()
            raise
        self.pending = {}
        self.hk = None
        self.last_packet = None
        self.invalid = 0
        self.unmatched = 0
        self.error = None
        self.thread = threading.Thread(target=self._receive, daemon=True)
        self.thread.start()

    def _record(self, direction, wire, packet):
        self.event_id += 1
        label = {0x10: 'HK', 0x11: 'ATT', 0x12: 'EVENT', 0x13: 'ACK'}.get(packet.apid, 'CMD')
        if packet.apid == 0x100:
            label = COMMANDS[packet.fields['function']][0].replace('_', ' ')
        event = {'id': self.event_id, 'direction': direction, 'label': label,
                 'hex': wire.hex(), 'sequence': packet.sequence, 'at': time.time(),
                 'status': None, 'rttMs': None}
        self.events.append(event)
        return event

    def _receive(self):
        while not self.stop.is_set():
            try:
                wire, address = self.socket.recvfrom(257)
            except socket.timeout:
                continue
            except OSError as error:
                if not self.stop.is_set():
                    with self.lock:
                        self.error = str(error)
                break
            now = time.monotonic()
            try:
                if address != self.destination:
                    raise PacketError('UNEXPECTED_SOURCE')
                packet = decode(wire)
                if packet.apid == 0x100:
                    raise PacketError('UNEXPECTED_COMMAND')
            except PacketError:
                with self.lock:
                    self.invalid += 1
                continue
            with self.lock:
                self.last_packet = now
                activity = self._record("rx", wire, packet)
                try:
                    self.csv.writerow([activity['at'], activity['label'], packet.apid,
                        packet.sequence, packet.time_ms, json.dumps(packet.fields, sort_keys=True), wire.hex()])
                    self.log_file.flush()
                except OSError as error:
                    self.error = 'Telemetry logging failed: ' + str(error)
                    break
                self.received_count += 1
                sample = {'receivedAt': activity['at'], 'packet': asdict(packet)}
                if packet.apid in (0x10, 0x11):
                    self.samples.append(sample)
                if packet.apid == 0x12:
                    self.mode_events.append(sample)
                if packet.apid == 0x010:
                    self.hk = {'packet': asdict(packet), 'receivedAt': time.time(), '_received': now}
                elif packet.apid == 0x013:
                    sequence = packet.fields['command_sequence']
                    code = packet.fields['status']
                    activity['status'] = STATUS[code] if code < len(STATUS) else 'UNKNOWN_STATUS'
                    activity['commandSequence'] = sequence
                    waiting = self.pending.get(sequence)
                    row = waiting[0] if waiting else next((r for r in reversed(self.history)
                          if r['sequence'] == sequence and r['state'] == 'timeout'), None)
                    if row is None:
                        self.unmatched += 1
                        continue
                    status = packet.fields['status']
                    row.update(state='acknowledged' if waiting else 'late',
                               status=STATUS[status] if status < len(STATUS) else 'UNKNOWN_STATUS',
                               rttMs=round((now - row['_sent']) * 1000, 3), ackSequence=packet.sequence)
                    activity["rttMs"] = row["rttMs"]
                    if waiting:
                        waiting[1].set()

    def command(self, name, timeout=1.0, argument=0):
        functions = {'noop': 0, 'set_mode': 1, 'reset_counters': 2, 'set_hk_rate': 3, 'request_hk': 4, 'inject_fault': 5}
        if name not in functions:
            raise ValueError('Unknown command.')
        # Validate before consuming a sequence or creating a pending row.
        encode(Packet(0x100, 0, 0, {'function': functions[name], 'argument': argument}))
        if not self.command_lock.acquire(blocking=False):
            raise RuntimeError('A command is awaiting acknowledgement.')
        sequence = None
        try:
            with self.lock:
                if self.stop.is_set() or self.error:
                    raise RuntimeError('Ground link is closed or failed.')
                sequence = self.sequences.take(0x100)
                now = time.monotonic()
                packet = Packet(0x100, sequence, int((now - self.epoch) * 1000) & 0xffffffff,
                                {'function': functions[name], 'argument': argument})
                row = {'sequence': sequence, 'command': name, 'argument': argument, 'sentAt': time.time(),
                       '_sent': now, 'state': 'pending', 'status': None, 'rttMs': None}
                event = threading.Event()
                self.history.append(row)
                self.pending[sequence] = (row, event)
                try:
                    wire = encode(packet)
                    self.socket.sendto(wire, self.destination)
                    self._record("tx", wire, packet)
                except OSError:
                    row['state'] = 'send_failed'
                    raise
            event.wait(timeout)
            with self.lock:
                if row['state'] == 'pending':
                    row['state'] = 'timeout'
                return {k: v for k, v in row.items() if not k.startswith('_')}
        finally:
            with self.lock:
                if sequence is not None:
                    self.pending.pop(sequence, None)
            self.command_lock.release()

    def snapshot(self):
        with self.lock:
            now = time.monotonic()
            age = None if self.last_packet is None else round(now - self.last_packet, 3)
            state = ('closed' if self.stop.is_set() else 'error' if self.error else
                     'listening' if age is None else 'connected' if age <= 15 else 'stale')
            hk = None
            if self.hk:
                hk = {k: v for k, v in self.hk.items() if not k.startswith('_')}
                hk['ageSeconds'] = round(now - self.hk['_received'], 3)
                hk['stale'] = hk['ageSeconds'] > 15
            return {'samples': list(self.samples), 'modeEvents': list(reversed(self.mode_events)),
                    'loggedPackets': self.received_count, 'logAvailable': True, 'sessionId': self.session_id, 'events': [dict(e) for e in self.events], 'state': state, 'lastPacketAgeSeconds': age, 'hk': hk,
                    'history': [{k: v for k, v in r.items() if not k.startswith('_')}
                                for r in reversed(self.history)],
                    'invalidPackets': self.invalid, 'unmatchedAcks': self.unmatched,
                    'error': self.error, 'flightPort': self.destination[1],
                    'groundPort': self.socket.getsockname()[1] if not self.stop.is_set() else None}

    def close(self):
        self.stop.set()
        with self.lock:
            for row, event in self.pending.values():
                row['state'] = 'cancelled'
                event.set()
        self.thread.join(timeout=1)
        self.socket.close()
        self.log_file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
