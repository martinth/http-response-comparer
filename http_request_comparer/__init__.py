from __future__ import annotations

import datetime as _dt
import json as _json
import threading as _threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import difflib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl

import requests


@dataclass
class FetchResult:
    base_url: str
    path: str
    status_code: int
    headers: dict[str, str]
    text: str
    json: Optional[Any]
    error: Optional[str] = None


@dataclass
class CompareOutcome:
    path: str
    equal: bool
    mode: str  # "json" or "text" or "error"
    diff: str
    file1: Optional[Path]
    file2: Optional[Path]


def _sanitize_path_for_filename(path: str) -> str:
    # remove leading slash, replace non-alnum with underscore, collapse repeats
    path = path.lstrip("/") or "root"
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", path)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return sanitized or "root"


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _try_parse_json(resp: requests.Response) -> Optional[Any]:
    try:
        return resp.json()
    except Exception:
        return None


def _start_barrier():
    # Two parties: host1 and host2 threads
    return _threading.Barrier(2)


def _fetch(
    base_url: str,
    path: str,
    timeout: float,
    session: requests.Session,
    start_barrier: _threading.Barrier,
    common_params: list[tuple[str, str]] | None,
    common_headers: dict[str, str] | None,
) -> FetchResult:
    # Build URL and merged query params
    # Split provided path into path part and existing query pairs
    split = urlsplit(path)
    path_only = split.path or "/"
    existing_params = parse_qsl(split.query, keep_blank_values=True)
    merged_params: list[tuple[str, str]] = []
    if existing_params:
        merged_params.extend(existing_params)
    if common_params:
        merged_params.extend(common_params)

    url = base_url.rstrip("/") + "/" + path_only.lstrip("/")
    headers = common_headers or {}

    try:
        # wait until both requests are ready to fire
        start_barrier.wait(timeout=timeout)
    except Exception:
        # Even if barrier breaks, proceed; we still attempt request
        pass
    try:
        resp = session.get(url, timeout=timeout, params=merged_params or None, headers=headers or None)
        text = resp.text
        js = _try_parse_json(resp)
        headers_resp = {k.lower(): v for k, v in resp.headers.items()}
        return FetchResult(base_url=base_url, path=path, status_code=resp.status_code, headers=headers_resp, text=text, json=js)
    except Exception as e:
        return FetchResult(base_url=base_url, path=path, status_code=-1, headers={}, text="", json=None, error=str(e))


def _json_compare(a: Any, b: Any) -> tuple[bool, str]:
    a_str = _json.dumps(a, sort_keys=True, indent=2, ensure_ascii=False)
    b_str = _json.dumps(b, sort_keys=True, indent=2, ensure_ascii=False)
    diff = "\n".join(
        difflib.unified_diff(a_str.splitlines(), b_str.splitlines(), fromfile="host1.json", tofile="host2.json", lineterm="")
    )
    return a_str == b_str, diff


def _text_diff(a: str, b: str) -> tuple[bool, str]:
    if a == b:
        return True, ""
    diff = "\n".join(
        difflib.unified_diff(a.splitlines(), b.splitlines(), fromfile="host1.txt", tofile="host2.txt", lineterm="")
    )
    return False, diff


def _write_outputs(path: str, content1: str, content2: str, is_json: bool, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = _timestamp()
    sanitized = _sanitize_path_for_filename(path)
    ext = "json" if is_json else "txt"
    f1 = out_dir / f"{ts}_{sanitized}_host1.{ext}"
    f2 = out_dir / f"{ts}_{sanitized}_host2.{ext}"
    f1.write_text(content1)
    f2.write_text(content2)
    return f1, f2


def compare_paths(
    base_url_1: str,
    base_url_2: str,
    paths: list[str],
    *,
    timeout: float = 20.0,
    out_dir: Path | str = ".",
    common_params: list[tuple[str, str]] | None = None,
    common_headers: dict[str, str] | None = None,
) -> list[CompareOutcome]:
    """
    For each path, concurrently request both hosts and compare responses.

    Returns a list of CompareOutcome objects with diff and any written files.
    """
    out_path = Path(out_dir)
    session1 = requests.Session()
    session2 = requests.Session()

    outcomes: list[CompareOutcome] = []

    for path in paths:
        barrier = _start_barrier()
        res1: Optional[FetchResult] = None
        res2: Optional[FetchResult] = None

        def run1():
            nonlocal res1
            res1 = _fetch(base_url_1, path, timeout, session1, barrier, common_params, common_headers)

        def run2():
            nonlocal res2
            res2 = _fetch(base_url_2, path, timeout, session2, barrier, common_params, common_headers)

        t1 = _threading.Thread(target=run1, daemon=True)
        t2 = _threading.Thread(target=run2, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout + 5); t2.join(timeout + 5)

        # Safety defaults if something went very wrong
        if res1 is None:
            res1 = FetchResult(base_url_1, path, -1, {}, "", None, error="thread did not return")
        if res2 is None:
            res2 = FetchResult(base_url_2, path, -1, {}, "", None, error="thread did not return")

        # Determine compare mode
        if res1.error or res2.error:
            diff_lines = []
            if res1.error:
                diff_lines.append(f"Host1 error: {res1.error}")
            if res2.error:
                diff_lines.append(f"Host2 error: {res2.error}")
            if res1.status_code != res2.status_code:
                diff_lines.append(f"Status codes differ: {res1.status_code} vs {res2.status_code}")
            diff = "\n".join(diff_lines)
            outcomes.append(CompareOutcome(path, False, "error", diff, None, None))
            continue

        # Prefer JSON comparison only if both parsed as JSON
        if res1.json is not None and res2.json is not None:
            equal, diff = _json_compare(res1.json, res2.json)
            file1 = file2 = None
            if not equal:
                # write pretty JSONs
                a_str = _json.dumps(res1.json, sort_keys=True, indent=2, ensure_ascii=False)
                b_str = _json.dumps(res2.json, sort_keys=True, indent=2, ensure_ascii=False)
                file1, file2 = _write_outputs(path, a_str, b_str, True, out_path)
            outcomes.append(CompareOutcome(path, equal, "json", diff, file1, file2))
        else:
            equal, diff = _text_diff(res1.text, res2.text)
            file1 = file2 = None
            if not equal:
                file1, file2 = _write_outputs(path, res1.text, res2.text, False, out_path)
            outcomes.append(CompareOutcome(path, equal, "text", diff, file1, file2))

    # Close sessions
    try:
        session1.close(); session2.close()
    except Exception:
        pass

    return outcomes


__all__ = [
    "compare_paths",
    "CompareOutcome",
]
