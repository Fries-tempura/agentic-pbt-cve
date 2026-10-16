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

FW, FH = 17.0, 15.0
INK, GREY, MUTE, NEW = "#1a1a1a", "#6b7280", "#4b5563", "#c2410c"
PAD, GAP = 0.016, 0.046
F_TITLE, F_BODY, F_FILE = 13.5, 10.6, 10.0


def lh(pt, spacing=1.5):
    return pt * spacing / 72 / FH


fig, ax = plt.subplots(figsize=(FW, FH))
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
fig.patch.set_facecolor("white")

COLS = [
    ("阶段一 · 数据集构建", "#eef3fb", "#9db8dd", "#2f5c9e", 0.022, 0.312),
    ("阶段二 · 实验运行", "#fdf4e7", "#e0b473", "#b4762a", 0.355, 0.645),
    ("阶段三 · 结果度量", "#edf7f0", "#8fc4a3", "#2f7a52", 0.688, 0.978),
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


INNER = [("1", "确定测试目标", 0), ("2", "阅读实现", 0),
         ("3", "记录代码声明的规约  → claims.md", 1),
         ("4", "依据 claims.md 推导性质", 1),
         ("5", "编写测试,逐条标注所依据的规约", 1),
         ("6", "运行测试,分类失败原因", 0), ("7", "撰写报告", 0), ("8", "给出结论", 0)]


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
        ax.text(x0 + 0.040, t, "agent 按提示词执行 8 步", fontsize=F_TITLE,
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
    0: [step(0, 1, "获取漏洞公告", "保留附 CVE 编号与修复提交的记录", "dataset/build_dataset.py"),
        arrow(0, "2942 行 / 694 个包"),
        step(0, 2, "定位受影响函数", "解析补丁提交之前的源码", "dataset/enrich_functions.py"),
        arrow(0, "vuln_functions 列"),
        step(0, 3, "排除平台相关样本", "标记仅在 Windows 成立的缺陷", "dataset/platform_scan.py"),
        arrow(0, "风险样本 17%"),
        step(0, 4, "回退至补丁前版本", "检出修复提交的父提交", "dataset/materialize.py"),
        (None, 0.040),
        note(0, "17 个样本", size=15, color=COLS[0][3], weight="bold"),
        (None, 0.010),
        note(0, "补丁前的源码 + 指定的目标模块\n+ 已知的标准答案")],
    1: [step(1, 5, "发起单次运行", "串行调度,配额超限后自动重试",
             "runs/serial.sh · go.sh"),
        arrow(1, 'claude -p "/hypo_v2 <模块>"'),
        agent_box(),
        arrow(1, "单次运行的产物"),
        note(1, "claims.md            代码声明的规约\n"
                "test_*.py            性质测试\n"
                "bug_report_*.md      缺陷报告与复现脚本\n"
                "claude_result.json   运行回合数与开销", size=10, mono=True)],
    2: [step(2, 7, "还原全部提出的性质", "不限于失败的,通过的亦计入",
             "dataset/extract_properties.py"),
        arrow(2, "每条性质一行"),
        step(2, 8, "判定是否命中", "三个相互独立的信号", "dataset/classify_hit.py"),
        arrow(2, "每次运行一行"),
        step(2, 9, "5 次运行归并为一档", "稳定命中 / 不稳定 / 从未命中", "dataset/aggregate.py"),
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

# ── 事前筛查表 ──
# 它不读 runs/ 里的任何东西,只读补丁前的源码,所以能在跑任何实验之前用。
# 画成脱离主链的一个框:之前把它编成「第 10 步」摆在阶段三末尾,等于说它是
# 判定命中之后的下一步,而它根本不在那条链上。
BX0, BX1 = 0.250, 0.750
BY1 = band_bottom - 0.036
BY0 = BY1 - (PAD * 2 + lh(14) + 0.012 + 3 * lh(10.4, 1.65) + lh(F_FILE) + 0.010)
DASH = "#8b5cf6"
ax.add_patch(FancyBboxPatch((BX0, BY0), BX1 - BX0, BY1 - BY0,
                            boxstyle="round,pad=0.005,rounding_size=0.010",
                            fc="#faf7ff", ec=DASH, lw=1.6, ls="--", zorder=2))
ax.text(BX0 + 0.020, BY1 - 0.022, "事前筛查表", fontsize=14, fontweight="bold",
        color=INK, va="center", zorder=4)
ax.text(BX0 + 0.126, BY1 - 0.022, "不在主链上 · 只读补丁前的源码,不读任何运行产物",
        fontsize=10.2, color=DASH, va="center", zorder=4)
ax.text(BX0 + 0.020, BY1 - 0.052,
        "由阶段三的结果总结出 I1–I5 五条限制,再把其中可计算的那些写成指标。\n"
        "目前实现 I3:统计函数读取的自由变量。取自框架上下文的变量测试无法设定,\n"
        "该样本不必运行。现用于事后验算,扩充数据集时用于事前筛选。",
        fontsize=10.4, color="#374151", va="top", linespacing=1.65, zorder=4)
ax.text(BX1 - 0.018, BY0 + PAD, "dataset/check_i3.py", fontsize=F_FILE,
        color=DASH, ha="right", va="center", family=MONO, zorder=4)

for x_band, x_box, label, ha in [(0.833, BX1, "由实验结果总结而来", "right"),
                                 (0.167, BX0, "筛掉不值得运行的样本", "left")]:
    ax.add_patch(FancyArrowPatch((x_band, band_bottom), (x_box, (BY0 + BY1) / 2),
                                 connectionstyle="angle,angleA=-90,angleB=0,rad=12",
                                 arrowstyle="-|>", mutation_scale=16, lw=1.6,
                                 ls="--", color=DASH, zorder=6)
                 if ha == "right" else
                 FancyArrowPatch((x_box, (BY0 + BY1) / 2), (x_band, band_bottom),
                                 connectionstyle="angle,angleA=0,angleB=-90,rad=12",
                                 arrowstyle="-|>", mutation_scale=16, lw=1.6,
                                 ls="--", color=DASH, zorder=6))
    # 标签放到竖线旁边,不要压在线上
    ax.text(x_band + (0.010 if ha == "left" else -0.010), band_bottom - 0.007,
            label, fontsize=9.8, color=DASH, ha=ha, va="top", zorder=6)

ax.text(0.5, 0.992, "agentic PBT × 真实 CVE:全流程与对应代码", fontsize=22,
        fontweight="bold", color=INK, ha="center", va="top")
ax.text(0.5, 0.930,
        "将每个项目回退至补丁提交之前,使「agent 是否发现补丁所修复的缺陷」成为可判定的问题",
        fontsize=12.5, color=GREY, ha="center", va="top")
ax.text(0.5, BY0 - 0.028,
        "方框右下角 = 执行该步骤的代码文件          "
        "★ = 为使规约可追溯而新增的步骤          "
        "虚线 = 不在主链上",
        fontsize=10.5, color=GREY, ha="center", va="top")

for ext in ("png", "pdf"):
    fig.savefig(f"docs/pipeline.{ext}", dpi=200, bbox_inches="tight", facecolor="white")
assert BY0 > 0.02, f"筛查表下沿 {BY0:.3f} 跑出画布,加大 FH"
print(f"写出 docs/pipeline.png 与 .pdf  (色带下沿 {band_bottom:.3f},筛查表 {BY0:.3f}-{BY1:.3f})")
