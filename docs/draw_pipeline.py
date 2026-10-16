#!/usr/bin/env python3
"""画一张流程图:从漏洞公告到一张「这个 CVE 能不能被测出来」的表。

图只回答「有哪些步、每步由谁执行、交出什么」。为什么要这么做,写在文档里,
不写在图上 —— 一张要凑近了读的图,等于没画。

方框高度由文字行数算出来,不是手填的坐标,否则改一句话就撑破版面。
    /opt/miniconda3/bin/python docs/draw_pipeline.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

plt.rcParams["font.family"] = ["Hiragino Sans GB", "PingFang HK", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
MONO = ["Menlo", "Hiragino Sans GB"]

FW, FH = 17.0, 9.6
INK, GREY, MUTE, NEW = "#1a1a1a", "#6b7280", "#4b5563", "#c2410c"
PAD, GAP = 0.016, 0.046
F_TITLE, F_BODY, F_FILE = 13.5, 10.6, 10.0


def lh(pt, spacing=1.5):
    return pt * spacing / 72 / FH


fig, ax = plt.subplots(figsize=(FW, FH))
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
fig.patch.set_facecolor("white")

COLS = [
    ("阶段一 · 建数据集", "#eef3fb", "#9db8dd", "#2f5c9e", 0.022, 0.312),
    ("阶段二 · 跑 agent", "#fdf4e7", "#e0b473", "#b4762a", 0.355, 0.645),
    ("阶段三 · 量结果",   "#edf7f0", "#8fc4a3", "#2f7a52", 0.688, 0.978),
]
Y_TOP = 0.830


def step(col, n, title, body, file, star=False):
    h = PAD * 2 + lh(F_TITLE) + lh(F_BODY) + 0.008 + lh(F_FILE)
    _, _, _, accent, x0, x1 = COLS[col]

    def draw(y):
        ax.add_patch(FancyBboxPatch((x0, y - h), x1 - x0, h,
                                    boxstyle="round,pad=0.004,rounding_size=0.008",
                                    fc="white", ec=accent, lw=1.8 if star else 1.0, zorder=2))
        ax.add_patch(Rectangle((x0, y - h), 0.004, h, fc=accent, ec="none", zorder=3))
        t = y - PAD
        ax.text(x0 + 0.016, t, str(n), fontsize=F_TITLE, fontweight="bold",
                color=accent, va="top", zorder=4)
        ax.text(x0 + 0.040, t, title, fontsize=F_TITLE, fontweight="bold",
                color=INK, va="top", zorder=4)
        ax.text(x0 + 0.040, t - lh(F_TITLE), body, fontsize=F_BODY,
                color="#4b5563", va="top", zorder=4)
        ax.text(x1 - 0.014, t - lh(F_TITLE) - lh(F_BODY) - 0.008, file,
                fontsize=F_FILE, color=accent, ha="right", va="top",
                family=MONO, zorder=4)
    return draw, h


def arrow(col, label):
    _, _, _, _, x0, x1 = COLS[col]
    x = x0 + 0.034

    def draw(y):
        ax.add_patch(FancyArrowPatch((x, y), (x, y - GAP + 0.006), arrowstyle="-|>",
                                     mutation_scale=15, lw=1.4, color=MUTE, zorder=5))
        ax.text(x + 0.012, y - GAP / 2, label, fontsize=10, color=MUTE,
                va="center", ha="left", family=MONO, zorder=5)
    return draw, GAP


def note(col, text, size=10, color="#374151", mono=False, weight="normal", gapsize=1.7):
    h = len(text.split("\n")) * lh(size, gapsize)
    _, _, _, _, x0, x1 = COLS[col]

    def draw(y):
        ax.text(x0 + 0.016, y, text, fontsize=size, color=color, va="top",
                linespacing=gapsize, fontweight=weight,
                family=MONO if mono else None, zorder=4)
    return draw, h


INNER = [("1", "看懂要测什么", 0), ("2", "读实现", 0),
         ("3", "写下代码承诺了什么  → claims.md", 1),
         ("4", "只据 claims.md 想性质", 1),
         ("5", "写测试,每条标出对应哪条规约", 1),
         ("6", "跑测试,分诊失败", 0), ("7", "写报告", 0), ("8", "下结论", 0)]


def agent_box():
    row = lh(11.5) + 0.009
    h = PAD * 2 + lh(F_TITLE) + 0.010 + len(INNER) * row
    _, _, _, accent, x0, x1 = COLS[1]

    def draw(y):
        ax.add_patch(FancyBboxPatch((x0, y - h), x1 - x0, h,
                                    boxstyle="round,pad=0.004,rounding_size=0.008",
                                    fc="white", ec=accent, lw=1.8, zorder=2))
        ax.add_patch(Rectangle((x0, y - h), 0.004, h, fc=accent, ec="none", zorder=3))
        t = y - PAD
        ax.text(x0 + 0.016, t, "6", fontsize=F_TITLE, fontweight="bold",
                color=accent, va="top", zorder=4)
        ax.text(x0 + 0.040, t, "agent 照着剧本走 8 步", fontsize=F_TITLE,
                fontweight="bold", color=INK, va="top", zorder=4)
        ax.text(x1 - 0.014, t, "hypo_v2.md", fontsize=F_FILE, color=accent,
                ha="right", va="top", family=MONO, fontweight="bold", zorder=4)
        yy = t - lh(F_TITLE) - 0.010
        for num, head, new in INNER:
            c = NEW if new else "#57534e"
            ax.text(x0 + 0.040, yy, num, fontsize=10.5, color=c,
                    fontweight="bold", va="top", zorder=4)
            ax.text(x0 + 0.058, yy, head, fontsize=11.5, color=NEW if new else INK,
                    fontweight="bold" if new else "normal", va="top", zorder=4)
            if new:
                ax.text(x1 - 0.014, yy, "★", fontsize=11, color=NEW,
                        ha="right", va="top", zorder=4)
            yy -= row
    return draw, h


PLAN = {
    0: [step(0, 1, "拉漏洞公告", "筛出有 CVE、有修复提交的", "dataset/build_dataset.py"),
        arrow(0, "2942 行 / 694 个包"),
        step(0, 2, "定位被改的函数", "在打补丁之前的源码上解析", "dataset/enrich_functions.py"),
        arrow(0, "vuln_functions 列"),
        step(0, 3, "剔除平台假阴性", "只在 Windows 成立的标掉", "dataset/platform_scan.py"),
        arrow(0, "风险样本 17%"),
        step(0, 4, "退回修复前一刻", "切到修复提交的父提交", "dataset/materialize.py"),
        (None, 0.040),
        note(0, "17 个样本", size=15, color=COLS[0][3], weight="bold"),
        (None, 0.010),
        note(0, "一份修复前的源码 + 一个被指向的模块\n+ 一条已知的标准答案")],
    1: [step(1, 5, "发起一次运行", "串行,一次一个,撞配额就重试",
             "runs/serial.sh · go.sh"),
        arrow(1, 'claude -p "/hypo_v2 <模块>"'),
        agent_box(),
        arrow(1, "留下四样东西"),
        note(1, "claims.md            代码承诺了什么\n"
                "test_*.py            性质测试\n"
                "bug_report_*.md      缺陷报告与复现脚本\n"
                "claude_result.json   回合数与花费", size=10, mono=True)],
    2: [step(2, 7, "还原每条性质", "含通过的、和压根没想到的",
             "dataset/extract_properties.py"),
        arrow(2, "每条性质一行"),
        step(2, 8, "判定有没有找到", "三个各自独立的信号", "dataset/classify_hit.py"),
        arrow(2, "每次运行一行"),
        step(2, 9, "5 次折成一档", "稳定命中 / 不稳定 / 从未命中", "dataset/aggregate.py"),
        arrow(2, "三档分类"),
        step(2, 10, "事前可算的筛选量", "不跑也能算,用来挑样本", "dataset/check_i3.py"),
        (None, 0.040),
        note(2, "最终产出", size=15, color=COLS[2][3], weight="bold"),
        (None, 0.010),
        note(2, "table1_cve.csv   table2_results.csv\ntable3_stability.csv",
             size=10, mono=True)],
}

bottoms = {c: Y_TOP - sum(h for _, h in items) for c, items in PLAN.items()}
band_bottom = min(bottoms.values()) - 0.030

for name, face, edge, accent, x0, x1 in COLS:
    ax.add_patch(FancyBboxPatch((x0 - 0.014, band_bottom), x1 - x0 + 0.028,
                                0.892 - band_bottom,
                                boxstyle="round,pad=0.004,rounding_size=0.010",
                                fc=face, ec=edge, lw=1.4, zorder=0))
    ax.text(x0, 0.876, name, fontsize=15.5, fontweight="bold", color=INK, va="top")

for col, items in PLAN.items():
    y = Y_TOP
    for draw, h in items:
        if draw is not None:
            draw(y)
        y -= h

ym = (Y_TOP + band_bottom) / 2
for xa, xb in [(0.327, 0.341), (0.660, 0.674)]:
    ax.add_patch(FancyArrowPatch((xa, ym), (xb, ym), arrowstyle="-|>",
                                 mutation_scale=19, lw=2.2, color="#6b7280", zorder=6))

ax.text(0.5, 0.992, "agentic PBT × 真实 CVE:全流程与对应代码", fontsize=22,
        fontweight="bold", color=INK, ha="center", va="top")
ax.text(0.5, 0.930,
        "把每个项目退回修复前一刻,「agent 有没有找到补丁修的那个缺陷」就有了标准答案",
        fontsize=12.5, color=GREY, ha="center", va="top")
ax.text(0.5, band_bottom - 0.030,
        "方框右下角 = 执行这一步的代码文件          "
        "★ = 为「让规约可追溯」新增的步骤",
        fontsize=10.5, color=GREY, ha="center", va="top")

for ext in ("png", "pdf"):
    fig.savefig(f"docs/pipeline.{ext}", dpi=200, bbox_inches="tight", facecolor="white")
print(f"写出 docs/pipeline.png 与 .pdf  (三列底边 {bottoms})")
