#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

from http_request_comparer import compare_paths


def _parse_param(value: str) -> Tuple[str, str]:
    s = value.strip()
    if not s:
        raise argparse.ArgumentTypeError("--param cannot be empty")
    if "=" in s:
        key, val = s.split("=", 1)
        key = key.strip()
        # value may be empty; keep as-is (to serialize as key=)
        return key, val
    # bare flag: include with empty string so it serializes as key=
    return s, ""


def _parse_header(value: str) -> Tuple[str, str]:
    s = value.strip()
    if not s:
        raise argparse.ArgumentTypeError("--header cannot be empty")
    if ":" in s:
        key, val = s.split(":", 1)
        return key.strip(), val.strip()
    # If format invalid (no ':'), treat whole string as header name with empty value
    return s, ""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare HTTP GET responses between two hosts for a list of paths.")
    p.add_argument("base_url_1", help="First base URL, e.g. https://api.example.com")
    p.add_argument("base_url_2", help="Second base URL, e.g. https://api.example.org")
    p.add_argument("paths_file", help="Text file containing one URL path per line")
    p.add_argument("--timeout", type=float, default=20.0, help="Request timeout in seconds (default: 20)")
    p.add_argument("--out-dir", default=".", help="Directory to write differing responses (default: current dir)")
    p.add_argument(
        "--param",
        action="append",
        type=_parse_param,
        default=[],
        help="Add a GET parameter to all requests. Use key=value or a bare key (repeatable)",
    )
    p.add_argument(
        "--header",
        action="append",
        type=_parse_header,
        default=[],
        help='Add a header to all requests, e.g. "Authorization: Bearer 123" (repeatable)',
    )
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
    common_params = args.param  # already list[tuple[str, str]] from type parser
    common_headers = dict(args.header) if args.header else {}

    outcomes = compare_paths(
        args.base_url_1,
        args.base_url_2,
        paths,
        timeout=args.timeout,
        out_dir=args.out_dir,
        common_params=common_params,
        common_headers=common_headers,
    )

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
