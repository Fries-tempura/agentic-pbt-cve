#!/usr/bin/env python3
"""
I3 的观测量:被改函数读取了多少个自由变量,其中哪些来自框架上下文。

A property only works as a selection filter if it can be computed *before* running
anything. For I3 -- "the state the defect needs must be settable by the test" --
the computable proxy is the function's free variables: every name it reads that is
neither a parameter nor assigned locally. Those are exactly the values a test cannot
pass in, and so must set some other way.

    依赖=0            纯函数,随便测
    依赖是模块常量     测试可以赋值,可测
    依赖是框架上下文   request / session / g / current_app -- 要起框架,实际不可测

Usage:
    python dataset/check_i3.py --cve CVE-2026-25480
    python dataset/check_i3.py --all
"""

import argparse
import ast
import csv
from pathlib import Path

HERE = Path(__file__).parent

# 读到这些名字,基本等于"需要一个活的 Web 框架":它们是请求期才有值的上下文对象,
# 测试要给它们赋值就得先把整个框架跑起来。import 得到它们不代表能设定它们。
FRAMEWORK = {"request", "session", "g", "current_app", "current_user",
             "scope", "receive", "send", "websocket", "ctx", "app_ctx",
             "flask", "quart", "sanic"}
# 这些模块一出现在自由变量里,基本等于函数挂在某个 Web 框架的请求周期上
FRAMEWORK_MODULES = {"flask", "quart", "sanic", "starlette", "fastapi", "django"}


class FreeVars(ast.NodeVisitor):
    """Names a function reads but neither takes as a parameter nor binds itself."""

    def __init__(self, fn: ast.FunctionDef):
        self.bound = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
        if fn.args.vararg:
            self.bound.add(fn.args.vararg.arg)
        if fn.args.kwarg:
            self.bound.add(fn.args.kwarg.arg)
        self.read: set[str] = set()
        for node in fn.body:
            self.visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.bound.add(node.id)
        elif node.id not in self.bound:
            self.read.add(node.id)

    def visit_comprehension(self, node):
        self.generic_visit(node)


def find_func(tree: ast.AST, qualname: str):
    want = qualname.split(".")[-1]
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == want:
            return n
    return None


def analyse(clone: Path, spec: str) -> dict:
    path, _, qual = spec.partition("::")
    f = clone / path
    if not f.exists():
        return {"spec": spec, "verdict": "缺文件"}
    try:
        tree = ast.parse(f.read_text(errors="replace"))
    except SyntaxError:
        return {"spec": spec, "verdict": "解析失败"}
    fn = find_func(tree, qual)
    if fn is None:
        return {"spec": spec, "verdict": "非函数(类/模块级)"}

    fv = FreeVars(fn)
    # 模块里 import 或在顶层赋值的名字,测试能设定
    settable = {a.asname or a.name.split(".")[0]
                for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in n.names}
    settable |= {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
                 for t in n.targets if isinstance(t, ast.Name)}

    src = f.read_text(errors="replace")
    framework = sorted(fv.read & FRAMEWORK)
    # 从框架 import 进来的名字也算框架上下文,哪怕名字本身不在表里
    for mod in FRAMEWORK_MODULES:
        if f"from {mod}" in src or f"import {mod}" in src:
            framework += [n for n in sorted(fv.read)
                          if f"from {mod} import" in src and n in src.split(f"from {mod} import")[1][:120]]
    framework = sorted(set(framework))
    unknown = sorted(fv.read - settable - set(FRAMEWORK) - set(dir(__builtins__)))
    verdict = ("❌ 框架上下文" if framework else
               "✅ 无隐式依赖" if not unknown else "⚠️ 有模块级依赖")
    return {"spec": spec, "n_free": len(fv.read), "framework": ";".join(framework),
            "module_level": ";".join(unknown[:4]), "verdict": verdict}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cve")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dataset", type=Path, default=HERE / "dataset.csv")
    args = ap.parse_args()

    rows = [r for r in csv.DictReader(open(args.dataset))
            if r["vuln_functions"] and r["clone_path"]
            and (args.all or r["cve_id"] == args.cve)]

    print(f"{'CVE':17}{'包':18}{'被改函数':42}{'自由变量':9}判定")
    print("-" * 104)
    for r in rows:
        clone = HERE / r["clone_path"].replace("checkouts/", "checkouts/")
        for spec in r["vuln_functions"].split(";")[:2]:
            if not spec:
                continue
            a = analyse(clone, spec)
            short = spec.split("/")[-1][:40]
            print(f"{r['cve_id']:17}{r['package_name']:18}{short:42}"
                  f"{a.get('n_free', '-'):<9}{a['verdict']}"
                  + (f"  [{a['framework']}]" if a.get("framework") else ""))


if __name__ == "__main__":
    main()
