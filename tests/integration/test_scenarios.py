"""M6: real scenario execution, cancellation, exclusivity, failure and HTTP guards."""
import argparse
import csv
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.flight_control import FlightController
from tools.scenarios import ScenarioRunner, SCENARIOS
from tools.dashboard import DashboardServer

BINARY=ROOT/'build/kestrel_flight'


def port():
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def wait(predicate, timeout=12):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        if predicate():return
        time.sleep(.02)
    raise AssertionError('Timed out waiting for scenario state')


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.flight=FlightController(BINARY,port(),port())
        self.operation=threading.Lock()
        self.runner=ScenarioRunner(self.flight,self.operation,Path(self.temp.name))

    def tearDown(self):
        self.runner.close();self.flight.stop();self.temp.cleanup()

    def finish(self):
        self.runner.thread.join(timeout=12)
        self.assertFalse(self.runner.thread.is_alive())
        self.assertFalse(self.operation.locked())
        return self.runner.snapshot()

    def test_all_fixed_scenarios_and_download_evidence(self):
        for name in SCENARIOS:
            with self.subTest(scenario=name):
                self.runner.start(name)
                result=self.finish()
                self.assertEqual(result['state'],'passed',result)
                self.assertTrue(all(s['state']=='passed' for s in result['steps']))
                self.assertEqual(self.flight.snapshot()['observation']['mode'],2)
                report=json.loads(self.runner.download())
                self.assertIn('fields_json',report['telemetryCsv'])
                self.assertEqual(len(list(csv.DictReader(io.StringIO(report['telemetryCsv'])))),report['flight']['loggedPackets'])
                self.assertEqual(report['flight']['observation']['faultMask'],0)
                print(json.dumps({'scenario':name,'result':'passed','steps':len(result['steps']),
                    'transition':next(s['detail']['transitionMs'] for s in result['steps'] if 'transitionMs' in s.get('detail',{}))}))
                self.flight.stop()

    def test_existing_flight_and_unknown_scenario_are_preserved(self):
        self.flight.start(test_build=True)
        process=self.flight.process
        with self.assertRaises(RuntimeError):self.runner.start('low_battery')
        with self.assertRaises(ValueError):self.runner.start('../../command')
        self.assertIs(self.flight.process,process)
        self.assertIsNone(process.poll())
        self.assertFalse(self.operation.locked())

    def test_cancel_during_injection_stops_owned_flight(self):
        self.runner.start('critical_battery')
        wait(lambda:bool((self.flight.snapshot().get('observation') or {}).get('injection')))
        with self.assertRaises(RuntimeError):self.runner.start('low_battery')
        self.runner.cancel()
        result=self.finish()
        self.assertEqual(result['state'],'cancelled',result)
        self.assertFalse(self.flight.snapshot()['running'])
        self.assertTrue(result['reportAvailable'])
        self.assertEqual(json.loads(self.runner.download())['state'],'cancelled')

    def test_failed_command_is_visible_and_cleans_up(self):
        with patch.object(self.runner,'_command',side_effect=RuntimeError('forced ACK timeout')):
            self.runner.start('low_battery')
            result=self.finish()
        self.assertEqual(result['state'],'failed',result)
        self.assertIn('forced ACK timeout',result['error'])
        self.assertFalse(self.flight.snapshot()['running'])

    def test_report_write_failure_stops_flight_and_is_not_a_pass(self):
        blocked=Path(self.temp.name)/'blocked'
        blocked.write_text('not a directory')
        self.runner.output=blocked
        self.runner.start('low_battery')
        result=self.finish()
        self.assertEqual(result['state'],'failed',result)
        self.assertIn('report failed',result['error'])
        self.assertFalse(result['reportAvailable'])
        self.assertFalse(self.flight.snapshot()['running'])

    def test_server_close_cancels_worker(self):
        self.runner.start('telemetry_stall')
        wait(lambda:self.flight.snapshot()['running'])
        self.runner.close()
        self.assertFalse(self.runner.thread.is_alive())
        self.assertFalse(self.flight.snapshot()['running'])
        self.assertFalse(self.operation.locked())
        with self.assertRaises(RuntimeError):self.runner.start('low_battery')

    def test_http_security_validation_and_exclusive_commands(self):
        server=DashboardServer(0,Path(self.temp.name),[],BINARY,{},BINARY)
        server.flight=self.flight;server.scenario=self.runner;server.run_lock=self.operation
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def post(path,body=None,origin=base,token=server.token):
            request=Request(base+path,data=json.dumps(body).encode() if body is not None else b'',method='POST',
                headers={'Origin':origin,'X-Kestrel-Token':token,'Content-Type':'application/json'})
            with urlopen(request,timeout=4) as response:return json.load(response)
        try:
            for path in ['/api/scenario/start','/api/scenario/cancel']:
                for origin,token in [('https://example.com',server.token),(base,'')]:
                    with self.assertRaises(HTTPError) as error:post(path,{'scenario':'low_battery'},origin,token)
                    self.assertEqual(error.exception.code,403)
            for body in ({'scenario':'arbitrary'},{'scenario':[]},{'scenario':'low_battery','command':'bad'}):
                with self.assertRaises(HTTPError) as error:post('/api/scenario/start',body)
                self.assertEqual(error.exception.code,409)
            post('/api/scenario/start',{'scenario':'low_battery'})
            for path,body in [('/api/flight/noop',None),('/api/flight/stop',None),('/api/run-m0',None),('/api/scenario/start',{'scenario':'low_battery'})]:
                with self.assertRaises(HTTPError) as error:post(path,body)
                self.assertEqual(error.exception.code,409)
            with urlopen(base+'/api/flight') as response:self.assertEqual(json.load(response)['scenario']['state'],'running')
            post('/api/scenario/cancel')
            self.finish()
            with urlopen(base+'/api/scenario/report.json') as response:self.assertEqual(json.load(response)['state'],'cancelled')
        finally:
            server.shutdown();server.server_close();worker.join()


class JUnitResult(unittest.TextTestResult):
    def startTest(self,test):
        super().startTest(test);self.started=time.monotonic();self.problem=None
    def addFailure(self,test,err):
        super().addFailure(test,err);self.problem=self._exc_info_to_string(err,test)
    def addError(self,test,err):
        super().addError(test,err);self.problem=self._exc_info_to_string(err,test)
    def addSubTest(self,test,subtest,err):
        super().addSubTest(test,subtest,err)
        if err:self.problem=self._exc_info_to_string(err,test)
    def stopTest(self,test):
        case=ET.SubElement(self.report,'testcase',name='m6_'+test._testMethodName,time=str(time.monotonic()-self.started))
        if self.problem:ET.SubElement(case,'failure').text=self.problem
        super().stopTest(test)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,default=BINARY)
    parser.add_argument('--junit',type=Path,default=ROOT/'build/scenario-results.xml')
    args=parser.parse_args();BINARY=args.binary.resolve()
    JUnitResult.report=ET.Element('testsuite',name='M6 scenarios')
    result=unittest.TextTestRunner(verbosity=2,resultclass=JUnitResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(ScenarioTests))
    args.junit.parent.mkdir(parents=True,exist_ok=True)
    ET.ElementTree(JUnitResult.report).write(args.junit,encoding='utf-8',xml_declaration=True)
    sys.exit(not result.wasSuccessful())
