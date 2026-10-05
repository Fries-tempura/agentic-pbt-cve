#!/usr/bin/env python3
"""
Stage 2: fill in vuln_functions / n_vuln_functions from the patch diff.

For each row's patch_commit we ask the GitHub API for the diff, work out which
lines of each touched ``.py`` file the patch changed, then AST-parse that file
*as it was before the patch* and report the enclosing function for each changed
line. The pre-patch file is the right side to parse: those are the functions the
agent will be pointed at, and a pure-addition patch (the common shape for a
missing-validation CVE) has no post-patch counterpart for its insertion point.

Also records how big the patch is, which is the cheapest signal for throwing out
bad samples -- a 40-file commit is a release merge, not a fix worth testing.

Needs `gh` on PATH and authenticated. Responses are cached under .cache/gh so a
run can be interrupted and resumed for free.

Usage:
    python dataset/enrich_functions.py --limit 30 --tier A
    python dataset/enrich_functions.py --workers 8
"""

import argparse
import ast
import base64
import csv
import json
import re
import subprocess
import sys
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CACHE_DIR = Path(__file__).parent / ".cache" / "gh"
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

_print_lock = threading.Lock()


def gh_api(path: str, raw: bool = False) -> bytes | None:
    """Call the GitHub API through `gh`, caching the response body on disk."""
    key = re.sub(r"[^A-Za-z0-9._-]", "_", path)[:180] + (".raw" if raw else ".json")
    cached = CACHE_DIR / key
    if cached.exists():
        data = cached.read_bytes()
        return None if data == b"__404__" else data

    cmd = ["gh", "api"]
    if raw:
        cmd += ["-H", "Accept: application/vnd.github.raw"]
    cmd.append(path)
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if r.returncode != 0:
        # 404/409 are expected: repos get renamed, deleted, or the sha was GC'd.
        cached.write_bytes(b"__404__")
        return None
    cached.write_bytes(r.stdout)
    return r.stdout


TEST_PATH = re.compile(
    r"(^|/)(tests?|testing|integration_tests|functional_tests|benchmarks?|docs?|"
    r"examples?|migrations)/|(^|/)(test_[^/]*|[^/]*_test|conftest|setup)\.py$", re.I)


def is_test_path(path: str) -> bool:
    """A fix commit almost always touches its own regression test.

    Those functions are not the vulnerability, so pointing the agent at them would
    be worse than useless -- it would hand it the oracle. Excluded from
    vuln_functions but counted separately, since shipping a test alongside the fix
    is a good sign the commit really is the fix.
    """
    return bool(TEST_PATH.search(path))


def changed_old_lines(patch: str) -> set[int]:
    """Old-side line numbers the patch touches.

    A deleted or modified line contributes its own old line number. A pure
    insertion contributes the old line it lands in front of, so that a patch which
    only *adds* a guard still resolves to the function being guarded.
    """
    touched: set[int] = set()
    old = 0
    for line in patch.splitlines():
        m = HUNK.match(line)
        if m:
            old = int(m.group(1))
            continue
        if line.startswith("-"):
            touched.add(old)
            old += 1
        elif line.startswith("+"):
            touched.add(max(1, old))
        elif line.startswith("\\"):
            continue
        else:
            old += 1
    return touched


def function_spans(source: str):
    """(start, end, qualname, kind) for every def/class, innermost last."""
    try:
        with warnings.catch_warnings():
            # Old target files are full of "\d" in non-raw strings; not our problem.
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return []
    spans = []

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{child.name}"
                start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                end = getattr(child, "end_lineno", child.lineno)
                kind = "class" if isinstance(child, ast.ClassDef) else "func"
                spans.append((start, end, name, kind))
                walk(child, name + ".")
            else:
                walk(child, prefix)

    walk(tree, "")
    # Innermost (narrowest span) last so it wins when spans nest.
    spans.sort(key=lambda s: s[1] - s[0], reverse=True)
    return spans


def resolve_functions(source: str, lines: set[int]) -> list[str]:
    """Innermost enclosing def for each changed line, falling back to the class.

    A changed line sitting directly in a class body -- the shape a ReDoS fix takes
    when the regex is a class constant, e.g. configobj's
    ``Validator._func_re = re.compile(...)`` -- has no enclosing function at all.
    Dropping those rows loses a whole class of real samples, and the class is a
    perfectly good target to point the agent at, so name it instead.
    """
    spans = function_spans(source)
    found: dict[str, None] = {}
    for ln in sorted(lines):
        best = best_class = None
        for start, end, name, kind in spans:
            if start <= ln <= end:
                if kind == "func":
                    best = name          # later spans are narrower -> innermost wins
                else:
                    best_class = name
        if best:
            found.setdefault(best, None)
        elif best_class:
            found.setdefault(best_class, None)
    return list(found)


def enrich_one(row: dict) -> dict:
    sha, repo = row["patch_commit"], row["repo_url"]
    out = {"vuln_functions": "", "n_vuln_functions": "0", "changed_py_files": "",
           "n_changed_files": "", "patch_lines": "", "enrich_status": "",
           "n_test_files": "0", "n_nested_functions": "0"}
    if not sha or "github.com/" not in repo:
        out["enrich_status"] = "no_commit"
        return out
    slug = repo.split("github.com/", 1)[1].strip("/")

    body = gh_api(f"repos/{slug}/commits/{sha}")
    if body is None:
        out["enrich_status"] = "commit_unreachable"
        return out
    try:
        commit = json.loads(body)
    except json.JSONDecodeError:
        out["enrich_status"] = "bad_json"
        return out

    parents = [p["sha"] for p in commit.get("parents", [])]
    if not parents:
        out["enrich_status"] = "no_parent"
        return out
    if len(parents) > 1:
        # A merge commit was previously dropped for having no single "before"
        # state, but the common shape here is a PR merged into the mainline, and
        # for that `sha^1` IS the vulnerable mainline immediately before the fix
        # -- the diff GitHub reports for the merge is already the PR's net change
        # against that parent. Take the first parent and record that we did.
        # Verified on dparse / configobj / h11 / soupsieve: the checkout at `sha^1`
        # contains the pre-patch code in every case.
        out["enrich_status"] = "ok_merge"
    parent = parents[0]

    files = commit.get("files") or []
    out["n_changed_files"] = str(len(files))
    out["patch_lines"] = str(sum(f.get("changes", 0) for f in files))

    py_files, funcs, test_files = [], [], []
    for f in files:
        path = f.get("filename", "")
        if not path.endswith(".py") or f.get("status") == "added":
            continue
        if is_test_path(path):
            test_files.append(path)
            continue
        patch = f.get("patch")
        if not patch:
            continue  # too large for the API to inline
        py_files.append(path)
        lines = changed_old_lines(patch)
        if not lines:
            continue
        src = gh_api(f"repos/{slug}/contents/{path}?ref={parent}", raw=True)
        if src is None:
            continue
        try:
            text = src.decode("utf-8", "replace")
        except Exception:
            continue
        for name in resolve_functions(text, lines):
            funcs.append(f"{path}::{name}")

    out["changed_py_files"] = ";".join(py_files)
    out["n_test_files"] = str(len(test_files))
    uniq = list(dict.fromkeys(funcs))
    out["vuln_functions"] = ";".join(uniq)
    out["n_vuln_functions"] = str(len(uniq))
    # Nested defs (a lowercase qualname parent, i.e. a closure rather than a class)
    # are not reachable from the public API, so they make poor PBT targets.
    out["n_nested_functions"] = str(sum(
        1 for q in uniq
        if any(p[:1].islower() for p in q.split("::")[-1].split(".")[:-1])))
    if funcs:
        # keep the ok_merge marker set above, if any
        if out.get("enrich_status") != "ok_merge":
            out["enrich_status"] = "ok"
    elif not py_files:
        out["enrich_status"] = "no_py_change" if not test_files else "test_only_change"
    else:
        out["enrich_status"] = "no_func_resolved"
    return out


NEW_COLS = ["changed_py_files", "n_changed_files", "patch_lines", "enrich_status",
            "n_test_files", "n_nested_functions"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, default=Path(__file__).parent / "dataset.csv")
    ap.add_argument("--out", type=Path, default=None, help="default: overwrite --csv")
    ap.add_argument("--tier", default="", help="only enrich these tiers, e.g. A")
    ap.add_argument("--cve", default="", help="comma-separated CVE ids; overrides --tier")
    ap.add_argument("--limit", type=int, default=0, help="only enrich the first N matching rows")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8")))
    fields = list(rows[0].keys()) + [c for c in NEW_COLS if c not in rows[0]]

    tiers = {t.strip().upper() for t in args.tier.split(",") if t.strip()}
    cves = {c.strip().upper() for c in args.cve.split(",") if c.strip()}
    if cves:
        # an explicit CVE list is a re-run request: ignore enrich_status so a row
        # can be refreshed, and ignore --tier.
        todo = [r for r in rows if r["cve_id"].upper() in cves]
    else:
        todo = [r for r in rows if (not tiers or r["pbt_tier"] in tiers)
                and r.get("enrich_status", "") == ""]
    if args.limit:
        todo = todo[:args.limit]
    print(f"enriching {len(todo)} of {len(rows)} rows with {args.workers} workers")

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(enrich_one, r): r for r in todo}
        for fut in as_completed(futs):
            row = futs[fut]
            try:
                row.update(fut.result())
            except Exception as e:
                row["enrich_status"] = f"error:{str(e)[:40]}"
            done += 1
            with _print_lock:
                print(f"[{done}/{len(todo)}] {row['cve_id'] or row['ghsa_id']:18s} "
                      f"{row['package_name']:20s} {row['enrich_status']:18s} "
                      f"n_func={row['n_vuln_functions']} {row['vuln_functions'][:70]}")

    out = args.out or args.csv
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    print(f"\nwrote {out}")

    import collections
    st = collections.Counter(r.get("enrich_status", "") for r in rows if r.get("enrich_status"))
    print("status:", dict(st))
    ok = [r for r in rows if r.get("enrich_status") == "ok"]
    if ok:
        print(f"resolved functions for {len(ok)} rows; "
              f"median funcs/row={sorted(int(r['n_vuln_functions']) for r in ok)[len(ok)//2]}")


if __name__ == "__main__":
    main()
