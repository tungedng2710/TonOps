#!/usr/bin/env python3
"""Install, configure, verify, and run a Linux ClearML Docker GPU worker."""

import argparse
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "workers/clearml-agent"
VENV = ROOT / ".venv/clearml-agent"
CONFIG = ROOT / "docker-data/agent/clearml.conf"
IMAGE = "clearml/yolo12-worker:torch2.7.1-cu126"
CUDA_CHECK = """import json, torch
assert torch.cuda.is_available(), 'CUDA is unavailable inside the task image'
x = torch.ones((32, 32), device='cuda')
assert (x @ x).sum().item() == 32768
print(json.dumps({'torch': torch.__version__, 'cuda': torch.version.cuda,
                  'gpu_count': torch.cuda.device_count(),
                  'gpu': torch.cuda.get_device_name(0)}))
"""


def run(command, **kwargs):
    print("+ " + shlex.join(map(str, command)), flush=True)
    return subprocess.run(list(map(str, command)), check=True, **kwargs)


def configure(base_config):
    base_config = base_config.expanduser().resolve()
    if not base_config.is_file():
        raise ValueError(f"Missing {base_config}; run clearml-agent init first")
    if base_config == CONFIG:
        raise ValueError("Base configuration must differ from generated worker configuration")
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    # Includes preserve the user's API credentials and RustFS settings.
    content = (
        f"include required(file({json.dumps(str(base_config))}))\n"
        f"include required(file({json.dumps(str(ASSETS / 'agent.conf'))}))\n"
    )
    CONFIG.write_text(content)
    CONFIG.chmod(0o600)
    print(f"Worker configuration: {CONFIG}")


def doctor(args):
    gpu_selection = "all" if args.gpus == "all" else f"device={args.gpus}"
    if "," in args.gpus:
        gpu_selection = f'"{gpu_selection}"'
    checks = [
        ["nvidia-smi", "--query-gpu=index,name,driver_version", "--format=csv,noheader"],
        ["docker", "info", "--format", "{{json .Runtimes}}"],
        ["docker", "run", "--rm", "--gpus", gpu_selection,
         "--network=host", "--shm-size=2g", args.image, "python", "-c", CUDA_CHECK],
    ]
    failures = 0
    for command in checks:
        try:
            run(command, timeout=120)
        except (OSError, subprocess.SubprocessError) as exc:
            failures += 1
            print(f"FAILED: {exc}", file=sys.stderr)
    return 1 if failures else 0


def agent_command(args):
    agent = VENV / "bin/clearml-agent"
    if not agent.is_file():
        raise ValueError("Agent is not installed; run the install command")
    if not CONFIG.is_file():
        raise ValueError("Worker configuration is missing; run the configure command")
    command = [str(agent), "--config-file", str(CONFIG)]
    if args.command == "list":
        return command + ["list"]
    command += ["daemon", "--gpus", args.gpus, "--queue", args.queue]
    if args.command == "stop":
        return command + ["--stop"]
    return command + ["--create-queue", "--detached" if args.detached else "--foreground",
                      "--force-current-version", "--docker", args.image]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["install", "configure", "build", "doctor", "start", "stop", "list"])
    parser.add_argument("--python", default="python3.10", help="Python interpreter for the agent venv")
    parser.add_argument("--base-config", type=Path, default=Path.home() / "clearml.conf")
    parser.add_argument("--queue", default="gpu")
    parser.add_argument("--gpus", default="0", help="Physical GPU indices or UUIDs, comma separated")
    parser.add_argument("--worker-id", help="Defaults to hostname:gpu<selection>")
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--detached", action="store_true")
    args = parser.parse_args()
    if args.command == "install":
        run([args.python, "-m", "venv", VENV])
        run([VENV / "bin/python", "-m", "pip", "install", "-r", ASSETS / "requirements.txt"])
    elif args.command == "configure":
        configure(args.base_config)
    elif args.command == "build":
        run(["docker", "build", "--tag", args.image, ASSETS])
    elif args.command == "doctor":
        return doctor(args)
    else:
        command = agent_command(args)
        if args.command == "start" and doctor(args):
            return 1
        env = os.environ.copy()
        env["CLEARML_WORKER_ID"] = args.worker_id or f"{socket.gethostname()}:gpu{args.gpus}"
        run(command, env=env)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
