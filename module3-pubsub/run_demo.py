"""Start broker, dashboard, alarm monitor, (energy logger) and the simulator
as separate processes for a demo. Ctrl-C stops everything.

    python run_demo.py --rounds 30 --interval 0.5
"""
import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=7883)
ap.add_argument("--rounds", type=int, default=30)
ap.add_argument("--interval", type=float, default=0.5)
ap.add_argument("--with-energy-logger", action="store_true")
args = ap.parse_args()

procs = []


def spawn(*module_args):
    procs.append(subprocess.Popen([sys.executable, "-m", *module_args, "--port", str(args.port)], cwd=ROOT))


try:
    spawn("bus.broker")
    time.sleep(0.5)
    spawn("subscribers.alarm_monitor")
    if args.with_energy_logger:
        spawn("subscribers.energy_logger")
    time.sleep(0.3)
    spawn("publishers.sensor_simulator", "--rounds", str(args.rounds), "--interval", str(args.interval))
    print("\nDemo running. In another terminal try:\n"
          "  python -m subscribers.dashboard\n"
          "  python -m publishers.operator_console B201 --by kris\n")
    procs[-1].wait()
    print("simulator finished; press Ctrl-C to stop the rest")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    for p in procs:
        if p.poll() is None:
            p.send_signal(signal.SIGTERM)
