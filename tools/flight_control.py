"""Own only the flight child launched by this console, and its loopback receiver."""
from pathlib import Path
from collections import deque
import json
import subprocess
import threading
import time
from ground.link import GroundLink


class FlightController:
    def __init__(self, binary, flight_port=5000, ground_port=5001):
        self.binary = Path(binary)
        self.flight_port, self.ground_port = flight_port, ground_port
        self.lock = threading.RLock()
        self.process = None
        self.link = None
        self.last = None
        self.test_binary = self.binary.with_name('kestrel_flight_test')
        self.test_build = False
        self.observer = None
        self.observation_lock = threading.Lock()
        self.observations = deque(maxlen=600)
        self.timeline = deque(maxlen=100)
        self.observation_received = None
        self.observation_error = None

    def _observe(self, process, log_path):
        try:
            with log_path.open('w') as log:
                previous = None
                for line in process.stdout:
                    row = json.loads(line)
                    log.write(line)
                    log.flush()
                    with self.observation_lock:
                        self.observations.append(row)
                        self.observation_received = time.monotonic()
                        phase = ('armed' if row['timeMs'] < row['injectionStartMs'] else
                                 'active' if row['timeMs'] < row['injectionEndMs'] else 'expired')
                        key = (row['mode'], row['faultMask'], row['stalledMask'], row['injection'], phase)
                        if key != previous:
                            self.timeline.append(dict(row, injectionPhase=phase))
                        previous = key
        except (ValueError, OSError) as error:
            with self.observation_lock:
                self.observation_error = str(error)

    def start(self, test_build=False):
        with self.lock:
            if self.process is not None:
                raise RuntimeError('A console flight session already exists. Stop it first.')
            binary = self.test_binary if test_build else self.binary
            if not binary.is_file():
                raise FileNotFoundError('Build the flight binaries first.')
            link = GroundLink(self.flight_port, self.ground_port)
            try:
                self.test_build = test_build
                with self.observation_lock:
                    self.observations.clear(); self.timeline.clear()
                    self.observation_received = None; self.observation_error = None
                command = [str(binary), '--flight-port', str(self.flight_port), '--ground-port', str(self.ground_port)]
                if test_build:
                    command += ['--observe', '1']
                self.process = subprocess.Popen(command, stdout=subprocess.PIPE if test_build else subprocess.DEVNULL,
                                                stderr=subprocess.PIPE, text=True)
                if test_build:
                    log_path = link.log_path.with_suffix('.observations.jsonl')
                    self.observer = threading.Thread(target=self._observe, args=(self.process, log_path), daemon=True)
                    self.observer.start()
                self.link = link
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    if self.process.poll() is not None:
                        raise RuntimeError('Flight process exited during startup; check for an occupied UDP port.')
                    if link.snapshot()['hk']:
                        return self.snapshot()
                    time.sleep(0.01)
                raise RuntimeError('Flight did not produce SAFE housekeeping within 2 seconds.')
            except Exception:
                if self.link is None:
                    link.close()
                self.stop()
                raise

    def snapshot(self):
        with self.lock:
            if self.link:
                result = self.link.snapshot()
                if self.process.poll() is not None:
                    result.update(state='process_exited', error='Flight process exited. Stop and restart the session.')
                    if result['hk']:
                        result['hk']['stale'] = True
                result['running'] = self.process.poll() is None
                result['available'] = self.binary.is_file()
                result['testAvailable'] = self.test_binary.is_file()
                result['testBuild'] = self.test_build
                with self.observation_lock:
                    result['observation'] = dict(self.observations[-1]) if self.observations else None
                    result['observationAgeSeconds'] = (time.monotonic()-self.observation_received) if self.observation_received else None
                    result['observationError'] = self.observation_error
                    result['recoveryTimeline'] = list(reversed(self.timeline))
                    result['sensorSamples'] = list(self.observations)
                return result
            return {'state': 'stopped', 'running': False, 'available': self.binary.is_file(),
                    'testAvailable': self.test_binary.is_file(), 'testBuild': False, 'hk': None, 'history': [], 'logAvailable': self.last is not None, 'flightPort': self.flight_port, 'groundPort': self.ground_port}

    def command(self, name, argument=0):
        with self.lock:
            if not self.link or self.process.poll() is not None:
                raise RuntimeError('Start the flight simulator first.')
            if name == 'inject_fault' and not self.test_build:
                raise RuntimeError('Start a test flight to inject faults.')
            return self.link.command(name, argument=argument)

    def csv_log(self):
        with self.lock:
            if self.link:
                with self.link.lock:
                    return self.link.log_path.read_bytes()
            if getattr(self, 'last_log', None):
                return self.last_log.read_bytes()
            raise RuntimeError('No telemetry log yet. Start flight first.')

    def stop(self):
        with self.lock:
            if self.link:
                self.last = self.link.snapshot()
                self.last_log = self.link.log_path
                self.link.close()
                self.link = None
            if self.process:
                if self.process.poll() is None:
                    self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
                if self.observer:
                    self.observer.join(timeout=2)
                    self.observer = None
                if self.process.stdout:
                    self.process.stdout.close()
                self.process.stderr.close()
                self.process = None
            return self.snapshot()
