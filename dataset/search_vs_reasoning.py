#!/usr/bin/env python3
"""一次命中是搜出来的,还是 agent 读代码推出来的?

把 agent 留下的测试文件原样再跑一遍,换一批随机种子。性质本身没变,变的只有
抽样。于是:

    重跑仍然失败  ->  Hypothesis 的搜索能自己到达反例
    重跑全部通过  ->  报告里的复现输入不是搜出来的,是 agent 从代码里推出来的,
                     Hypothesis 在这里只充当了验证器

这个区分决定改进往哪走:前者该改输入生成,后者该改代码阅读。只统计「有没有
找到」看不出区别 —— litestar 上 agent 推理补上了搜索的空缺,命中了,而那条
性质在 12 个种子 × 300 例下一次都没抓到碰撞。

用法:
    python dataset/search_vs_reasoning.py --run runs/litestar-verify_v2_r1
    python dataset/search_vs_reasoning.py --run runs/xxx --seeds 8
"""

import argparse
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

# Hypothesis 收缩完会打印反例,两种措辞都见过
FALSIFY = re.compile(r"(?:Falsifying example|Failing test case):\s*\w+\(\s*\n(.*?)^E?\s*\)",
                     re.M | re.S)

HERE = Path(__file__).parent


def test_files(run: Path):
    # repro 脚本不是性质测试,排除;__pycache__ 同理
    return [p for p in sorted(run.rglob("test*.py")) if "__pycache__" not in p.parts]


def test_names(path: Path) -> list[str]:
    """文件里的测试函数名。整文件一起跑太粗:一个文件常含好几条性质,
    其中一条失败就把整份判成「搜索可达」,而失败的可能是另一条。"""
    return re.findall(r"^def (test_\w+)", path.read_text(errors="replace"), re.M)


def falsifying(out: str) -> str:
    """输出里收缩后的反例,整理成一行。

    只数「失败几次」是不够的:一个文件里的一条性质可能被好几个不同的缺陷触发,
    而我们要知道的是搜索到达了哪一个。litestar 上这条差别很关键 —— 那条碰撞
    性质每次都失败,但每次收缩到的都是另一个缺陷(文件系统拒绝非 BMP 字符),
    碰撞本身一次都没被搜到。
    """
    m = FALSIFY.search(out)
    if not m:
        return ""
    args = [re.sub(r"^E?\s*", "", ln).rstrip(",")
            for ln in m.group(1).splitlines() if ln.strip()]
    return "; ".join(a for a in args if a)[:88]


def run_with_seed(path: Path, python: Path, seed: int, name: str = "",
                  nice: int = 10, timeout: int = 300) -> tuple[int, str]:
    """跑一遍,用 -p no:cacheprovider 避免写进项目目录。

    降优先级跑,并给足够短的超时:被测的是补丁前的代码,里面可能就有耗时缺陷,
    让它满速跑到底既没必要也会把机器拖垮。
    """
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(seed)
    # Hypothesis 把失败过的输入存进 cwd 下的 .hypothesis/,下次直接重放。
    # 留着它,重跑永远「失败」—— 测到的是重放,不是搜索。每次换一个空目录当 cwd。
    cmd = [str(python), "-m", "pytest",
           f"{path}::{name}" if name else str(path), "-q", "-p", "no:cacheprovider",
           "-W", "ignore::DeprecationWarning"]
    # 降优先级要在子进程里做。包一层 `nice` 命令不行:nice 会沿 PATH 重新查找
    # 解释器,把我们给的绝对路径丢掉,于是跑到了系统 python 上,报 No module named pytest。
    with tempfile.TemporaryDirectory() as cwd:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout, env=env, cwd=cwd,
                               preexec_fn=(lambda: os.nice(nice)) if nice else None)
        except subprocess.TimeoutExpired:
            return 2, "(超时)"
    return r.returncode, (r.stdout + r.stderr)[-4000:]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--python", type=Path, required=True,
                    help="该样本虚拟环境里的 python")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--nice", type=int, default=10, help="进程优先级,越大越让路")
    ap.add_argument("--timeout", type=int, default=300, help="单次运行上限(秒)")
    ap.add_argument("--pause", type=float, default=1.0, help="每次之间歇多久(秒)")
    args = ap.parse_args()

    # 跑在临时目录里,相对路径会失效,所以要绝对路径。但不能用 resolve():
    # venv 里的 python 是符号链接,解开之后指向系统解释器,venv 的 site-packages
    # 就失效了 —— 症状是 "No module named pytest"。absolute() 保留符号链接。
    args.python = args.python.absolute()
    args.run = args.run.resolve()
    files = test_files(args.run)
    if not files:
        print("没有测试文件"); return

    print(f"{args.run}:{len(files)} 个测试文件,各跑 {args.seeds} 次\n")
    for f in files:
        for name in test_names(f):
            fails, shrunk, slow = 0, set(), 0
            for s in range(args.seeds):
                code, out = run_with_seed(f, args.python, s, name,
                                          args.nice, args.timeout)
                if code == 2 and out == "(超时)":
                    slow += 1
                elif code != 0:
                    fails += 1
                    if (ex := falsifying(out)):
                        shrunk.add(ex)
                time.sleep(args.pause)
            if slow == args.seeds:
                verdict = "每次都超时"
            elif fails + slow == args.seeds:
                verdict = "搜索可达    (每次都失败)"
            elif fails:
                verdict = f"搜索不稳    ({fails}/{args.seeds} 次失败)"
            else:
                verdict = "搜索到不了  (全部通过)"
            print(f"  {name:46s} {verdict}")
            for ex in sorted(shrunk):
                print(f"      收缩到: {ex}")

    print("\n「全部通过」而报告里有缺陷 = 那个缺陷是推出来的,不是搜出来的。")


if __name__ == "__main__":
    main()
