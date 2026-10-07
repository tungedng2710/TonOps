#!/usr/bin/env python3
"""Compatibility entry point for the TonOps object detection project CLI."""

from pathlib import Path
import runpy
import sys

if __name__ == "__main__":
    example = Path(__file__).resolve().parents[1] / "examples/vehicle_detection_yolo12"
    sys.path.insert(0, str(example))
    runpy.run_path(str(example / "project.py"), run_name="__main__")
