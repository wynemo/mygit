#!/usr/bin/env python3
"""Read-only legacy diff benchmark using the same byte samples as Rust."""
import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from diff_calculator import DifflibCalculator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=pathlib.Path)
    parser.add_argument("right", type=pathlib.Path)
    parser.add_argument("iterations", type=int)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 1000:
        parser.error("iterations must be 1..=1000")
    left = args.left.read_bytes()
    right = args.right.read_bytes()
    left_text, right_text = left.decode("utf-8"), right.decode("utf-8")
    calculator = DifflibCalculator()
    timings = []
    blocks = 0
    for _ in range(args.iterations):
        start = time.perf_counter()
        chunks = calculator.compute_diff(left_text, right_text)
        timings.append((time.perf_counter() - start) * 1000)
        blocks = sum(c.type != "equal" for c in chunks)
    timings.sort()
    print(json.dumps({
        "implementation": "python-legacy-diff", "iterations": args.iterations,
        "left_bytes": len(left), "right_bytes": len(right), "changed_blocks": blocks,
        "min_ms": timings[0], "median_ms": timings[args.iterations // 2],
        "max_ms": timings[-1], "scope": "legacy splitlines and chunk calculation; no UI or syntax",
    }))


if __name__ == "__main__":
    main()
