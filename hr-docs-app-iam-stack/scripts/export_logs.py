#!/usr/bin/env python3
"""Xuất log ứng dụng (đúng log schema) từ Loki ra file JSON cho TV3.

    python scripts/export_logs.py --since 2h --out logs.json
    python scripts/export_logs.py --scenario S1-idor --out s1.json          # chỉ log tấn công của 1 kịch bản
    python scripts/export_logs.py --job kong --since 30m --out kong.json     # log gateway / --job opa: decision log

Mặc định trả về mảng JSON, mỗi phần tử là một bản ghi log nguyên gốc. Chỉ dùng thư viện chuẩn.
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request

UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_since(s: str) -> int:
    m = re.fullmatch(r"(\d+)([smhd])", s)
    if not m:
        raise SystemExit("--since dạng 30m, 2h, 1d")
    return int(m.group(1)) * UNITS[m.group(2)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loki", default="http://localhost:3100")
    ap.add_argument("--job", default="hrdocs-api", choices=["hrdocs-api", "kong", "opa"])
    ap.add_argument("--since", default="1h")
    ap.add_argument("--scenario", help="lọc theo scenario_id (chỉ với job hrdocs-api)")
    ap.add_argument("--query", help="LogQL tùy ý, ghi đè --job/--scenario")
    ap.add_argument("--out", default="-", help="file đích (mặc định stdout)")
    ap.add_argument("--jsonl", action="store_true", help="xuất JSON Lines thay vì mảng JSON")
    args = ap.parse_args()

    query = args.query or f'{{job="{args.job}"}}'
    if not args.query and args.scenario:
        query += f' | json | scenario_id="{args.scenario}"'

    end_ns = time.time_ns()
    start_ns = end_ns - parse_since(args.since) * 10**9
    rows = []
    while True:  # phân trang: Loki trả tối đa `limit` dòng mỗi lần
        qs = urllib.parse.urlencode({"query": query, "start": start_ns, "end": end_ns, "limit": 5000, "direction": "forward"})
        with urllib.request.urlopen(f"{args.loki}/loki/api/v1/query_range?{qs}") as res:
            streams = json.load(res)["data"]["result"]
        batch = sorted(((int(ts), line) for s in streams for ts, line in s["values"]), key=lambda x: x[0])
        rows += batch
        if len(batch) < 5000:
            break
        start_ns = batch[-1][0] + 1

    records = []
    for _, line in rows:
        try:
            records.append(json.loads(line))
        except ValueError:
            records.append({"raw": line})

    out = sys.stdout if args.out == "-" else open(args.out, "w", encoding="utf-8")
    if args.jsonl:
        for r in records:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    else:
        json.dump(records, out, ensure_ascii=False, indent=2)
    if out is not sys.stdout:
        out.close()
        print(f"Đã xuất {len(records)} bản ghi ({query}) -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
