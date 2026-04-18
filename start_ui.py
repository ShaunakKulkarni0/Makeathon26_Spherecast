#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "src" / "ui" / "frontend"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"


def _pick_python() -> str:
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def _is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


def _terminate(proc: subprocess.Popen[bytes], name: str) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        print(f"{name} did not stop gracefully, killing.")
        proc.kill()
        proc.wait(timeout=5)


def main() -> int:
    python_bin = _pick_python()
    print(f"Using Python: {python_bin}")
    api_host = "127.0.0.1"
    api_port = 8001
    ui_port = 8000

    if _is_port_in_use(api_host, api_port):
        print(f"Cannot start API: {api_host}:{api_port} is already in use.")
        return 1
    if _is_port_in_use(api_host, ui_port):
        print(f"Cannot start frontend: {api_host}:{ui_port} is already in use.")
        return 1

    api_cmd = [
        python_bin,
        "-m",
        "uvicorn",
        "src.ui.api.main:app",
        "--host",
        api_host,
        "--port",
        str(api_port),
    ]
    ui_cmd = [python_bin, "-m", "http.server", str(ui_port)]

    try:
        api_proc = subprocess.Popen(api_cmd, cwd=ROOT)
    except Exception as exc:
        print(f"Failed to start API: {exc}")
        return 1

    time.sleep(0.5)
    if api_proc.poll() is not None:
        print("API process exited immediately. Check OPENAI_API_KEY and dependencies.")
        return api_proc.returncode or 1

    try:
        ui_proc = subprocess.Popen(ui_cmd, cwd=FRONTEND_DIR)
    except Exception as exc:
        print(f"Failed to start frontend server: {exc}")
        _terminate(api_proc, "API")
        return 1

    time.sleep(0.2)
    if ui_proc.poll() is not None:
        print("Frontend process exited immediately. Check port 8000 and permissions.")
        _terminate(api_proc, "API")
        return ui_proc.returncode or 1

    print(f"API:      http://{api_host}:{api_port}")
    print(f"Frontend: http://{api_host}:{ui_port}")
    print("Press Ctrl+C to stop both.")

    def _signal_handler(_signum: int, _frame: object) -> None:
        print("\nStopping services...")
        _terminate(ui_proc, "Frontend")
        _terminate(api_proc, "API")
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        while True:
            if api_proc.poll() is not None:
                print("API stopped. Shutting down frontend.")
                _terminate(ui_proc, "Frontend")
                return api_proc.returncode or 1
            if ui_proc.poll() is not None:
                print("Frontend stopped. Shutting down API.")
                _terminate(api_proc, "API")
                return ui_proc.returncode or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        _signal_handler(signal.SIGINT, None)
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    raise SystemExit(main())
