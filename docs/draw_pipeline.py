#!/usr/bin/env python3
"""画一张流程图:从漏洞公告到一张「这个 CVE 能不能被测出来」的表。

每个方框标注真正执行那一步的代码文件,箭头上标注这一步交出去的东西。

方框高度由文字行数算出来,不是手填的坐标 —— 否则改一句话就撑破版面。
流程改了就重跑:
    /opt/miniconda3/bin/python docs/draw_pipeline.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

plt.rcParams["font.family"] = ["Hiragino Sans GB", "PingFang HK", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
MONO = ["Menlo", "Hiragino Sans GB"]          # 等宽优先,中文回退

FW, FH = 20.0, 14.0                            # 画布英寸
INK, GREY, MUTE = "#1a1a1a", "#6b7280", "#4b5563"
PAD = 0.013                                    # 框内上下留白
GAP = 0.040                                    # 框之间留给箭头的距离

F_TITLE, F_BODY, F_FILE = 12.5, 10.3, 9.7


def lh(pt, spacing=1.55):
    """一行文字在图上占多高(按比例计)。字号是磅,1 磅 = 1/72 英寸。"""
    return pt * spacing / 72 / FH


fig, ax = plt.subplots(figsize=(FW, FH))
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
fig.patch.set_facecolor("white")

COLS = [  # 阶段名, 副标题, 底色, 边框, 强调色, 左, 右
    ("阶段一 · 建数据集", "让「有没有找到那个缺陷」变成可机械判定的问题",
     "#eef3fb", "#9db8dd", "#2f5c9e", 0.020, 0.310),
    ("阶段二 · 跑 agent", "每个样本重复 5 次",
     "#fdf4e7", "#e0b473", "#b4762a", 0.355, 0.645),
    ("阶段三 · 量结果", "把一堆运行产物变成可比较的数字",
     "#edf7f0", "#8fc4a3", "#2f7a52", 0.690, 0.980),
]

Y_TOP = 0.842          # 各列第一个方框的顶边
queued = []            # (画它的函数, 占多高) —— 先量后画


def step(col, n, title, body, files, star=False):
    """一个步骤框。高度 = 标题 + 正文行数 + 文件名行数 + 留白。"""
    lines = body.split("\n")
    h = PAD * 2 + lh(F_TITLE) + len(lines) * lh(F_BODY) + 0.006 + len(files) * lh(F_FILE)
    _, _, _, _, accent, x0, x1 = COLS[col]

    def draw(ytop):
        ax.add_patch(FancyBboxPatch((x0, ytop - h), x1 - x0, h,
                                    boxstyle="round,pad=0.004,rounding_size=0.008",
                                    fc="white", ec=accent, lw=1.8 if star else 1.0,
                                    zorder=2))
        ax.add_patch(Rectangle((x0, ytop - h), 0.004, h, fc=accent, ec="none", zorder=3))
        y = ytop - PAD
        ax.text(x0 + 0.014, y, str(n), fontsize=F_TITLE, fontweight="bold",
                color=accent, va="top", zorder=4)
        ax.text(x0 + 0.034, y, title, fontsize=F_TITLE, fontweight="bold",
                color=INK, va="top", zorder=4)
        y -= lh(F_TITLE)
        ax.text(x0 + 0.034, y, body, fontsize=F_BODY, color="#374151",
                va="top", linespacing=1.55, zorder=4)
        y -= len(lines) * lh(F_BODY) + 0.006
        for f in files:
            ax.text(x1 - 0.012, y, f, fontsize=F_FILE, color=accent,
                    ha="right", va="top", family=MONO, zorder=4)
            y -= lh(F_FILE)
    return draw, h


def note(col, text, size=10.3, color="#374151", align="center", mono=False,
         weight="normal", spacing=1.7):
    """不带框的说明文字。"""
    lines = text.split("\n")
    h = len(lines) * lh(size, spacing)
    _, _, _, _, _, x0, x1 = COLS[col]
    xs = {"center": (x0 + x1) / 2, "left": x0 + 0.014}[align]

    def draw(ytop):
        ax.text(xs, ytop, text, fontsize=size, color=color, ha=align,
                va="top", linespacing=spacing, fontweight=weight,
                family=MONO if mono else None, zorder=4)
    return draw, h


def arrow(col, label):
    """两框之间的箭头,旁边标这一步交出去的是什么。"""
    _, _, _, _, _, x0, x1 = COLS[col]
    x = x0 + 0.030

    def draw(ytop):
        ax.add_patch(FancyArrowPatch((x, ytop), (x, ytop - GAP + 0.004),
                                     arrowstyle="-|>", mutation_scale=14,
                                     lw=1.3, color=MUTE, zorder=5))
        ax.text(x + 0.010, ytop - GAP / 2, label, fontsize=9.5, color=MUTE,
                va="center", ha="left", family=MONO, zorder=5)
    return draw, GAP


# ───────────────────────── 各列内容 ─────────────────────────
PLAN = {0: [], 1: [], 2: []}

PLAN[0] += [
    step(0, 1, "拉漏洞公告,粗筛",
         "把 PyPI 全部已审核的漏洞公告(33MB 压缩包)一次拉下来,\n"
         "只留三样都满足的:有 CVE 编号、指向本仓库的修复提交、\n"
         "缺陷类别上性质测试有可能观测得到。",
         ["dataset/build_dataset.py"]),
    arrow(0, "dataset.csv · 2942 行 / 694 个包"),
    step(0, 2, "定位被改的函数",
         "取补丁的改动记录,算出它动了哪些行,再到打补丁之前的\n"
         "源码上做语法树解析,报出每一行所在的函数 —— 那才是\n"
         "agent 将被指向的、还带着缺陷的代码。",
         ["dataset/enrich_functions.py"]),
    arrow(0, "vuln_functions 列"),
    step(0, 3, "剔除平台假阴性",
         "路径穿越类缺陷常常只在 Windows 上成立。扫描补丁里的平台\n"
         "相关写法,把这类样本标出来 —— 在 macOS 上跑它们,不管\n"
         "结果如何都说明不了问题。",
         ["dataset/platform_scan.py"]),
    arrow(0, "platform 列 · 风险样本 17%"),
    step(0, 4, "把代码退回修复前一刻",
         "克隆仓库,切到修复提交的父提交。这是整件事的支点:代码\n"
         "此刻一定还是坏的,于是「agent 有没有找到补丁修的那个\n"
         "缺陷」才有了标准答案。",
         ["dataset/materialize.py"]),
    (None, 0.030),
    note(0, "17 个样本", size=15, color=COLS[0][4], weight="bold"),
    (None, 0.012),
    note(0, "每个 = 一份修复前的源码\n"
            "    + 一个被指向的模块\n"
            "    + 一条已知的标准答案(补丁修了什么)"),
]

PLAN[1] += [
    step(1, 5, "组装并发起一次运行",
         "serial.sh 串行调度,一次只跑一个,撞上配额就等 10 分钟重试。\n"
         "go.sh 组装单次调用:把提示词拷成这次运行本地的斜杠命令、\n"
         "设好虚拟环境,再启动一个 agent。",
         ["runs/serial.sh", "runs/go.sh"]),
    arrow(1, 'claude -p "/hypo_v2 <模块名>"'),
]

INNER = [
    ("1", "看懂要测什么", "从参数里认出是模块、文件还是函数", False),
    ("2", "读实现", "导入它、读源码、看别处怎么调用它", False),
    ("3", "写下代码承诺了什么 → claims.md",
     "每条记五样:原话出处 / 来源种类 / 怎么从这话读出来的 /\n规约本身 / 为什么不能读得更强", True),
    ("4", "规约 → 性质", "只看 claims.md,不准回头重新判断一遍代码", True),
    ("5", "写测试", "每个测试首行注释标明它对应哪一条规约", True),
    ("6", "跑 pytest,分诊失败", "区分真缺陷、测试写错、和本来就不该测的输入", False),
    ("7", "写报告", "复现脚本 + 为什么这是缺陷", False),
    ("8", "下结论", "找到了 / 没找到 / 这个目标没有可测的性质", False),
]


def agent_box():
    hdr = PAD + lh(F_TITLE)
    body = sum(lh(11) + len(s.split("\n")) * lh(9.7) + 0.011 for _, _, s, _ in INNER)
    h = hdr + body + PAD
    _, _, _, _, accent, x0, x1 = COLS[1]

    def draw(ytop):
        ax.add_patch(FancyBboxPatch((x0, ytop - h), x1 - x0, h,
                                    boxstyle="round,pad=0.004,rounding_size=0.008",
                                    fc="white", ec=accent, lw=1.8, zorder=2))
        ax.add_patch(Rectangle((x0, ytop - h), 0.004, h, fc=accent, ec="none", zorder=3))
        y = ytop - PAD
        ax.text(x0 + 0.014, y, "6", fontsize=F_TITLE, fontweight="bold",
                color=accent, va="top", zorder=4)
        ax.text(x0 + 0.034, y, "agent 照着剧本走 8 步", fontsize=F_TITLE,
                fontweight="bold", color=INK, va="top", zorder=4)
        ax.text(x1 - 0.012, y, "hypo_v2.md", fontsize=F_FILE, color=accent,
                ha="right", va="top", family=MONO, fontweight="bold", zorder=4)
        y -= lh(F_TITLE)
        for num, head, sub, new in INNER:
            c = "#c2410c" if new else "#57534e"
            ax.text(x0 + 0.030, y, num, fontsize=10, color=c, fontweight="bold",
                    va="top", zorder=4)
            ax.text(x0 + 0.047, y, head, fontsize=11, color=INK,
                    fontweight="bold" if new else "normal", va="top", zorder=4)
            if new:
                ax.text(x1 - 0.012, y, "本次新增", fontsize=9, color="#c2410c",
                        ha="right", va="top", fontweight="bold", zorder=4)
            y -= lh(11)
            ax.text(x0 + 0.047, y, sub, fontsize=9.7, color=GREY, va="top",
                    linespacing=1.5, zorder=4)
            y -= len(sub.split("\n")) * lh(9.7) + 0.011
    return draw, h


PLAN[1] += [
    agent_box(),
    arrow(1, "每次运行留下四样东西"),
    note(1, "claims.md           代码承诺了什么,以及怎么读出来的\n"
            "test_*.py           性质测试,每条标着它对应哪条规约\n"
            "bug_report_*.md     找到缺陷时的报告与复现脚本\n"
            "claude_result.json  这次运行的回合数与花费",
         size=9.8, mono=True, align="left"),
    (None, 0.026),
    note(1, "为什么要把第 3 步单拎出来", size=11, color="#c2410c",
         weight="bold", align="left"),
    (None, 0.006),
    note(1, "「代码承诺了什么」和「我怎么检查它」原本挤在同一步。合在\n"
            "一起做,第一个判断错了,后面写出的测试会替它遮掩 —— 你只\n"
            "看到一个通过的测试,分不清是规约读错了,还是测试没碰到触发\n"
            "输入。这两种失败长得一模一样,改进方向却完全相反。拆开、\n"
            "并留下书面记录,事后才查得了。",
         size=9.9, align="left", spacing=1.6),
]

PLAN[2] += [
    step(2, 7, "还原它提出过的每一条性质",
         "只看报告是不够的 —— 报告里只有碰巧失败的那些。回放\n"
         "这次运行的完整记录,解析 claims.md,再用语法树拆开每个\n"
         "测试函数,得到:输入怎么生成、断言是什么、通过还是失败、\n"
         "背后是哪一条规约。通过的性质、和压根没想到的性质,才是\n"
         "解释「为什么没找到」的证据。",
         ["dataset/extract_properties.py"]),
    arrow(2, "每条性质一行的表"),
    step(2, 8, "判定这次有没有找到",
         "三个各自独立的信号:有没有点名那个 CVE、有没有点名出\n"
         "问题的函数、有没有用补丁同样的说法描述缺陷。分开报而\n"
         "不是合成一个分数 —— 只中一个的多半是误判。命中仍需\n"
         "人工复核。",
         ["dataset/classify_hit.py"]),
    arrow(2, "每次运行一行"),
    step(2, 9, "5 次折叠成一个判断",
         "单次运行几乎说明不了什么:同一条正确的性质在 litestar\n"
         "上测得的命中率只有 33%,一次没找到,既可能是能力不行,\n"
         "也可能只是这次手气差。重复 5 次、报命中次数,才分得开\n"
         "这两件事。",
         ["dataset/aggregate.py"]),
    arrow(2, "稳定命中 / 不稳定 / 从未命中"),
    step(2, 10, "事前可算的筛选量",
         "不跑也能算的指标,用来事先判断一个样本值不值得测。\n"
         "例如:被改的函数读了多少个自由变量、其中几个来自框架\n"
         "上下文 —— 那些是测试给不出来的值,给不出来就触发不了。",
         ["dataset/check_i3.py"]),
    (None, 0.030),
    note(2, "最终产出", size=13, color=COLS[2][4], weight="bold"),
    (None, 0.012),
    note(2, "table1_cve.csv        样本本身:缺陷是什么\n"
            "table2_results.csv    每条性质:提了什么、结果如何\n"
            "table3_stability.csv  每个样本:5 次里命中几次",
         size=9.8, mono=True, align="left"),
]

# ─── 先量出每列用到哪儿,再画底色,最后画内容 ───
bottoms = {}
for col, items in PLAN.items():
    y = Y_TOP
    for _, h in items:
        y -= h
    bottoms[col] = y

band_bottom = min(bottoms.values()) - 0.028
for i, (name, sub, face, edge, accent, x0, x1) in enumerate(COLS):
    ax.add_patch(FancyBboxPatch((x0 - 0.013, band_bottom), x1 - x0 + 0.026,
                                0.912 - band_bottom,
                                boxstyle="round,pad=0.004,rounding_size=0.010",
                                fc=face, ec=edge, lw=1.4, zorder=0))
    ax.text(x0, 0.895, name, fontsize=14.5, fontweight="bold", color=INK, va="top")
    ax.text(x0, 0.867, sub, fontsize=10.4, color=GREY, va="top")

for col, items in PLAN.items():
    y = Y_TOP
    for draw, h in items:
        if draw is not None:
            draw(y)
        y -= h

# 跨列箭头
for xa, xb, label in [(0.325, 0.340, "指向修复前的代码"),
                      (0.660, 0.675, "运行产物")]:
    ym = (Y_TOP + band_bottom) / 2
    ax.add_patch(FancyArrowPatch((xa, ym - 0.085), (xb, ym - 0.085), arrowstyle="-|>",
                                 mutation_scale=18, lw=2.0, color="#6b7280", zorder=6))
    ax.text((xa + xb) / 2, ym - 0.070, label, fontsize=9.6, color="#4b5563",
            ha="center", va="bottom", fontweight="bold", rotation=90, zorder=6)

ax.text(0.5, 0.988, "agentic PBT × 真实 CVE:全流程与对应代码", fontsize=21,
        fontweight="bold", color=INK, ha="center", va="top")
ax.text(0.5, 0.952,
        "LLM agent 自动写性质测试找缺陷,但「找得好不好」原本只能靠人抽检。"
        "把每个项目退回修复前一刻,就有了标准答案。",
        fontsize=11.8, color=GREY, ha="center", va="top")
ax.text(0.5, band_bottom - 0.022,
        "方框右下角 = 真正执行这一步的代码文件        "
        "橙色标记 = 为「让规约可追溯」新增的步骤        "
        "重画:/opt/miniconda3/bin/python docs/draw_pipeline.py",
        fontsize=9.6, color=GREY, ha="center", va="top")

for ext in ("png", "pdf"):
    fig.savefig(f"docs/pipeline.{ext}", dpi=200, bbox_inches="tight", facecolor="white")
print(f"写出 docs/pipeline.png 与 .pdf  (三列底边 {bottoms})")
