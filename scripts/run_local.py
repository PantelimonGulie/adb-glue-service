import hashlib
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
LOCAL = ROOT / ".local"
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
GLUE_URL = "http://127.0.0.1:8000"

# Mirrors docker-compose.yml, with 127.0.0.1 for the service hostnames and the database in .local/.
SERVICES = {
    "shop": (8001, {"GLUE_URL": GLUE_URL, "SHOP_WEBHOOK_SECRET": "demo-shop-secret"}),
    "emag": (8002, {"GLUE_URL": GLUE_URL, "EMAG_WEBHOOK_SECRET": "demo-emag-secret"}),
    "warehouse": (
        8003,
        {"GLUE_URL": GLUE_URL, "WAREHOUSE_WEBHOOK_SECRET": "demo-warehouse-secret"},
    ),
    "glue": (
        8000,
        {
            "SHOP_URL": "http://127.0.0.1:8001",
            "EMAG_URL": "http://127.0.0.1:8002",
            "WAREHOUSE_URL": "http://127.0.0.1:8003",
            "SHOP_WEBHOOK_SECRET": "demo-shop-secret",
            "EMAG_WEBHOOK_SECRET": "demo-emag-secret",
            "WAREHOUSE_WEBHOOK_SECRET": "demo-warehouse-secret",
            "DB_PATH": str(LOCAL / "glue.db"),
            "HTTP_TIMEOUT_SECONDS": "2",
            "RETRY_ATTEMPTS": "5",
            "RETRY_BASE_SECONDS": "0.5",
            "WORKER_CONCURRENCY": "10",
            "RECONCILE_INTERVAL_SECONDS": "10",
            "LLM_BASE_URL": "http://127.0.0.1:11434",
            "LLM_MODEL": "qwen2.5:3b",
            "SESSION_SECRET": "demo-session-secret",
            "VIEWER_PASSWORD": "viewer",
            "OPERATOR_PASSWORD": "operator",
            "ADMIN_PASSWORD": "admin",
            "DEMO_TRAFFIC": "slow",
        },
    ),
}
MOCKS = ("shop", "emag", "warehouse")

READY = """
Glue Service is running. Ctrl+C stops it; each service logs to .local/<name>.log.

  Glue dashboard      http://localhost:8000   users: admin, operator, viewer (password = name)
  Electronic Market   http://localhost:8001
  eMAG Marketplace    http://localhost:8002
  Warehouse           http://localhost:8003

The assistant needs Ollama running on this machine (https://ollama.com). If it is running, Glue
pulls qwen2.5:3b once (about 2 GB). Without it the Assistant page says the model server is not
answering; everything else works.
"""


def run(command: list, cwd: Path = ROOT) -> None:
    if subprocess.run(command, cwd=cwd).returncode:
        sys.exit("Failed: " + " ".join(command))


def run_if_changed(source: Path, stamp: Path, command: list, what: str) -> None:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if stamp.is_file() and stamp.read_text() == digest:
        return
    print(what)
    run(command, source.parent)
    stamp.write_text(digest)


def check_ports() -> None:
    for name, (port, _) in SERVICES.items():
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                sys.exit(
                    f"Port {port} ({name}) is in use. Is the Docker stack running? "
                    "Stop it with `docker compose stop`."
                )


def prepare_python() -> None:
    if not VENV_PYTHON.exists():
        print("Creating .venv")
        run([sys.executable, "-m", "venv", str(VENV)])
    pip = [str(VENV_PYTHON), "-m", "pip", "install", "-q", "--disable-pip-version-check"]
    requirements = ROOT / "requirements.txt"
    stamp = VENV / "requirements.sha256"
    run_if_changed(requirements, stamp, [*pip, "-r", str(requirements)], "Installing requirements")


def build_dashboard() -> None:
    index = FRONTEND / "dist" / "index.html"
    sources = [p for p in [*FRONTEND.glob("*"), *(FRONTEND / "src").rglob("*")] if p.is_file()]
    if index.is_file() and index.stat().st_mtime > max(p.stat().st_mtime for p in sources):
        return
    npm = shutil.which("npm")
    if not npm:
        sys.exit(
            "Building the dashboard needs Node.js 20.19 or newer with npm; the Dockerfile uses "
            "24.21.0. https://nodejs.org"
        )
    stamp = FRONTEND / "node_modules" / "package-lock.sha256"
    run_if_changed(
        FRONTEND / "package-lock.json", stamp, [npm, "ci"], "Installing dashboard packages"
    )
    print("Building the dashboard")
    run([npm, "run", "build"], FRONTEND)


def start(name: str) -> subprocess.Popen:
    port, env = SERVICES[name]
    command = [str(VENV_PYTHON), "-m", "uvicorn", f"{name}.main:app"]
    return subprocess.Popen(
        [*command, "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env={**os.environ, **env, "PYTHONUNBUFFERED": "1"},
        stdout=(LOCAL / f"{name}.log").open("w"),
        stderr=subprocess.STDOUT,
    )


def failed(name: str, what: str) -> None:
    log = LOCAL / f"{name}.log"
    tail = "".join(log.read_text(errors="replace").splitlines(keepends=True)[-15:])
    sys.exit(f"{name} {what}. The end of .local/{log.name}:\n{tail}")


def wait_healthy(name: str, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 60
    while process.poll() is None and time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{SERVICES[name][0]}/health", timeout=1)
            return
        except OSError:
            time.sleep(0.2)
    failed(name, "did not start")


def stop(processes: dict) -> None:
    for process in reversed(processes.values()):
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> None:
    if sys.version_info < (3, 12):  # noqa: UP036
        sys.exit(f"Python 3.12 or newer is needed; this is {sys.version.split()[0]}.")
    # Keeps these lines in order with pip's and npm's output when the console is a pipe.
    sys.stdout.reconfigure(line_buffering=True)
    check_ports()
    prepare_python()
    build_dashboard()
    LOCAL.mkdir(exist_ok=True)
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    processes = {}
    try:
        for name in MOCKS:
            processes[name] = start(name)
        for name in MOCKS:
            wait_healthy(name, processes[name])
        processes["glue"] = start("glue")
        wait_healthy("glue", processes["glue"])
        print(READY)
        while True:
            for name, process in processes.items():
                if process.poll() is not None:
                    failed(name, f"stopped with exit code {process.returncode}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping")
    finally:
        stop(processes)


if __name__ == "__main__":
    main()
