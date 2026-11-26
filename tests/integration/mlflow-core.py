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


def main(env_file: str, project: str, docker: str) -> None:
    docker_command = shlex.split(docker)
    compose_command = [
        *docker_command, "compose", "--env-file", env_file, "--project-name", project,
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
        elif name == "gitea":
            require(len(bindings) == 1 and bindings[0][0] == "127.0.0.1", "Gitea is exposed outside loopback")
        else:
            require(not bindings, f"Unexpected published port for {name}")
    port = ports["mlflow"][0][1]
    name = f"mlflow-core-test-{uuid.uuid4().hex[:12]}"
    reference = f"/results/{name}.json"

    try:
        ready()
        run("git-init")
        database_perms = compose(
            "exec", "-T", "postgres", "psql", "-U", "platform_db_admin", "-d", "postgres", "-At", "-c",
            "SELECT has_database_privilege('mlflow','gitea','CONNECT'),"
            " has_database_privilege('gitea','mlflow','CONNECT')",
            capture=True,
        )
        require(database_perms == "f|f", "Service database roles can connect to each other's database")
        print("PostgreSQL denied both cross-database connections", flush=True)
        storage_container = container_id("rustfs")
        storage_ip = inspect(storage_container, "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}")
        require(bool(storage_ip), "Could not resolve RustFS container IP for isolation test")
        run("client", "check-isolation", "--storage-ip", storage_ip)
        check_http_listener(port)
        run("client", "train", "--name", name, "--reference", reference)
        run("client", "verify", "--reference", reference)
        run("storage-test", "write", reference)
        run("storage-policy-test", name)
        commit = run("git-test", "write", name, capture=True)
        print(f"Verified private Git repository {name} at {commit}", flush=True)

        tracking_container = container_id("mlflow")
        for dependency in ("rustfs", "postgres"):
            compose("stop", dependency)
            try:
                wait_health(tracking_container, "unhealthy")
                print(f"MLflow became unhealthy with {dependency} stopped", flush=True)
            finally:
                compose("start", dependency)
                wait_health(tracking_container, "healthy")
                print(f"MLflow recovered after {dependency} restarted", flush=True)

        compose("down")
        ready()
        run("git-init")
        run("client", "verify", "--reference", reference)
        run("storage-test", "read", reference)
        run("git-test", "read", name, commit)
        check_http_listener(port)
        print("PASS: run, report, model, RustFS multipart object, and Git commit survived container recreation")
    except (RuntimeError, subprocess.SubprocessError, OSError):
        compose("ps", "--all")
        compose("logs", "--tail=35", "db-init", "storage-init", "mlflow", "gitea", "postgres", "rustfs")
        raise


if __name__ == "__main__":
    main(*sys.argv[1:])
