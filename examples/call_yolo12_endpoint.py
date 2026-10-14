#!/usr/bin/env python3
"""Send an image to the YOLO12 endpoint and print its JSON detections.

Usage:
    python examples/call_yolo12_endpoint.py /path/to/photo.jpg

Uses only the Python standard library; no extra packages are required.
"""

import argparse
import base64
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_ENDPOINT = "http://27.66.108.30:7872/predict/yolo12"


def predict(image_path: Path, endpoint: str, timeout: float) -> dict:
    """POST the image as base64 JSON and return the prediction response.""" 
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = json.dumps({"image_base64": encoded}).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Path to a JPG or PNG image")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Prediction URL")
    parser.add_argument("--timeout", type=float, default=60, help="Timeout in seconds (default: 60)")
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"Image file does not exist: {args.image}")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    try:
        result = predict(args.image, args.endpoint, args.timeout)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        print(f"Endpoint returned HTTP {error.code}: {detail}", file=sys.stderr)
        return 1
    except (OSError, URLError, ValueError) as error:
        print(f"Prediction failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
