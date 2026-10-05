# CVE dataset for agentic PBT

Builds a corpus of real PyPI vulnerabilities whose fix commit is known, filtered
down to the ones a property-based test could plausibly witness, with each project
checked out at the commit *before* the fix.

## Pipeline

```
build_dataset.py     OSV bulk export  ->  dataset.csv          (stdlib only, no API key)
enrich_functions.py  + patch diff     ->  vuln_functions       (needs `gh` auth)
materialize.py       + git clone      ->  checkouts/<CVE>__<pkg>/  at patch_commit^
```

```bash
python dataset/build_dataset.py                          # ~2900 rows, 30s
python dataset/enrich_functions.py --tier A --workers 6  # GitHub API, cached & resumable
python dataset/materialize.py --tier A --workers 4       # shallow clones
```

Every stage is re-runnable. Stage 1 merges into an existing `dataset.csv` on
`(ghsa_id, package_name)` rather than clobbering it, so re-running it after an
advisory refresh keeps the stage 2/3 columns (`--no-merge` to opt out). Stages 2
and 3 skip rows they have already done.

### Stage 1 — `build_dataset.py`

Pulls `https://osv-vulnerabilities.storage.googleapis.com/PyPI/all.zip` (33 MB,
~3 s) rather than scraping `github.com/advisories`. Same data, structured, no rate
limit. Keeps records that are `github_reviewed`, carry a CVE, and reference a fix
commit **in the package's own repo** — a commit link pointing at a distro fork or
an oss-security mirror is not something we can check out.

Two quirks of GitHub's OSV export are handled here:

- `reference.type == "FIX"` never appears; every link is typed `WEB`. Fix commits
  have to be recognised by URL shape.
- One advisory is split into one `affected` entry per maintained branch (Django
  5.1.x / 5.0.x / 4.2.x) and some entries are repeated verbatim, so `affected` is
  merged per package to give one row per `(ghsa_id, package_name)`.

### Stage 2 — `enrich_functions.py`

Fetches the commit, maps each changed line back to the **pre-patch** file, and
AST-resolves the enclosing function. Pre-patch is the right side to parse: a
missing-validation CVE is usually a pure insertion, which has no post-patch
counterpart at its insertion point, and the pre-patch functions are the ones the
agent will actually be pointed at.

Skips test files — a fix commit nearly always ships its own regression test, and
those functions are the oracle, not the bug. Merge commits are dropped (no single
"before" state). Responses cache under `.cache/gh`, so runs resume for free.

### Stage 3 — `materialize.py`

`git init` + `git fetch --depth 2 origin <sha>` + `checkout <sha>^`. Depth 2 is
the minimum that brings down the parent. Verified on every sample that
`HEAD == patch_commit^` and that each `vuln_functions` entry resolves in the tree.

## Columns

| column | meaning |
|---|---|
| `cve_id`, `package_name`, `repo_url` | identity |
| `patch_commit` | fix commit SHA in the project's own repo |
| `vuln_commit` | resolved `patch_commit^` — what gets checked out |
| `affected_ranges` | `>=4.2,<4.2.18 \|\| >=5.0,<5.0.11` |
| `vuln_version` / `fixed_version` | newest still-vulnerable release / first fixed |
| `vuln_functions` | `path/to/file.py::Class.method;...` (pre-patch, tests excluded) |
| `n_vuln_functions` | count |
| `clone_path` | checkout directory |
| `pbt_tier` | `A` / `B` / `C`, see below |
| `n_changed_files`, `patch_lines`, `n_test_files`, `n_nested_functions` | quality gates |
| `ghsa_id`, `cwe_ids`, `severity`, `published`, `summary` | provenance |

## Tiers

`A` — the CWE class names a property a test can assert directly: path traversal
(22/23/36), open redirect (601), ReDoS (1333), cert & hostname validation
(295/297), encoding & escaping (116/172/838), request smuggling (444), incorrect
calculation and integer over/underflow (682/190/191).

`B` — plausible, but only when the patched code sits on a pure-function boundary.
Input validation (20), XSS (79, sanitisers only), resource exhaustion (400/770),
deserialisation (502), the injection families, and the memory-safety CWEs
(787/125/119/476/617) — for a C extension the property is just "no interpreter
crash on any well-typed input", which Hypothesis is good at.

`C` — needs multi-user state, a live request, or a network peer: 200, 862/863/284,
287/306, 352, 918, 639. Not emitted unless `--tier` asks for it.

**The tier is a prefilter, not a verdict.** CWE-22 in `gradio/utils.py::safe_join`
is an ideal target; CWE-22 in a Django view whose input is an `HttpRequest` is not
testable at all. The deciding signal is whether the patched function takes values
Hypothesis can generate, and that only shows up in the diff.

## Current numbers

```
25644  OSV PyPI records
 6271  github-reviewed
 -391  no CVE
-2439  tier C
 -143  no resolvable repo
-1133  no fix commit in own repo
 2942  rows          (tier A 621 / tier B 2321, 694 distinct packages)
```

Stage 2 on the first 60 tier-A rows: 41 resolved (68%). Failures are all
legitimate — 8 merge commits, 5 test-only changes, 3 C-extension-only patches
(TensorFlow), 1 dead commit, 2 module-level changes.

Applying the size gates to those 41:

```
41  ok
39  n_changed_files <= 10
34  patch_lines <= 200
30  n_vuln_functions <= 5      <- a 368-function "fix" is a refactor, not a fix
```

So roughly **half of tier A survives end to end**, projecting to ~310 clean tier-A
samples and perhaps ~1000 including tier B.

## What a good sample looks like

`CVE-2026-28414`, gradio, CWE-22, 1 file, 6 lines, `gradio/utils.py::safe_join`:

```diff
@@ def safe_join(directory: DeveloperPath, path: UserProvidedPath) -> str:
     if (
         any(sep in filename for sep in _os_alt_seps)
         or os.path.isabs(filename)
+        or filename.startswith("/")
         or filename == ".."
         or filename.startswith("../")
     ):
```

The patch is an added clause in a guard, which is the same thing as an assertion
the code was missing. Written as a property:

```python
@given(st.text())
def test_safe_join_never_escapes(p):
    try:
        out = safe_join(BASE, p)
    except InvalidPathError:
        return
    assert Path(out).resolve().is_relative_to(Path(BASE).resolve())
```

`os.path.isabs("/x")` is `False` on Windows, so `"/x"` walked straight through the
guard. This is the shape most tier-A samples have, and it is why extracting the
property implied by each patch is worth a column of its own.
