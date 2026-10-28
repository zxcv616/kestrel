"""Fixed live scenarios. Own a test flight while holding the console operation lock."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import uuid

SCENARIOS = {
    'low_battery': {'name':'Low battery recovery', 'injection':5, 'target':3, 'limitMs':1000},
    'critical_battery': {'name':'Critical battery protection', 'injection':6, 'target':1, 'limitMs':1000},
    'over_temperature': {'name':'Over-temperature protection', 'injection':7, 'target':1, 'limitMs':1000},
    'telemetry_stall': {'name':'Telemetry stall recovery', 'injection':3, 'target':1, 'limitMs':4000},
}


class Cancelled(Exception):
    pass


class ScenarioRunner:
    def __init__(self, flight, operation_lock, output):
        self.flight, self.operation_lock, self.output = flight, operation_lock, Path(output)
        self.lock = threading.Lock()
        self.cancel_event = threading.Event()
        self.thread = None
        self.result = {'state':'idle','steps':[]}
        self.report = None
        self.closing = False

    def snapshot(self):
        with self.lock:
            return deepcopy(self.result)

    def start(self, name):
        if not isinstance(name, str) or name not in SCENARIOS:
            raise ValueError('Choose a supported scenario.')
        with self.lock:
            if self.closing:
                raise RuntimeError('Console is closing.')
            if not self.operation_lock.acquire(blocking=False):
                raise RuntimeError('Another operation is running.')
            try:
                if self.flight.snapshot()['running'] or self.flight.process is not None:
                    raise RuntimeError('Stop the current flight before starting a scenario.')
                if not self.flight.test_binary.is_file():
                    raise RuntimeError('Build the test flight executable first.')
                self.cancel_event.clear()
                self.result = {'state':'running','id':uuid.uuid4().hex,'scenario':name,
                               'name':SCENARIOS[name]['name'],'startedAt':datetime.now(timezone.utc).isoformat(),
                               'steps':[], 'error':None, 'reportAvailable':False}
                self.report = None
                self.thread = threading.Thread(target=self._run,args=(SCENARIOS[name],),daemon=True)
                self.thread.start()
                return deepcopy(self.result)
            except Exception:
                self.operation_lock.release()
                raise

    def cancel(self):
        self.cancel_event.set()
        return self.snapshot()

    def close(self):
        with self.lock:
            self.closing = True
            thread = self.thread
            self.cancel_event.set()
        if thread:
            thread.join(timeout=8)
            if thread.is_alive():
                raise RuntimeError('Scenario did not stop within its shutdown deadline.')

    def download(self):
        with self.lock:
            if self.report is None:
                raise RuntimeError('A report is available after the scenario finishes.')
            return self.report

    def _check_cancel(self):
        if self.cancel_event.is_set():
            raise Cancelled('Scenario cancelled. Its test flight was stopped.')

    def _wait(self, predicate, timeout=8):
        deadline = time.monotonic()+timeout
        while time.monotonic()<deadline:
            self._check_cancel()
            snap=self.flight.snapshot()
            if not snap['running']:
                raise RuntimeError('Flight exited during the scenario.')
            observation=snap.get('observation')
            if observation and snap['observationAgeSeconds'] is not None and snap['observationAgeSeconds']<.5 and predicate(snap):
                return snap
            self.cancel_event.wait(.02)
        raise RuntimeError('Expected flight response did not arrive before the deadline.')

    def _command(self, name, argument=0):
        self._check_cancel()
        result=self.flight.command(name, argument)
        if result.get('status')!='OK':
            raise RuntimeError(f"{name}: {result.get('status') or result.get('state')}")
        return result

    def _step(self, name, operation):
        self._check_cancel()
        with self.lock:
            self.result['steps'].append({'name':name,'state':'running'})
            index=len(self.result['steps'])-1
        detail=operation() or {}
        self._check_cancel()
        with self.lock:
            self.result['steps'][index].update(state='passed',detail=detail)
        return detail

    def _run(self, scenario):
        state, error = 'passed', None
        terminal = None
        try:
            def boot():
                self.flight.start(test_build=True)
                snap=self._wait(lambda s:s['observation']['mode']==1 and s['observation']['sensorValid'])
                return {'mode':'SAFE','flightTimeMs':snap['observation']['timeMs']}
            self._step('Start a healthy test flight in SAFE',boot)
            def nominal():
                receipt=self._command('set_mode',2)
                self._wait(lambda s:s['observation']['mode']==2)
                return {'command':receipt,'mode':'NOMINAL'}
            self._step('Enter NOMINAL',nominal)
            self._step('Inject the selected condition for 5 seconds',lambda:{'command':self._command('inject_fault',scenario['injection'])})
            def protection():
                snap=self._wait(lambda s:s['observation']['injection']==scenario['injection'] and s['observation']['mode']==scenario['target'])
                o=snap['observation']; delay=o['changedAtMs']-o['injectionStartMs']
                if not 0<=delay<=scenario['limitMs']:
                    raise RuntimeError(f"Protection took {delay} ms; limit is {scenario['limitMs']} ms.")
                return {'mode':'LOW_POWER' if scenario['target']==3 else 'SAFE','transitionMs':delay,'limitMs':scenario['limitMs'], 'injectionStartMs':o['injectionStartMs'],'injectionEndMs':o['injectionEndMs']}
            change=self._step('Verify automatic protection',protection)
            if scenario['injection']==3:
                def watchdog():
                    o=self._wait(lambda s:bool(s['observation']['stalledMask'] & (1<<4)))['observation']
                    if o['misses'][3]!=3 or o['timeMs']-change['injectionStartMs']>4000:
                        raise RuntimeError('Watchdog did not detect three missed windows within 4 seconds.')
                    return {'missedWindows':3,'detectionMs':o['timeMs']-change['injectionStartMs']}
                self._step('Verify watchdog detection despite paused telemetry',watchdog)
            def recover():
                o=self._wait(lambda s:s['observation']['timeMs']>=change['injectionEndMs']+200 and not s['observation']['faultMask'] and not s['observation']['stalledMask'] and s['observation']['sensorValid'])['observation']
                expected=2 if scenario['target']==3 else 1
                if o['mode']!=expected:
                    raise RuntimeError('Unexpected recovery mode; critical faults must remain SAFE.')
                return {'mode':'NOMINAL' if expected==2 else 'SAFE','battery':o['battery'],'activeFaults':0}
            self._step('Verify fault clearance and recovery policy',recover)
            if scenario['target']==1:
                self._step('Recover deliberately to NOMINAL',nominal)
            def hk():
                previous=self.flight.snapshot()['hk']['packet']['sequence']
                receipt=self._command('request_hk')
                snap=self._wait(lambda s:s['hk']['packet']['sequence']!=previous and s['hk']['packet']['fields']['mode']==2)
                return {'command':receipt,'housekeeping':snap['hk']['packet']}
            self._step('Confirm NOMINAL through received housekeeping',hk)
            terminal=self.flight.snapshot()
        except Cancelled as exc:
            state,error='cancelled',str(exc)
        except Exception as exc:
            state,error='failed',str(exc)
        finally:
            try:
                csv_text = None
                # Follow FlightController's lock order and freeze telemetry/counts together.
                with self.flight.lock:
                    if self.flight.link:
                        with self.flight.link.lock:
                            terminal=self.flight.snapshot()
                            csv_text=self.flight.csv_log().decode()
                    elif terminal is None:
                        terminal=self.flight.snapshot()
                if state!='passed':
                    self.flight.stop()
                with self.lock:
                    for step in self.result['steps']:
                        if step['state']=='running':step.update(state=state,error=error)
                    self.result.update(state=state,error=error,finishedAt=datetime.now(timezone.utc).isoformat(),
                                       finalMode=(terminal.get('observation') or {}).get('mode'))
                    report=deepcopy(self.result)
                report['source']='Actual test flight; protection timing from internal observation, commands/housekeeping over UDP.'
                report['flight']=terminal
                if csv_text is not None:
                    report['telemetryCsv']=csv_text
                self.output.mkdir(parents=True,exist_ok=True)
                path=self.output/(report['id']+'.json')
                encoded=(json.dumps(report,indent=2)+'\n').encode()
                path.write_bytes(encoded)
                with self.lock:
                    self.report=encoded
                    self.result['reportAvailable']=True
            except Exception as exc:
                message='Scenario cleanup/report failed: '+str(exc)
                try:
                    self.flight.stop()
                except Exception as cleanup_error:
                    message+='; flight cleanup: '+str(cleanup_error)
                with self.lock:
                    self.result.update(state='failed',error=message)
            finally:
                self.operation_lock.release()
