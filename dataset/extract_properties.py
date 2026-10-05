#!/usr/bin/env python3
"""
Stage 4: recover the properties the agent *proposed*, not just the bugs it reported.

`hypo.md` step 3 is where the agent decides what to test, and that decision is what
separates a sample the agent can find from one it cannot. The bug report only shows
the properties that happened to fail; the ones that passed -- and the ones it never
wrote down -- are exactly the evidence needed to explain a miss.

Every proposed property ends up as a `@given`-decorated test function, so the test
files *are* the record. This stage reads the Claude Code transcript for the run,
replays the Write/Edit calls in order (so the iteration history survives, not just
the final file), AST-parses each version for `@given` functions, and joins each one
with the pytest outcome scraped from the Bash tool results.

Note on Todo: `hypo.md` asks the agent to track proposed properties with the Todo
tool, but `run.py`'s allowlist spells it `Todo` while the tool is actually named
`TodoWrite`, so that channel has never recorded anything. Todo entries are read here
when present; the test functions are the reliable source.

Usage:
    python dataset/extract_properties.py --run runs/litestar_module --cve CVE-2026-25480
    python dataset/extract_properties.py --run runs/litestar_module --cve CVE-2026-25480 --csv out.csv
"""

import argparse
import ast
import csv
import glob
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent

# columns carried over from dataset.csv, in the order asked for
META = ["cve_id", "package_name", "repo_url", "patch_commit", "affected_ranges"]
META_OPT = ["vuln_functions", "n_vuln_functions", "clone_path"]
PROP = ["prop_seq", "prop_file", "prop_name", "prop_statement",
        "prop_strategy", "prop_assertions", "prop_outcome"]


def transcript_path(run_dir: Path):
    """Claude Code stores a session under ~/.claude/projects/<cwd with / and _ as ->."""
    key = re.sub(r"[/_]", "-", str(run_dir.resolve()))
    hits = sorted(glob.glob(os.path.expanduser(f"~/.claude/projects/{key}/*.jsonl")))
    return Path(hits[-1]) if hits else None


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def replay(tp: Path):
    """-> (versions, outcomes, todos)

    versions: [(filename, source)] in the order the agent wrote them
    outcomes: {test_name: "failed"|"passed"}
    todos:    [str] any Todo entries, if the tool was ever usable

    pytest only names the failures; a pass is a bare dot. So a test is recorded as
    passing when its file was run, the run reported passes, and the test was not in
    that run's FAILED list -- which is the whole point of this stage: a property
    that passed is a formulation that missed, and that is the interesting case.
    """
    versions, todos = [], []
    cmds = {}                       # tool_use_id -> bash command
    failed, passed = set(), set()
    tests_in = {}                   # filename -> {test names seen so far}

    def note(fname, src):
        tests_in.setdefault(fname, set()).update(
            f["prop_name"] for f in given_functions(src))

    for line in tp.read_text(errors="replace").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        for c in (d.get("message") or {}).get("content") or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                name, inp = c.get("name"), c.get("input") or {}
                if name == "Write" and str(inp.get("file_path", "")).endswith(".py"):
                    fn = os.path.basename(inp["file_path"])
                    versions.append((fn, inp.get("content", "")))
                    note(fn, inp.get("content", ""))
                elif name == "Bash":
                    cmds[c.get("id")] = inp.get("command", "")
                elif name in ("TodoWrite", "Todo"):
                    for t in inp.get("todos") or []:
                        todos.append(t.get("content") or t.get("activeForm") or str(t))
            elif c.get("type") == "tool_result":
                txt = _text(c.get("content"))
                if "passed" not in txt and "failed" not in txt:
                    continue
                run_failed = {m.group(2) for m in
                              re.finditer(r"^FAILED\s+(\S+?)::(\w+)", txt, re.M)}
                failed |= run_failed
                passed |= {m.group(2) for m in
                           re.finditer(r"^(\S+\.py)::(\w+)\s+PASSED", txt, re.M)}
                if not any(re.finditer(r"(\d+)\s+passed", txt)):
                    continue
                cmd = cmds.get(c.get("tool_use_id"), "")
                ran = {f for f in tests_in if f in cmd} or set(tests_in)
                for f in ran:
                    passed |= (tests_in[f] - run_failed)

    outcomes = {t: "passed" for t in passed}
    outcomes.update({t: "failed" for t in failed})     # a failure anywhere wins
    return versions, outcomes, todos


def given_functions(src: str):
    """Every @given-decorated function in `src`, as a dict."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        given = None
        for dec in n.decorator_list:
            f = dec.func if isinstance(dec, ast.Call) else dec
            if getattr(f, "id", None) == "given" or getattr(f, "attr", None) == "given":
                given = dec
        if given is None:
            continue
        strategy = ast.unparse(given)[len("@") if False else 0:]
        doc = ast.get_docstring(n) or ""
        asserts = [ast.unparse(s.test) for s in ast.walk(n) if isinstance(s, ast.Assert)]
        out.append({
            "prop_name": n.name,
            "prop_statement": " ".join(doc.split()),
            "prop_strategy": " ".join(strategy.split()),
            "prop_assertions": " ; ".join(" ".join(a.split()) for a in asserts),
        })
    return out


def collect(run_dir: Path):
    """Properties in first-seen order, deduped on (file, name, assertions)."""
    tp = transcript_path(run_dir)
    versions, outcomes, todos = replay(tp) if tp else ([], {}, [])
    # The transcript only carries whole-file Writes; anything the agent appended with
    # Edit shows up only on disk. Append the final on-disk state so those are not
    # lost -- dedup keeps the transcript's ordering for everything already seen.
    versions += [(f.name, f.read_text(errors="replace"))
                 for f in sorted(run_dir.glob("*.py"))]
    props, seen = [], set()
    for fname, src in versions:
        for p in given_functions(src):
            key = (fname, p["prop_name"], p["prop_assertions"])
            if key in seen:
                continue
            seen.add(key)
            p["prop_file"] = fname
            p["prop_outcome"] = outcomes.get(p["prop_name"], "unknown")
            props.append(p)
    # keep the files in the order the agent first touched them, and properties in
    # the order they appear within each file -- the Edit-only ones were appended by
    # the disk merge and would otherwise all pile up at the end.
    order = {}
    for p_ in props:
        order.setdefault(p_["prop_file"], len(order))
    props.sort(key=lambda x: order[x["prop_file"]])
    for i, p_ in enumerate(props, 1):
        p_["prop_seq"] = i
    return props, todos, tp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path, help="worker dir, e.g. runs/litestar_module")
    ap.add_argument("--cve", required=True)
    ap.add_argument("--dataset", type=Path, default=HERE / "dataset.csv")
    ap.add_argument("--csv", type=Path, default=None, help="also write the table here")
    ap.add_argument("--no-optional", action="store_true", help="drop the optional columns")
    ap.add_argument("--wide", action="store_true",
                    help="repeat the metadata columns on every row (the full flat table)")
    args = ap.parse_args()

    rows = {r["cve_id"]: r for r in csv.DictReader(open(args.dataset))}
    if args.cve not in rows:
        sys.exit(f"{args.cve} not in {args.dataset}")
    meta = rows[args.cve]

    props, todos, tp = collect(args.run)
    cols = META + ([] if args.no_optional else META_OPT) + PROP
    table = [{**{k: meta.get(k, "") for k in cols if k in meta}, **p} for p in props]

    def show(rows, cols, widths):
        """Aligned table, values clipped to the given widths."""
        head = "  ".join(c[:widths[c]].ljust(widths[c]) for c in cols)
        print(head)
        print("  ".join("-" * widths[c] for c in cols))
        for r in rows:
            cells = []
            for c in cols:
                v = str(r.get(c, "") or "")
                w = widths[c]
                cells.append((v if len(v) <= w else v[:w - 1] + "…").ljust(w))
            print("  ".join(cells))

    W = {"cve_id": 15, "package_name": 10, "repo_url": 38, "patch_commit": 12,
         "affected_ranges": 17, "vuln_functions": 40, "n_vuln_functions": 3,
         "clone_path": 34, "prop_seq": 3, "prop_file": 30, "prop_name": 38,
         "prop_statement": 60, "prop_strategy": 52, "prop_assertions": 46,
         "prop_outcome": 7}

    if args.wide:
        show(table, cols, W)
    else:
        # The metadata is identical on every row, so print it once and give the
        # width to the part that differs -- one row per proposed property.
        print(f"\n{'='*100}")
        for k in META + ([] if args.no_optional else META_OPT):
            print(f"{k:<18}{meta.get(k, '') or '(空)'}")
        print(f"{'='*100}")
        print(f"{len(props)} 条 property   ·   transcript: "
              f"{tp.name if tp else '(未找到,已回退到磁盘)'}\n")
        show(props, PROP[:1] + ["prop_outcome", "prop_file", "prop_name",
                                "prop_strategy", "prop_assertions", "prop_statement"], W)
    print()

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(table)
        print(f"已写入 {args.csv}  ({len(table)} 行 × {len(cols)} 列)")


if __name__ == "__main__":
    main()
