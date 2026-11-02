#!/usr/bin/env python3
"""
Stage 1b: GitLab Advisory Database (gemnasium-db) -> rows in dataset.csv's format.

A second, independently curated source. Everything so far came from one place --
the GitHub Advisory Database -- and a single curator has its own selection bias:
which ecosystems it staffs, which reports it reviews, what it declines. Any result
measured on one source alone may hold only on that source.

GitLab's Vulnerability Research team reviews separately, and the overlap is partial:
of its 3841 PyPI advisories carrying a GitHub fix commit, 1787 are absent from the
GitHub export we already use.

Two wrinkles compared with the OSV export:

  * The fix commit has no field of its own. It sits in the untyped ``urls`` list
    beside NVD, GHSA and bounty links, so it has to be matched out by shape.
  * Every entry carries CWE-937 and CWE-1035 ("uses components with known
    vulnerabilities"). Those are not defect classes, they are a property of every
    advisory, so they are dropped before tiering -- left in, every row tiers as C.

Usage:
    git clone --depth 1 https://gitlab.com/gitlab-org/security-products/gemnasium-db
    python dataset/build_gitlab.py --db ./gemnasium-db --out dataset/gitlab.csv
    python dataset/build_gitlab.py --db ./gemnasium-db --only-new   # skip what we have
"""

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_dataset import FIELDS, RE_COMMIT, norm_repo, tier_of   # noqa: E402

HERE = Path(__file__).parent

# Present on every single entry, so they carry no information about the defect.
META_CWE = {"CWE-937", "CWE-1035", "CWE-1104"}

RE_FIELD = re.compile(r'^(\w+):\s*"?(.*?)"?\s*$', re.M)
RE_LIST = re.compile(r'^\s*-\s*"?(.+?)"?\s*$', re.M)
RE_CVE = re.compile(r"CVE-\d{4}-\d{4,}", re.I)
RE_GHSA = re.compile(r"GHSA-[\w-]{14,}", re.I)


def block(text: str, key: str) -> list[str]:
    """The list items under ``key:``, up to the next top-level key.

    gemnasium-db writes sequence items flush left, not indented::

        urls:
        - "https://..."

    so "ends at the next unindented line" would end the block at its own first
    item. The terminator has to be the next ``key:`` instead.
    """
    m = re.search(rf"^{key}:\s*$(.*?)(?=^\w[\w.-]*:|\Z)", text, re.M | re.S)
    return RE_LIST.findall(m.group(1)) if m else []


def scalar(text: str, key: str) -> str:
    m = re.search(rf'^{key}:\s*"?(.*?)"?\s*$', text, re.M)
    return m.group(1) if m else ""


def parse(path: Path) -> dict | None:
    text = path.read_text(errors="replace")
    urls = block(text, "urls")
    commits = [m for u in urls for m in [RE_COMMIT.search(u)] if m]
    if not commits:
        return None                      # no fix commit -> nothing to check out
    owner, repo, sha = commits[0].groups()
    if len(sha) < 40:
        # A short sha still resolves, but only against a full clone; the pipeline
        # wants to check out before cloning, so keep only unambiguous ones.
        return None

    ids = set(block(text, "identifiers")) | {scalar(text, "identifier")}
    cves = sorted({i.upper() for i in ids if RE_CVE.fullmatch(i)})
    ghsa = next((i for i in ids if RE_GHSA.fullmatch(i)), "")
    cwes = [c for c in block(text, "cwe_ids") if c not in META_CWE]
    fixed = block(text, "fixed_versions")

    return {
        "cve_id": cves[0] if cves else "",
        "package_name": path.parent.name,
        "repo_url": norm_repo(owner, repo),
        "patch_commit": sha,
        "affected_ranges": scalar(text, "affected_range"),
        "vuln_functions": "", "n_vuln_functions": "0",
        "clone_path": "", "checkout_ref": f"{sha}^",
        "ghsa_id": ghsa,
        "pbt_tier": tier_of(cwes),
        "cwe_ids": ";".join(cwes),
        "severity": scalar(text, "cvss_v3"),
        "published": scalar(text, "date"),
        "summary": scalar(text, "title"),
        "fixed_version": fixed[0] if fixed else "",
        "vuln_version": "", "n_affected_versions": "",
        "all_patch_commits": ";".join(m.group(3) for m in commits),
        "foreign_commits": "", "pr_refs": "",
        "all_cves": ";".join(cves),
        "source": "gitlab",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, required=True, help="clone of gemnasium-db")
    ap.add_argument("--out", type=Path, default=HERE / "gitlab.csv")
    ap.add_argument("--existing", type=Path, default=HERE / "dataset.csv")
    ap.add_argument("--only-new", action="store_true",
                    help="drop CVEs already present in --existing")
    ap.add_argument("--package", default="", help="comma-separated package names")
    args = ap.parse_args()

    have = set()
    if args.existing.exists():
        have = {r["cve_id"].upper()
                for r in csv.DictReader(open(args.existing, encoding="utf-8"))
                if r["cve_id"]}

    want = {p.strip().lower() for p in args.package.split(",") if p.strip()}
    rows, skipped_nofix, skipped_dup = [], 0, 0
    for p in sorted((args.db / "pypi").rglob("*.yml")):
        if want and p.parent.name.lower() not in want:
            continue
        r = parse(p)
        if r is None:
            skipped_nofix += 1
            continue
        if args.only_new and r["cve_id"].upper() in have:
            skipped_dup += 1
            continue
        rows.append(r)

    # One CVE can have an entry per affected package name; keep the first.
    seen, uniq = set(), []
    for r in rows:
        key = r["cve_id"] or r["patch_commit"]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)

    fields = FIELDS + ["source"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in uniq:
            w.writerow({k: r.get(k, "") for k in fields})

    import collections
    t = collections.Counter(r["pbt_tier"] for r in uniq)
    print(f"无补丁提交而跳过 {skipped_nofix} 条" +
          (f",已有而跳过 {skipped_dup} 条" if args.only_new else ""))
    print(f"写出 {args.out}:{len(uniq)} 条")
    print(f"分级: A={t['A']} B={t['B']} C={t['C']}")
    c = collections.Counter(r["package_name"] for r in uniq if r["pbt_tier"] == "A")
    print("A 级最多的包:", ", ".join(f"{k}({v})" for k, v in c.most_common(10)))


if __name__ == "__main__":
    main()
