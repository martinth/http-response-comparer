#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from http_request_comparer import compare_paths


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare HTTP GET responses between two hosts for a list of paths.")
    p.add_argument("base_url_1", help="First base URL, e.g. https://api.example.com")
    p.add_argument("base_url_2", help="Second base URL, e.g. https://api.example.org")
    p.add_argument("paths_file", help="Text file containing one URL path per line")
    p.add_argument("--timeout", type=float, default=20.0, help="Request timeout in seconds (default: 20)")
    p.add_argument("--out-dir", default=".", help="Directory to write differing responses (default: current dir)")
    return p.parse_args()


def load_paths(file_path: str | Path) -> List[str]:
    lines = Path(file_path).read_text().splitlines()
    paths: List[str] = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        paths.append(s)
    return paths


def main() -> int:
    args = parse_args()
    paths = load_paths(args.paths_file)
    outcomes = compare_paths(args.base_url_1, args.base_url_2, paths, timeout=args.timeout, out_dir=args.out_dir)

    any_diff = False
    for oc in outcomes:
        status = "OK" if oc.equal else "DIFF"
        mode = oc.mode.upper()
        print(f"[{status}] {oc.path} ({mode})")
        if not oc.equal:
            any_diff = True
            if oc.diff:
                print(oc.diff)
            if oc.file1 and oc.file2:
                print(f"Written differing responses to:\n  {oc.file1}\n  {oc.file2}")
        print()
    return 1 if any_diff else 0


if __name__ == "__main__":
    raise SystemExit(main())
