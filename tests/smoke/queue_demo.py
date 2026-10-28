"""Exercise real FreeRTOS scheduling, queue copies, ordering, and clean exit."""
import json
import subprocess
import sys


def main():
    run = subprocess.run([sys.argv[1]], capture_output=True, text=True, timeout=10)
    if run.returncode != 0:
        raise RuntimeError(f"Demo exited {run.returncode}: {run.stderr}")
    record = json.loads(run.stdout)
    expected = {"milestone": "M0", "messages": 20, "checksum": 2870, "result": "pass"}
    for field, value in expected.items():
        if record.get(field) != value:
            raise RuntimeError(f"Unexpected {field}: {record}")
    if not isinstance(record.get("elapsed_ticks"), int) or record["elapsed_ticks"] <= 0:
        raise RuntimeError(f"Scheduler tick did not advance: {record}")
    print("PASS: 20 ordered queue messages, verified payloads, advancing ticks, clean exit")


if __name__ == "__main__":
    main()
