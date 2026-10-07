#!/usr/bin/env python3
"""Deploy the validated image and restore the prior deployment on smoke failure."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import time

import httpx

HERE = Path(__file__).resolve().parent
COMPOSE = ["docker", "compose", "-f", str(HERE / "compose.yaml")]


def smoke(url, revision, sample):
    deadline = time.monotonic() + 90
    with httpx.Client(timeout=10) as client:
        while True:
            try:
                response = client.get(url + "/health")
                response.raise_for_status()
                if response.json().get("revision") != revision:
                    raise ValueError("Serving revision differs from the built commit")
                break
            except (httpx.HTTPError, ValueError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Deployment failed its health/revision check")
                time.sleep(2)
        with sample.open("rb") as image:
            response = client.post(url + "/predict", files={"file": (sample.name, image, "image/jpeg")})
        response.raise_for_status()
        payload = response.json()
        if payload.get("revision") != revision or not isinstance(payload.get("detections"), list):
            raise RuntimeError("Deployment returned an invalid prediction response")
        if not payload["detections"]:
            raise RuntimeError("Deployment detected no objects in the COCO8 smoke image")
        invalid = client.post(url + "/predict", files={"file": ("invalid.jpg", b"invalid", "image/jpeg")})
        if invalid.status_code != 400:
            raise RuntimeError("Invalid images must return HTTP 400")
        with sample.open("rb") as image:
            invalid = client.post(url + "/predict?confidence=2", files={"file": (sample.name, image, "image/jpeg")})
        if invalid.status_code != 422:
            raise RuntimeError("Deployment accepted an invalid confidence")
        print(json.dumps(payload, indent=2))


def deploy(image, revision, port):
    env = dict(os.environ, YOLO12_IMAGE=image, YOLO12_PORT=str(port))
    previous_id = subprocess.check_output(COMPOSE + ["ps", "-a", "-q", "detector"], env=env, text=True).strip()
    previous = None
    if previous_id:
        previous = subprocess.check_output(["docker", "inspect", "--format", "{{.Config.Image}}", previous_id], text=True).strip()
    try:
        subprocess.run(COMPOSE + ["up", "-d", "--wait", "--wait-timeout", "90"], env=env, check=True)
        smoke(f"http://127.0.0.1:{port}", revision, HERE / "build/sample.jpg")
    except Exception:
        subprocess.run(COMPOSE + ["logs", "--tail", "50"], env=env, check=False)
        if previous:
            env["YOLO12_IMAGE"] = previous
            subprocess.run(COMPOSE + ["up", "-d", "--wait", "--wait-timeout", "90"], env=env, check=True)
            print(f"Restored previous deployment: {previous}", flush=True)
        else:
            subprocess.run(COMPOSE + ["down"], env=env, check=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--port", type=int, default=7865)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be in [1, 65535]")
    deploy(args.image, args.revision, args.port)
