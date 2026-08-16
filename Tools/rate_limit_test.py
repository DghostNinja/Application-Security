#!/usr/bin/env python3
"""Replay a raw HTTP request N times to probe rate limiting.

Usage:
  python3 rate_limit_test.py request.txt [count] [pause_seconds]
  echo '<raw request>' | python3 rate_limit_test.py - [count] [pause_seconds]
  python3 rate_limit_test.py --raw 'POST /path HTTP/1.1
Host: example.com

{"a":1}' [count] [pause]

Optional env:
  VERIFY_SSL=0   to skip TLS verification (defaults to 1)
"""
import os
import sys
import time

import requests

VERIFY_SSL = os.environ.get("VERIFY_SSL", "1") == "1"


def parse_raw_request(raw):
    """Split a raw HTTP/1.1 request string into (method, url, headers, body)."""
    if "\r\n" in raw and "\n\n" not in raw.replace("\r\n", "\n"):
        pass
    normalized = raw.replace("\r\n", "\n")
    lines = normalized.split("\n")
    req_line = lines[0].strip()
    parts = req_line.split(" ")
    if len(parts) < 2:
        raise ValueError(f"Bad request line: {req_line!r}")
    method = parts[0]
    target = parts[1]

    headers = {}
    body_lines = []
    in_body = False
    for line in lines[1:]:
        if not in_body and line == "":
            in_body = True
            continue
        if in_body:
            body_lines.append(line)
        else:
            if ":" not in line:
                continue
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
    body = "\n".join(body_lines)

    if target.startswith("http://") or target.startswith("https://"):
        url = target
    else:
        host = headers.get("host", "")
        if not host:
            raise ValueError("No Host header and relative path in request line")
        scheme = "https" if headers.get("origin", "").startswith("https://") else "http"
        if headers.get("origin", "").startswith("http"):
            scheme = headers["origin"].split("://")[0]
        url = f"{scheme}://{host}{target}"

    # Strip hop-by-hop headers; requests recomputes these.
    for h in ("content-length", "connection", "accept-encoding"):
        headers.pop(h, None)

    return method, url, headers, body


def main():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    raw = None
    if not args:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
        else:
            print(__doc__)
            sys.exit(1)
    else:
        if args[0] == "--raw":
            raw = args[1]
            args = args[2:]
        elif args[0] == "-":
            raw = sys.stdin.read()
            args = args[1:]
        else:
            path = args[0]
            args = args[1:]
            with open(path, encoding="utf-8") as f:
                raw = f.read()

    count = int(args[0]) if len(args) > 0 else 50
    pause = float(args[1]) if len(args) > 1 else 0.0

    method, url, headers, body = parse_raw_request(raw)
    print(f"Replaying: {method} {url}")
    print(f"Headers   : {len(headers)} ({', '.join(sorted(headers))})")
    print(f"Body      : {len(body)} bytes")
    print(f"Count     : {count}  | pause: {pause}s  | verify_ssl: {VERIFY_SSL}\n")

    status_counts = {}
    start_all = time.time()
    print(f"{'#':>4} {'status':>6} {'time(s)':>8} {'retry':>7}  note")
    print("-" * 60)

    for i in range(1, count + 1):
        t0 = time.perf_counter()
        try:
            r = requests.request(
                method, url, headers=headers,
                data=body.encode() if body else None,
                timeout=15, verify=VERIFY_SSL,
            )
            dt = time.perf_counter() - t0
            retry = r.headers.get("Retry-After", "-")
            note = r.text[:70].replace("\n", " ")
            print(f"{i:>4} {r.status_code:>6} {dt:>8.3f} {retry:>7}  {note}")
            status_counts[r.status_code] = status_counts.get(r.status_code, 0) + 1
        except requests.exceptions.RequestException as e:
            dt = time.perf_counter() - t0
            print(f"{i:>4} {'ERR':>6} {dt:>8.3f}     -   {type(e).__name__}: {e}")
            status_counts["ERR"] = status_counts.get("ERR", 0) + 1
        if pause:
            time.sleep(pause)

    total = time.time() - start_all
    print("-" * 60)
    print("\nSummary:")
    for k, v in sorted(status_counts.items()):
        print(f"  HTTP {k}: {v}")
    if count:
        print(f"  Total: {total:.2f}s  |  avg {(total / count) * 1000:.0f}ms/req")


if __name__ == "__main__":
    main()