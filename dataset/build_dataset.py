#!/usr/bin/env python3
"""
Stage 1: GitHub Advisory (OSV export) -> candidate CVE dataset for PBT.

Pulls the whole PyPI advisory corpus as one 33MB zip instead of scraping
github.com/advisories, then keeps only github-reviewed records that (a) carry a
CVE, (b) point at a fix commit in the package's own GitHub repo, and (c) fall in
a CWE class where a property-based test could plausibly witness the bug.

Usage:
    python dataset/build_dataset.py
    python dataset/build_dataset.py --tier A --out dataset/tier_a.csv
    python dataset/build_dataset.py --tier A,B,C --min-year 2018
"""

import argparse
import csv
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

OSV_URL = "https://osv-vulnerabilities.storage.googleapis.com/PyPI/all.zip"
CACHE = Path(__file__).parent / ".cache" / "PyPI_all.zip"

# ---------------------------------------------------------------------------
# PBT-suitability tiers.
#
# A: the vulnerability class itself names a property a test can assert directly
#    ("the joined path stays under base", "the redirect host is in the allowlist",
#    "match_hostname accepts iff the cert covers the host", "runtime is bounded").
# B: plausible, but only when the patched code sits on a pure-function boundary --
#    a sanitiser/parser/escaper rather than a view or a request handler. The
#    memory-safety CWEs land here because for a C extension the property is just
#    "no interpreter crash on any well-typed input", which Hypothesis is good at.
# C: everything needing multi-user state, a live request, or a network peer.
#    Kept in the CSV only when explicitly asked for, for completeness.
# ---------------------------------------------------------------------------
TIER_A = {
    "CWE-22", "CWE-23", "CWE-36",        # path traversal
    "CWE-116", "CWE-838", "CWE-172", "CWE-170",  # encoding / escaping / decoding
    "CWE-295", "CWE-297",                # cert & hostname validation
    "CWE-444",                           # request smuggling (differential PBT)
    "CWE-601",                           # open redirect
    "CWE-682", "CWE-190", "CWE-191",     # incorrect calculation / int over-underflow
    "CWE-1333",                          # ReDoS
    "CWE-1289",                          # improper validation of unsafe equivalence
}
TIER_B = {
    "CWE-20", "CWE-79", "CWE-80",        # input validation / XSS (sanitisers only)
    "CWE-400", "CWE-770", "CWE-1050",    # resource exhaustion
    "CWE-787", "CWE-125", "CWE-119", "CWE-120", "CWE-122", "CWE-131",
    "CWE-476", "CWE-617", "CWE-824", "CWE-369",  # memory safety / crash in C ext
    "CWE-502",                           # deserialisation
    "CWE-74", "CWE-77", "CWE-78", "CWE-88", "CWE-89", "CWE-90", "CWE-91",
    "CWE-94", "CWE-95", "CWE-611",       # injection families
    "CWE-347", "CWE-327", "CWE-328", "CWE-916",  # signature / weak crypto
    "CWE-59", "CWE-73",                  # link following / externally controlled path
}

RE_COMMIT = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)/commit/([0-9a-f]{7,40})", re.I)
RE_PR = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)", re.I)
RE_COMPARE = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)/compare/([^/?#\s]+)", re.I)
RE_REPO = re.compile(r"github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/?#]|$)", re.I)

# Paths under github.com that are not repositories.
NOT_A_REPO = {"advisories", "security", "pypa", "orgs", "apps", "features", "blog"}


def fetch_osv(force: bool = False) -> Path:
    """Download the PyPI advisory bundle, cached on disk."""
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE.exists() and not force:
        print(f"using cached {CACHE} ({CACHE.stat().st_size/1e6:.1f} MB)")
        return CACHE
    print(f"downloading {OSV_URL} ...")
    with urllib.request.urlopen(OSV_URL, timeout=300) as r:
        data = r.read()
    CACHE.write_bytes(data)
    print(f"saved {CACHE} ({len(data)/1e6:.1f} MB)")
    return CACHE


# --- PEP 440-ish version ordering -----------------------------------------
# Only needs to be good enough to pick the newest affected release; a full
# packaging.version dependency is not worth it for a stdlib-only script.
_PRE = re.compile(r"(a|b|c|rc|alpha|beta|pre|preview|dev)", re.I)


def version_key(v: str):
    nums = [int(x) for x in re.findall(r"\d+", v)[:5]]
    nums += [0] * (5 - len(nums))
    return (0 if _PRE.search(v) else 1, tuple(nums))


def is_prerelease(v: str) -> bool:
    return bool(_PRE.search(v))


def tier_of(cwes) -> str:
    s = set(cwes or [])
    if s & TIER_A:
        return "A"
    if s & TIER_B:
        return "B"
    return "C"


def norm_repo(owner: str, repo: str) -> str:
    return f"https://github.com/{owner}/{repo}"


def extract_repo_url(rec) -> str | None:
    """Best-effort canonical GitHub repo for the advisory.

    Prefer the PACKAGE-typed reference (that is the upstream source GitHub links
    from the package page); otherwise fall back to whichever repo the fix commits
    live in.
    """
    refs = rec.get("references", [])
    for want in ("PACKAGE", "SOURCE_CODE"):
        for r in refs:
            if r.get("type") != want:
                continue
            m = RE_REPO.search(r["url"])
            if m and m.group(1).lower() not in NOT_A_REPO:
                return norm_repo(m.group(1), m.group(2))
    for r in refs:
        m = RE_COMMIT.search(r["url"])
        if m and m.group(1).lower() not in NOT_A_REPO:
            return norm_repo(m.group(1), m.group(2))
    return None


def extract_fixes(rec, repo_url: str | None):
    """Fix commits, PRs and compare links found in the advisory references.

    Commits are split into those landing in the package's own repo and those
    elsewhere (distro patches, forks, oss-security mirrors). Only the former are
    trustworthy enough to checkout, so they are what ends up in patch_commit.
    """
    own, foreign, prs = [], [], []
    slug = repo_url.lower().rsplit("github.com/", 1)[-1] if repo_url else None
    for r in rec.get("references", []):
        url = r["url"]
        m = RE_COMMIT.search(url)
        if m:
            owner, repo, sha = m.group(1), m.group(2), m.group(3).lower()
            if owner.lower() in NOT_A_REPO:
                continue
            entry = (f"{owner}/{repo}", sha)
            (own if slug and entry[0].lower() == slug else foreign).append(entry)
            continue
        m = RE_PR.search(url)
        if m and m.group(1).lower() not in NOT_A_REPO:
            prs.append(f"{m.group(1)}/{m.group(2)}#{m.group(3)}")

    def dedup(xs):
        seen, out = set(), []
        for x in xs:
            if x[1] not in seen:
                seen.add(x[1])
                out.append(x)
        return out

    return dedup(own), dedup(foreign), sorted(set(prs))


def version_ranges(aff) -> tuple[str, str]:
    """Render affected[].ranges[].events as ">=a,<b" plus the fixed version(s)."""
    parts, fixed = [], []
    for rng in aff.get("ranges", []):
        if rng.get("type") == "GIT":
            continue
        lo = None
        for ev in rng.get("events", []):
            if "introduced" in ev:
                lo = ev["introduced"]
            elif "fixed" in ev:
                hi = ev["fixed"]
                fixed.append(hi)
                parts.append(f">={lo or '0'},<{hi}")
                lo = None
            elif "last_affected" in ev:
                parts.append(f">={lo or '0'},<={ev['last_affected']}")
                lo = None
        if lo is not None:
            parts.append(f">={lo}")
    return " || ".join(parts), ",".join(sorted(set(fixed), key=version_key))


def pick_vuln_version(versions) -> str:
    """Newest still-vulnerable release: the version a user would have had installed."""
    stable = [v for v in versions if not is_prerelease(v)]
    pool = stable or list(versions)
    return max(pool, key=version_key) if pool else ""


def merge_affected(rec):
    """Collapse rec['affected'] into one entry per PyPI package.

    GitHub's OSV export splits a single advisory across one ``affected`` entry per
    maintained branch (Django 5.1.x / 5.0.x / 4.2.x) and, for some records, repeats
    each of those verbatim. Both would otherwise become separate CSV rows for what
    is one vulnerability in one package.
    """
    merged: dict[str, dict] = {}
    for aff in rec.get("affected", []):
        pkg = aff.get("package", {})
        if pkg.get("ecosystem") != "PyPI":
            continue
        name = pkg.get("name", "")
        slot = merged.setdefault(name, {"ranges": [], "fixed": set(), "versions": set()})
        ranges, fixed = version_ranges(aff)
        for part in filter(None, ranges.split(" || ")):
            if part not in slot["ranges"]:
                slot["ranges"].append(part)
        slot["fixed"].update(filter(None, fixed.split(",")))
        slot["versions"].update(aff.get("versions") or [])
    return merged


def build_rows(records, tiers, min_year, require_cve, require_commit):
    rows, stats = [], {
        "records": 0, "reviewed": 0, "no_cve": 0, "no_repo": 0,
        "no_own_commit": 0, "tier_filtered": 0, "year_filtered": 0, "emitted": 0,
    }
    for rec in records:
        stats["records"] += 1
        if not rec.get("database_specific", {}).get("github_reviewed"):
            continue
        stats["reviewed"] += 1

        published = rec.get("published", "")
        if min_year and published and int(published[:4]) < min_year:
            stats["year_filtered"] += 1
            continue

        cves = [a for a in rec.get("aliases", []) if a.startswith("CVE-")]
        if require_cve and not cves:
            stats["no_cve"] += 1
            continue

        cwes = rec.get("database_specific", {}).get("cwe_ids") or []
        tier = tier_of(cwes)
        if tier not in tiers:
            stats["tier_filtered"] += 1
            continue

        repo_url = extract_repo_url(rec)
        if not repo_url:
            stats["no_repo"] += 1
            continue

        own, foreign, prs = extract_fixes(rec, repo_url)
        if require_commit and not own:
            stats["no_own_commit"] += 1
            continue

        patch_commit = own[0][1] if own else ""
        for name, aff in sorted(merge_affected(rec).items()):
            ranges = " || ".join(aff["ranges"])
            fixed = ",".join(sorted(aff["fixed"], key=version_key))
            rows.append({
                "cve_id": cves[0] if cves else "",
                "package_name": name,
                "repo_url": repo_url,
                "patch_commit": patch_commit,
                "affected_ranges": ranges,
                "vuln_functions": "",       # filled by enrich_functions.py
                "n_vuln_functions": "",     # filled by enrich_functions.py
                "clone_path": "",           # filled by materialize.py
                "checkout_ref": f"{patch_commit}^" if patch_commit else "",
                # --- provenance / triage columns ---
                "ghsa_id": rec["id"],
                "pbt_tier": tier,
                "cwe_ids": ";".join(cwes),
                "severity": rec.get("database_specific", {}).get("severity", ""),
                "published": published[:10],
                "summary": (rec.get("summary") or "").replace("\n", " ")[:300],
                "fixed_version": fixed,
                "vuln_version": pick_vuln_version(aff["versions"]),
                "n_affected_versions": len(aff["versions"]),
                "all_patch_commits": ";".join(s for _, s in own),
                "foreign_commits": ";".join(f"{r}@{s}" for r, s in foreign),
                "pr_refs": ";".join(prs),
                "all_cves": ";".join(cves),
            })
            stats["emitted"] += 1
    return rows, stats


FIELDS = [
    "cve_id", "package_name", "repo_url", "patch_commit", "affected_ranges",
    "vuln_functions", "n_vuln_functions", "clone_path", "checkout_ref",
    "ghsa_id", "pbt_tier", "cwe_ids", "severity", "published", "summary",
    "fixed_version", "vuln_version", "n_affected_versions",
    "all_patch_commits", "foreign_commits", "pr_refs", "all_cves",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "dataset.csv")
    ap.add_argument("--tier", default="A,B", help="PBT tiers to keep (default: A,B)")
    ap.add_argument("--min-year", type=int, default=0, help="drop advisories published before this year")
    ap.add_argument("--allow-no-cve", action="store_true", help="keep GHSA-only records")
    ap.add_argument("--allow-no-commit", action="store_true", help="keep records with no fix commit")
    ap.add_argument("--refresh", action="store_true", help="re-download the OSV bundle")
    ap.add_argument("--no-merge", action="store_true",
                    help="discard stage 2/3 columns from an existing --out instead of merging")
    args = ap.parse_args()

    tiers = {t.strip().upper() for t in args.tier.split(",") if t.strip()}
    zip_path = fetch_osv(force=args.refresh)

    with zipfile.ZipFile(zip_path) as z:
        records = [json.loads(z.read(n)) for n in z.namelist() if n.endswith(".json")]

    rows, stats = build_rows(records, tiers, args.min_year,
                             not args.allow_no_cve, not args.allow_no_commit)

    # Carry over anything stages 2 and 3 already computed, keyed on the row identity,
    # so rebuilding stage 1 never throws away hours of API calls and clones.
    fields = list(FIELDS)
    if args.out.exists() and not args.no_merge:
        prior = {}
        with open(args.out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            extra = [c for c in (reader.fieldnames or []) if c not in FIELDS]
            for old in reader:
                prior[(old["ghsa_id"], old["package_name"])] = old
        fields += extra
        kept = 0
        for r in rows:
            old = prior.get((r["ghsa_id"], r["package_name"]))
            if not old:
                continue
            for col in extra + ["vuln_functions", "n_vuln_functions", "clone_path"]:
                if old.get(col):
                    r[col] = old[col]
            kept += 1
        print(f"merged enrichment from {len(prior)} existing rows ({kept} matched)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

    print("\n--- funnel ---")
    print(f"  OSV records            {stats['records']}")
    print(f"  github-reviewed        {stats['reviewed']}")
    print(f"  dropped: before {args.min_year or '-'}   {stats['year_filtered']}")
    print(f"  dropped: no CVE        {stats['no_cve']}")
    print(f"  dropped: tier not in {sorted(tiers)}  {stats['tier_filtered']}")
    print(f"  dropped: no repo url   {stats['no_repo']}")
    print(f"  dropped: no own-repo commit  {stats['no_own_commit']}")
    print(f"  rows emitted           {stats['emitted']}")
    by_tier = {}
    for r in rows:
        by_tier[r["pbt_tier"]] = by_tier.get(r["pbt_tier"], 0) + 1
    print(f"  by tier                {dict(sorted(by_tier.items()))}")
    print(f"  distinct packages      {len({r['package_name'] for r in rows})}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
