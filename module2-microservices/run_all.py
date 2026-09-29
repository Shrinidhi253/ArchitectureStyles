"""Start every service listed in services.txt as a separate OS process.

    python run_all.py            # start (Ctrl-C stops everything)
    python run_all.py --reset    # wipe all databases first
    python run_all.py --port-offset 100   # run on 5100..  (used by the tests)

Each service receives, through environment variables:
    <NAME>_PORT   its own port
    <NAME>_DB     path of its own SQLite file  (data/<name>.db)
    <NAME>_URL    the base URL of every service, so they can find each other
"""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent


def load_services(path=ROOT / "services.txt"):
    services = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, directory, port = line.split()
        services.append((name, directory, int(port)))
    return services


def start(port_offset=0, reset=False, quiet=False):
    services = load_services()
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    env = dict(os.environ)
    for name, _, port in services:
        env[f"{name.upper()}_PORT"] = str(port + port_offset)
        env[f"{name.upper()}_URL"] = f"http://127.0.0.1:{port + port_offset}"
        db = data_dir / f"{name}.db"
        env[f"{name.upper()}_DB"] = str(db)
        if reset and db.exists():
            db.unlink()
    procs = []
    out = subprocess.DEVNULL if quiet else None
    for name, directory, port in services:
        p = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT / directory, env=env,
                             stdout=out, stderr=out)
        procs.append((name, port + port_offset, p))
    # wait until every service answers /health
    deadline = time.time() + 20
    for name, port, p in procs:
        while True:
            try:
                if requests.get(f"http://127.0.0.1:{port}/health", timeout=0.5).ok:
                    break
            except requests.RequestException:
                pass
            if p.poll() is not None:
                raise RuntimeError(f"service {name} exited with code {p.returncode}")
            if time.time() > deadline:
                raise RuntimeError(f"service {name} did not start on port {port}")
            time.sleep(0.2)
    return procs


def stop(procs):
    for _, _, p in procs:
        if p.poll() is None:
            p.send_signal(signal.SIGTERM)
    for _, _, p in procs:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--port-offset", type=int, default=0)
    args = ap.parse_args()
    running = start(args.port_offset, args.reset)
    for name, port, _ in running:
        print(f"{name:10s} http://127.0.0.1:{port}")
    print("Gateway ready. Press Ctrl-C to stop.")
    try:
        while all(p.poll() is None for _, _, p in running):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop(running)
