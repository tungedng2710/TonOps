#!/usr/bin/env python3
"""Create/update a private Gitea YOLO12 example and register its local runner."""

import argparse
import base64
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RUNNER_IMAGE = "docker.gitea.com/runner:2.3.0"
LABEL = "yolo12-cpu:docker://tonops/yolo12-ci:local"


def api(url, auth, path, method="GET", payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(url + "/api/v1" + path, data=body, method=method,
                      headers={"Authorization": auth, "Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        content = response.read()
        return json.loads(content) if content else None


def run(command, **kwargs):
    return subprocess.run(command, check=True, cwd=ROOT, **kwargs)


def publish(url, username, auth, repo_name):
    target = ROOT / "docker-data/examples/gitea-yolo12-repo"
    target.mkdir(parents=True, exist_ok=True)
    # Publish an explicit source-only list; never scan local datasets/configs.
    paths = [".gitea/workflows/yolo12-cicd.yaml", ".gitignore",
             "scripts/clearml-gpu-worker.py", "workers/clearml-agent/requirements-task.txt",
             "tests/test_clearml_gpu_workflow.py", "tests/test_tonops_detection_project.py",
             "tests/test_yolo12_cicd.py", "tests/test_yolo12_api.py"]
    example = ROOT / "examples/vehicle_detection_yolo12"
    for pattern in ("*.py", "*.txt", "*.yaml"):
        paths.extend(str(path.relative_to(ROOT)) for path in example.glob(pattern))
    paths.extend(str(path.relative_to(ROOT)) for path in (example / "cicd").iterdir() if path.is_file())
    for relative in paths:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    shutil.copy2(example / "cicd/README.md", target / "README.md")
    remote = f"{url}/{username}/{repo_name}.git"
    if not (target / ".git").exists():
        subprocess.run(["git", "init", "-b", "main", str(target)], check=True)
        subprocess.run(["git", "-C", str(target), "remote", "add", "origin", remote], check=True)
    actual_remote = subprocess.check_output(["git", "-C", str(target), "remote", "get-url", "origin"], text=True).strip()
    if actual_remote != remote:
        raise RuntimeError(f"Existing example checkout points to another repository: {target}")
    env = dict(os.environ, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader",
               GIT_CONFIG_VALUE_0="Authorization: " + auth, GIT_TERMINAL_PROMPT="0")
    refs = subprocess.check_output(["git", "-C", str(target), "ls-remote", "origin", "refs/heads/main"], env=env, text=True).strip()
    if refs:
        subprocess.run(["git", "-C", str(target), "fetch", "origin", "main"], env=env, check=True)
        # Stop on divergence rather than overwriting edits made in Gitea.
        subprocess.run(["git", "-C", str(target), "merge", "--ff-only", "origin/main"], check=True)
    subprocess.run(["git", "-C", str(target), "add", "."], check=True)
    changes = subprocess.run(["git", "-C", str(target), "diff", "--cached", "--quiet"])
    if changes.returncode == 1:
        subprocess.run(["git", "-C", str(target), "-c", f"user.name={username}",
                        "-c", f"user.email={username}@users.noreply.local",
                        "commit", "-m", "Add tested YOLO12 training and deployment pipeline"], check=True)
    elif changes.returncode != 0:
        raise RuntimeError("Unable to inspect the example checkout")
    subprocess.run(["git", "-C", str(target), "push", "-u", "origin", "main"], env=env, check=True)
    print(f"Repository: {remote.removesuffix('.git')}", flush=True)
    print(f"Actions: {remote.removesuffix('.git')}/actions", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:7864")
    parser.add_argument("--username", default="tungn197")
    parser.add_argument("--repo", default="yolo12-cicd-example")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    url = args.url.rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username:
        parser.error("url must be an HTTP(S) URL without credentials")
    password = os.environ.get("GITEA_PASSWORD") or getpass.getpass("Gitea password: ")
    auth = "Basic " + base64.b64encode(f"{args.username}:{password}".encode()).decode()
    user = api(url, auth, "/user")
    if user["login"] != args.username:
        raise RuntimeError("Authenticated Gitea account differs from the requested owner")
    repo_path = f"/repos/{args.username}/{args.repo}"
    try:
        api(url, auth, repo_path)
    except HTTPError as exc:
        if exc.code != 404:
            raise
        api(url, auth, "/user/repos", "POST", {"name": args.repo, "private": True,
             "description": "YOLO12: test, COCO8 train, metric gate, build, deploy, predict",
             "default_branch": "main", "auto_init": False})
    api(url, auth, repo_path, "PATCH", {"has_actions": True})
    if not args.skip_build:
        run(["docker", "build", "--target", "ci", "-f",
             "examples/vehicle_detection_yolo12/cicd/Dockerfile", "-t", "tonops/yolo12-ci:local",
             "examples/vehicle_detection_yolo12"])
    config = json.loads(subprocess.check_output(["docker", "compose", "config", "--format", "json"], cwd=ROOT))
    data = next(Path(volume["source"]).parent for volume in config["services"]["gitea"]["volumes"]
                if volume["target"] == "/data") / "gitea-runner"
    data.mkdir(parents=True, exist_ok=True)
    if not (data / ".runner").exists():
        token = api(url, auth, repo_path + "/actions/runners/registration-token", "POST")["token"]
        token_file = data / "registration-token"
        with open(token_file, "w", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
            stream.write(token)
        try:
            run(["docker", "run", "--rm", "--network", "host", "-v", f"{data}:/data",
                 "-v", f"{ROOT}/workers/gitea-runner/config.yaml:/config.yaml:ro",
                 "--entrypoint", "gitea-runner", RUNNER_IMAGE, "--config", "/config.yaml",
                 "register", "--no-interactive", "--instance", url,
                 "--token-file", "/data/registration-token", "--name", "tonops-yolo12", "--labels", LABEL])
        finally:
            token_file.unlink(missing_ok=True)
        (data / ".runner").chmod(0o600)
    run(["docker", "compose", "-f", "compose.yaml", "-f", "compose.cicd.yaml",
         "up", "-d", "--no-deps", "gitea_runner"])
    publish(url, args.username, auth, args.repo)


if __name__ == "__main__":
    main()
