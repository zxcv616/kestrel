"""Run with python3 -m ground.cli. Only one ground receiver may bind a port."""
import argparse
import json
import time
from ground.link import GroundLink


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('noop', 'request_hk', 'set_mode', 'reset_counters', 'set_hk_rate', 'inject_fault', 'listen'))
    parser.add_argument('--flight-port', type=int, default=5000)
    parser.add_argument('--ground-port', type=int, default=5001)
    parser.add_argument('--seconds', type=float, default=11)
    parser.add_argument('--argument', type=int, default=0, help='Mode 1/2, HK period in milliseconds, or fault ID 1..9 (test flight only)')
    parser.add_argument('--log-directory', default=None)
    args = parser.parse_args()
    with GroundLink(args.flight_port, args.ground_port, args.log_directory) as link:
        if args.command != 'listen':
            result = link.command(args.command, argument=args.argument)
            print(json.dumps(result), flush=True)
            if result['status'] != 'OK':
                raise SystemExit(1)
        deadline = time.monotonic() + (args.seconds if args.command == 'listen' else 1)
        while time.monotonic() < deadline:
            time.sleep(0.05)
            if args.command != 'listen' and link.snapshot()['hk']:
                break
        print(json.dumps(link.snapshot(), indent=2))


if __name__ == '__main__':
    main()
