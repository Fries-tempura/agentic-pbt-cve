#!/usr/bin/env python3
"""
Collapse N repeated runs per sample into one row, and say how stable each sample is.

A single run tells you almost nothing: the same correct property measured a 33% hit rate
on litestar, so one miss is as likely to be a bad draw as a real limitation. Repeating
each sample and reporting the hit *count* is what separates "the agent cannot do this"
from "the agent did not do this that time" -- and those two want completely different
fixes.

Per-run hit/miss comes from classify_hit.py, which over-reports: its misses are reliable,
its hits are not. So `--review` prints the summary of every run it called a hit, for a
human to confirm, and `--overrides` reads the corrections back in.

Usage:
    python dataset/aggregate.py
    python dataset/aggregate.py --review
    python dataset/aggregate.py --overrides dataset/hit_overrides.csv --csv dataset/table3_stability.csv
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent


def load_samples() -> dict:
    out = {}
    for tsv in sorted((ROOT / "runs").glob("samples*.tsv")):
        for line in tsv.read_text().splitlines():
            if not line.strip():
                continue
            name, mod, venv, ckt, cve = line.split("\t")
            out[name] = {"module": mod, "venv": venv, "checkout": ckt, "cve": cve}
    return out


def run_dirs(name: str):
    base = ROOT / "runs" / name
    dirs = ([base] if base.exists() else []) + sorted((ROOT / "runs").glob(f"{name}_r*"))
    return [d for d in dirs
            if (d / "claude_result.json").exists()
            and (d / "claude_result.json").stat().st_size]


def summary_of(d: Path) -> str:
    try:
        return json.loads((d / "claude_result.json").read_text()).get("result") or ""
    except Exception:
        return ""


def stability(hits: int, n: int) -> str:
    if n == 0:
        return "未跑"
    if hits == n:
        return "稳定命中"
    if hits == 0:
        return "从未命中"
    return "不稳定"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=HERE / "hit_raw.csv")
    ap.add_argument("--overrides", type=Path)
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--csv", type=Path)
    args = ap.parse_args()

    auto = {}
    if args.raw.exists():
        for r in csv.DictReader(open(args.raw)):
            auto[r["run"]] = r["verdict"]
    if args.overrides and args.overrides.exists():
        for r in csv.DictReader(open(args.overrides)):
            auto[r["run"]] = r["verdict"]

    rows = []
    for name, meta in sorted(load_samples().items()):
        dirs = run_dirs(name)
        verdicts = [auto.get(d.name, "?") for d in dirs]
        hits = verdicts.count("hit")
        n = len([v for v in verdicts if v in ("hit", "miss")])
        rows.append({"sample": name, "cve": meta["cve"], "n_runs": n, "hits": hits,
                     "rate": f"{hits}/{n}" if n else "-",
                     "stability": stability(hits, n),
                     "dirs": [d.name for d in dirs]})

    if args.review:
        for r in rows:
            for dn in r["dirs"]:
                if auto.get(dn) != "hit":
                    continue
                print(f"\n### {dn}  [{r['cve']}]")
                print("    " + " ".join(summary_of(ROOT / "runs" / dn)[:300].split()))
        return

    print(f"{'样本':20}{'CVE':17}{'跑数':5}{'命中':5}{'命中率':8}{'稳定性':10}")
    print("-" * 68)
    for r in sorted(rows, key=lambda x: (-x["hits"], x["sample"])):
        print(f"{r['sample']:20}{r['cve']:17}{r['n_runs']:<5}{r['hits']:<5}"
              f"{r['rate']:8}{r['stability']:10}")
    tn = sum(r["n_runs"] for r in rows)
    th = sum(r["hits"] for r in rows)
    print("-" * 68)
    print(f"{len(rows)} 个样本    {th}/{tn} = {100*th//max(tn,1)}%")
    by = defaultdict(int)
    for r in rows:
        by[r["stability"]] += 1
    print("  " + "   ".join(f"{k} {v}" for k, v in sorted(by.items())))

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["sample", "cve", "n_runs", "hits",
                                              "rate", "stability"],
                               extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"\n已写入 {args.csv}")


if __name__ == "__main__":
    main()
