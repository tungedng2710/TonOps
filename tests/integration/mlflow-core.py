"""Run M0/M1 integration checks against the configured, dedicated Compose project."""

import json
import shlex
import subprocess
import sys
import time
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def check_http_listener(port: str) -> None:
    url = f"http://127.0.0.1:{port}/"
    with urlopen(url, timeout=10) as response:
        require(b"<html" in response.read().lower(), "MLflow UI did not serve HTML")
    try:
        urlopen(Request(url, headers={"Host": "invalid.example"}), timeout=10)
    except HTTPError as error:
        require(error.code == 403, f"Unexpected response {error.code} for disallowed Host")
    else:
        raise RuntimeError("MLflow accepted a disallowed Host header")
    print("Direct HTTP listener served the MLflow UI and rejected an unlisted Host", flush=True)


def check_shared_gitea(docker_command: list[str], env_file: str) -> None:
    published = subprocess.check_output(
        [*docker_command, "compose", "--env-file", env_file, "-f", "compose.yaml",
         "port", "gitea", "3000"],
        text=True, timeout=15,
    ).strip()
    port = published.rsplit(":", 1)[-1]
    require(port.isdecimal(), "Could not find the shared ClearML Gitea port")
    with urlopen(f"http://127.0.0.1:{port}/api/healthz", timeout=10) as response:
        require(json.load(response).get("status") == "pass", "Shared Gitea failed its health check")
    print("Existing ClearML Gitea is healthy", flush=True)


def main(storage_env: str, env_file: str, project: str, docker: str) -> None:
    docker_command = shlex.split(docker)
    compose_command = [
        *docker_command, "compose", "--env-file", storage_env, "--env-file", env_file, "--project-name", project,
        "-f", "compose.mlflow.yaml", "-f", "versions.lock.yaml",
    ]

    def compose(*args: str, capture: bool = False) -> str:
        print(f"+ compose {shlex.join(args)}", flush=True)
        result = subprocess.run(
            [*compose_command, *args], check=True, text=True,
            stdout=subprocess.PIPE if capture else None, timeout=300,
        )
        return result.stdout.strip() if capture else ""

    def ready() -> None:
        compose("up", "-d", "--pull", "never", "--no-build", "--wait", "--wait-timeout", "180")

    def run(service: str, *args: str, capture: bool = False) -> str:
        return compose("run", "--rm", "--no-deps", "-T", service, *args, capture=capture)

    def container_id(service: str) -> str:
        return compose("ps", "-q", service, capture=True)

    def inspect(container: str, template: str) -> str:
        return subprocess.check_output(
            [*docker_command, "inspect", "--format", template, container],
            text=True, timeout=10,
        ).strip()

    def wait_health(container: str, expected: str) -> None:
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            if inspect(container, "{{.State.Health.Status}}") == expected:
                return
            time.sleep(3)
        raise RuntimeError(f"MLflow healthcheck did not reach {expected}")

    config = json.loads(compose("config", "--format", "json", capture=True))
    ports = {
        name: [(port["host_ip"], port["published"], port["target"])
               for port in service.get("ports", [])]
        for name, service in config["services"].items()
    }
    for name, bindings in ports.items():
        if name == "mlflow":
            require(len(bindings) == 1 and bindings[0][0] == "0.0.0.0" and bindings[0][2] == 5000,
                    "MLflow must publish its HTTP port on all IPv4 interfaces")
        else:
            require(not bindings, f"Unexpected published port for {name}")
    port = ports["mlflow"][0][1]
    name = f"mlflow-core-test-{uuid.uuid4().hex[:12]}"
    reference = f"/results/{name}.json"

    try:
        ready()
        check_shared_gitea(docker_command, storage_env)
        database_perms = compose(
            "exec", "-T", "postgres", "psql", "-U", "platform_db_admin", "-d", "postgres", "-At", "-c",
            "SELECT rolcanlogin AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)"
            " FROM pg_roles WHERE rolname = 'mlflow'",
            capture=True,
        )
        require(database_perms == "t", "The MLflow database role is missing or has unexpected privileges")
        print("PostgreSQL verified the restricted MLflow database role", flush=True)
        storage_ip = compose(
            "run", "--rm", "--no-deps", "-T", "--entrypoint", "python", "storage-test",
            "-c", "import socket; print(socket.gethostbyname('rustfs'))", capture=True,
        )
        require(bool(storage_ip), "Could not resolve RustFS container IP for isolation test")
        run("client", "check-isolation", "--storage-ip", storage_ip)
        check_http_listener(port)
        run("client", "train", "--name", name, "--reference", reference)
        run("client", "verify", "--reference", reference)
        run("storage-test", "write", reference)
        run("storage-policy-test", name)

        tracking_container = container_id("mlflow")
        compose("stop", "postgres")
        try:
            wait_health(tracking_container, "unhealthy")
            print("MLflow became unhealthy with PostgreSQL stopped", flush=True)
        finally:
            compose("start", "postgres")
            wait_health(tracking_container, "healthy")
            print("MLflow recovered after PostgreSQL restarted", flush=True)

        compose("down")
        ready()
        check_shared_gitea(docker_command, storage_env)
        run("client", "verify", "--reference", reference)
        run("storage-test", "read", reference)
        check_http_listener(port)
        print("PASS: run, report, model, and RustFS multipart object survived container recreation")
    except (RuntimeError, subprocess.SubprocessError, OSError):
        compose("ps", "--all")
        compose("logs", "--tail=35", "db-init", "storage-init", "mlflow", "postgres")
        raise


if __name__ == "__main__":
    main(*sys.argv[1:])
