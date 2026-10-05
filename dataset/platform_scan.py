#!/usr/bin/env python3
"""
Stage 2b: fill in the ``platform`` column.

A path-traversal CVE is frequently *platform-specific*: the guard that the patch
adds only matters because a path primitive behaves differently on Windows than on
POSIX. ``os.path.isabs("/x")`` is False on Windows, ``\\`` is a separator only on
Windows, ``os.sep`` differs. Running such a sample on macOS or Linux can only ever
produce a false negative -- the agent is being graded on the operating system, not
on its own ability.

This stage screens the patch diff for the markers of that dependence and records

    any      -- no platform-specific primitive touched
    windows  -- the patch is about Windows path semantics
    check    -- a platform primitive is touched but the direction is unclear

``check`` is deliberately not a verdict. The marker says the patch *touches*
platform-specific code; whether the vulnerability is actually unreachable on the
host still needs the diff read by a human.

Reuses the .cache/gh responses written by enrich_functions.py, so a rescan is free.

Usage:
    python dataset/platform_scan.py --tier A
    python dataset/platform_scan.py --cwe CWE-22 --limit 50
"""

import argparse
import csv
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CACHE = Path(__file__).parent / ".cache" / "gh"

# A path primitive whose behaviour differs between Windows and POSIX.
# Note \\ in a *string or regex literal* is ambiguous -- it is a path separator in
# some patches and a CSS/regex escape in others (lxml-html-clean), so a hit here
# yields "check", never "windows", unless the commit message agrees.
CODE_MARKERS = re.compile(
    r"""\\\\{1,2}['"]|os\.sep|os\.altsep|os\.name|ntpath|win32|sys\.platform"""
    r"""|\bisabs\b|_os_alt_seps|splitdrive|\bdrive\b""")
TITLE_MARKERS = re.compile(r"windows|win32", re.I)


def api(repo: str, sha: str):
    f = CACHE / (repo.replace("/", "_") + "_" + sha + ".json")
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    out = subprocess.run(["gh", "api", f"repos/{repo}/commits/{sha}"],
                         capture_output=True, text=True)
    if out.returncode:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(out.stdout)
    return json.loads(out.stdout)


def classify(row: dict) -> tuple:
    """-> (platform, evidence)"""
    repo = "/".join(row["repo_url"].rstrip("/").split("/")[-2:])
    d = api(repo, row["patch_commit"])
    if not d:
        return "", ""
    title = d["commit"]["message"].splitlines()[0]
    code = set()
    for f in d.get("files", []):
        fn = f["filename"]
        if not fn.endswith(".py") or "test" in fn.lower():
            continue
        for ln in f.get("patch", "").splitlines():
            if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---")):
                code |= set(CODE_MARKERS.findall(ln))
    in_title = bool(TITLE_MARKERS.search(title))
    evidence = ";".join(sorted(code)) + (" |title" if in_title else "")
    if in_title:
        return "windows", evidence.strip()
    if code:
        return "check", evidence.strip()
    return "any", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=Path(__file__).parent / "dataset.csv")
    ap.add_argument("--tier", default="")
    ap.add_argument("--cwe", default="", help="only rows carrying this CWE, e.g. CWE-22")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv)))
    fields = list(rows[0].keys())
    for col in ("platform", "platform_evidence"):
        if col not in fields:
            fields.append(col)
            for r in rows:
                r[col] = ""

    todo = [r for r in rows
            if r["patch_commit"]
            and not r.get("platform")
            and (not args.tier or r["pbt_tier"] == args.tier)
            and (not args.cwe or args.cwe in r["cwe_ids"].split(";"))]
    if args.limit:
        todo = todo[:args.limit]
    print(f"scanning {len(todo)} rows", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for r, (plat, ev) in zip(todo, ex.map(classify, todo)):
            r["platform"], r["platform_evidence"] = plat, ev

    with open(args.csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    c = Counter(r["platform"] for r in todo)
    print(f"any={c['any']}  check={c['check']}  windows={c['windows']}  unresolved={c['']}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
