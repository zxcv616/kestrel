"""Capture a real short M2 session for the private console's recorded view."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.flight_control import FlightController


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,default=ROOT/'build/kestrel_flight')
    parser.add_argument('--output',type=Path,default=ROOT/'output/dashboard/m2-flight-record.json')
    args=parser.parse_args()
    controller=FlightController(args.binary.resolve())
    try:
        controller.start()
        for command in ('noop','request_hk'):
            result=controller.command(command)
            if result['status']!='OK':
                raise RuntimeError(f'{command} failed: {result}')
        deadline=time.monotonic()+1
        while time.monotonic()<deadline and controller.snapshot()['hk']['packet']['fields']['accepted']!=2:
            time.sleep(.01)
        session=controller.snapshot()
        if session['hk']['packet']['fields']['accepted']!=2:
            raise RuntimeError('Updated HK did not arrive.')
        session['running']=False
        session['state']='recorded'
        record={'recordedAt':datetime.now(timezone.utc).isoformat(),
                'source':'Local FreeRTOS process and real loopback UDP', 'session':session}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(record,indent=2)+'\n')
        print(f'M2 session recorded: {args.output}')
    finally:
        controller.stop()


if __name__=='__main__':
    main()
