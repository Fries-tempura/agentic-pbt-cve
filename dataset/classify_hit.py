#!/usr/bin/env python3
"""
Decide, for one `/hypo` run, whether the agent found the CVE the sample is about.

Reading 50 run summaries by hand is not practical, and the signal is actually quite
mechanical: a run that found the CVE names the vulnerable function, and usually also
names the defect in the same words the patch does. So score three independent signals
and report them separately rather than collapsing them -- a run that trips only one
still wants a human look.

    cve        the agent wrote the CVE id (strong, but only fires when the model
               happens to recognise the advisory from memory)
    func       a bug report targets a function the patch touched
    keyword    the summary uses words lifted from the patch's own added lines

Usage:
    python dataset/classify_hit.py --run runs/black --cve CVE-2024-21503
    python dataset/classify_hit.py --all            # every run dir named in samples*.tsv
"""

import argparse
import csv
import glob
import json
import re
from pathlib import Path

HERE = Path(__file__).parent


def run_text(run: Path) -> tuple:
    """-> (final summary, concatenated bug reports)"""
    res = run / "claude_result.json"
    summary = ""
    if res.exists() and res.stat().st_size:
        try:
            summary = json.loads(res.read_text()).get("result") or ""
        except Exception:
            pass
    reports = "\n".join(p.read_text(errors="replace")
                        for p in run.glob("bug_report*.md"))
    return summary, reports


# What the defect *is*, keyed by CWE. Naming the function the patch touched is not
# enough on its own -- an agent that reports a different bug in that same function
# names it too (configobj and eml-parser both did). Pairing the function with the
# defect's own vocabulary is what separates "found it" from "was in the area".
CWE_WORDS = {
    "CWE-1333": ["redos", "backtrack", "quadratic", "exponential", "catastrophic",
                 "超线性", "denial of service", "slow", "cubic", "linear time"],
    "CWE-400":  ["redos", "quadratic", "exhaust", "unbounded", "denial of service"],
    "CWE-22":   ["traversal", "outside", "escape", "../", "..\\", "parent director"],
    "CWE-23":   ["traversal", "outside", "../"],
    "CWE-36":   ["traversal", "absolute path"],
    "CWE-73":   ["traversal", "arbitrary file"],
    "CWE-116":  ["encod", "entit", "unescape", "escap", "normaliz", "decod"],
    "CWE-838":  ["encod", "escap"],
    "CWE-172":  ["encod", "normaliz", "decod"],
    "CWE-176":  ["unicode", "normaliz", "collid", "collision"],
    "CWE-190":  ["overflow", "size limit", "bomb", "unbounded", "exceeds"],
    "CWE-191":  ["underflow", "negative", "boundary"],
    "CWE-789":  ["memory", "bomb", "size limit", "unbounded"],
    "CWE-444":  ["smuggl", "chunk", "terminator", "content-length", "transfer-encoding"],
    "CWE-295":  ["certificate", "verif", "hostname", "tls", "ssl"],
    "CWE-297":  ["hostname", "certificate"],
    "CWE-601":  ["redirect", "open redirect", "same origin", "外部"],
    "CWE-20":   ["validat", "reject", "accepts"],
}


def classify(run: Path, row: dict) -> dict:
    summary, reports = run_text(run)
    blob = (summary + "\n" + reports)
    low = blob.lower()

    cve = row["cve_id"]
    hit_cve = cve.lower() in low

    # the bare function names the patch touched, e.g. "_safe_file_name"
    funcs = [spec.split("::")[-1].split(".")[-1]
             for spec in row.get("vuln_functions", "").split(";") if spec]
    hit_func = [f for f in funcs if f and f in blob]

    words = []
    for cwe in row.get("cwe_ids", "").split(";"):
        words += CWE_WORDS.get(cwe, [])
    hit_words = sorted({w for w in words if w in low})

    # Naming the advisory is decisive on its own; otherwise require both the right
    # function and the right vocabulary.
    verdict = "hit" if hit_cve or (hit_func and hit_words) else "miss"

    return {
        "run": run.name,
        "cve_id": cve,
        "package": row["package_name"],
        "ran": bool(summary),
        "n_reports": len(list(run.glob("bug_report*.md"))),
        "cve_named": hit_cve,
        "funcs_named": ";".join(hit_func),
        "defect_words": ";".join(hit_words[:3]),
        "verdict": verdict,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path)
    ap.add_argument("--cve")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dataset", type=Path, default=HERE / "dataset.csv")
    ap.add_argument("--csv", type=Path)
    args = ap.parse_args()

    rows = {r["cve_id"]: r for r in csv.DictReader(open(args.dataset))}

    jobs = []
    if args.all:
        root = HERE.parent
        for tsv in sorted((root / "runs").glob("samples*.tsv")):
            for line in tsv.read_text().splitlines():
                if not line.strip():
                    continue
                name, _mod, _venv, _ckt, cve = line.split("\t")
                for d in sorted(glob.glob(str(root / "runs" / f"{name}")) +
                                glob.glob(str(root / "runs" / f"{name}_r*"))):
                    jobs.append((Path(d), cve))
    else:
        jobs = [(args.run, args.cve)]

    out = []
    for run, cve in jobs:
        if not run.exists() or cve not in rows:
            continue
        out.append(classify(run, rows[cve]))

    w = max((len(o["run"]) for o in out), default=12)
    print(f"{'run':{w}} {'包':14} {'报告':4} {'CVE':4} {'函数':20} {'缺陷词':22} 判定")
    print("-" * (w + 70))
    for o in sorted(out, key=lambda x: (x["package"], x["run"])):
        print(f"{o['run']:{w}} {o['package']:14} {o['n_reports']:<4} "
              f"{'✔' if o['cve_named'] else '':4} {o['funcs_named'][:20]:20} "
              f"{o['defect_words'][:22]:22} {o['verdict']}")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            wr.writeheader()
            wr.writerows(out)
        print(f"\n已写入 {args.csv}")


if __name__ == "__main__":
    main()
