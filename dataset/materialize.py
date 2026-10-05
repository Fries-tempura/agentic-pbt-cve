#!/usr/bin/env python3
"""
Stage 3: clone each project and check out the code as it was *before* the patch.

The agent has to be pointed at vulnerable code, so the checkout target is
``patch_commit^`` -- the parent of the fix -- not the fix itself. Stage 2 already
dropped merge commits, so that parent is unambiguous here.

Clones are shallow (``--depth 2``: the fix plus its parent) and one checkout is
made per row, which keeps a few hundred samples in the low single-digit GB even
for repos like Django or Salt.

Usage:
    python dataset/materialize.py --limit 5
    python dataset/materialize.py --tier A --workers 4
"""

import argparse
import csv
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CHECKOUTS = Path(__file__).parent / "checkouts"
_lock = threading.Lock()


def run(cmd, cwd=None, timeout=600):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def safe_name(row) -> str:
    ident = row["cve_id"] or row["ghsa_id"]
    return f"{ident}__{row['package_name']}".replace("/", "_")


def materialize_one(row: dict, force: bool) -> dict:
    out = {"clone_path": "", "vuln_commit": "", "materialize_status": ""}
    sha, repo = row["patch_commit"], row["repo_url"]
    if not sha or "github.com/" not in repo:
        out["materialize_status"] = "no_commit"
        return out

    dest = CHECKOUTS / safe_name(row)
    if dest.exists() and not force:
        r = run(["git", "rev-parse", "HEAD"], cwd=dest)
        if r.returncode == 0:
            out.update(clone_path=str(dest.relative_to(Path(__file__).parent)),
                       vuln_commit=r.stdout.strip(), materialize_status="cached")
            return out
        shutil.rmtree(dest, ignore_errors=True)
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)

    dest.mkdir(parents=True, exist_ok=True)
    if run(["git", "init", "-q"], cwd=dest).returncode != 0:
        out["materialize_status"] = "init_failed"
        return out
    run(["git", "remote", "add", "origin", repo], cwd=dest)

    # Fetching a bare SHA works because GitHub enables uploadpack.allowAnySHA1InWant.
    # depth 2 is the minimum that also brings down the parent we want to check out.
    r = run(["git", "fetch", "-q", "--depth", "2", "origin", sha], cwd=dest, timeout=900)
    if r.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        out["materialize_status"] = "fetch_failed"
        return out

    r = run(["git", "rev-parse", f"{sha}^"], cwd=dest)
    if r.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        out["materialize_status"] = "no_parent"
        return out
    parent = r.stdout.strip()

    r = run(["git", "checkout", "-q", "--detach", parent], cwd=dest)
    if r.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        out["materialize_status"] = "checkout_failed"
        return out

    out.update(clone_path=str(dest.relative_to(Path(__file__).parent)),
               vuln_commit=parent, materialize_status="ok")
    return out


NEW_COLS = ["vuln_commit", "materialize_status"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, default=Path(__file__).parent / "dataset.csv")
    ap.add_argument("--tier", default="", help="only materialize these tiers")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true", help="re-clone even if present")
    ap.add_argument("--require-functions", action="store_true", default=True,
                    help="only rows where stage 2 resolved at least one function")
    ap.add_argument("--all-rows", dest="require_functions", action="store_false")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8")))
    fields = list(rows[0].keys()) + [c for c in NEW_COLS if c not in rows[0]]
    tiers = {t.strip().upper() for t in args.tier.split(",") if t.strip()}

    todo = []
    for r in rows:
        if tiers and r["pbt_tier"] not in tiers:
            continue
        if args.require_functions and r.get("enrich_status") != "ok":
            continue
        if r.get("materialize_status") in ("ok", "cached") and not args.force:
            continue
        todo.append(r)
    if args.limit:
        todo = todo[:args.limit]
    print(f"materializing {len(todo)} rows into {CHECKOUTS}")

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(materialize_one, r, args.force): r for r in todo}
        for fut in as_completed(futs):
            row = futs[fut]
            try:
                row.update(fut.result())
            except Exception as e:
                row["materialize_status"] = f"error:{str(e)[:40]}"
            done += 1
            with _lock:
                print(f"[{done}/{len(todo)}] {row['cve_id']:18s} {row['package_name']:20s} "
                      f"{row['materialize_status']:16s} {row['vuln_commit'][:12]}")

    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    print(f"\nwrote {args.csv}")

    import collections
    print("status:", dict(collections.Counter(
        r.get("materialize_status", "") for r in rows if r.get("materialize_status"))))


if __name__ == "__main__":
    main()
