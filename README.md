# agentic-pbt-cve

用**真实 CVE** 给 agentic property-based testing 做可量化评测。

这是 [mmaaz-git/agentic-pbt](https://github.com/mmaaz-git/agentic-pbt) 的扩展。
上游用 LLM agent 从代码里推断 property、合成 Hypothesis 测试、自动找 bug;
但它的评测只能靠 LLM 打分加人工抽检,**没有标准答案**。

本仓库补的就是标准答案:构建一个 PyPI CVE 语料,把每个项目 checkout 到
**修复前一刻**,于是「agent 有没有找到补丁修的那个缺陷」变成可机械判定的问题。

## 新增的东西

### 数据集流水线(`dataset/`)

```
build_dataset.py      OSV 批量导出      ->  dataset.csv        (2942 行,694 个包)
enrich_functions.py   + 补丁 diff       ->  vuln_functions
platform_scan.py      + 平台原语扫描    ->  platform           (新增)
materialize.py        + git clone       ->  checkouts/<CVE>__<pkg>/  @ patch_commit^
extract_properties.py + 运行 transcript ->  properties_*.csv   (新增)
```

- **`platform_scan.py`** —— 路径穿越类 CVE 常常只在 Windows 上成立,
  在 POSIX 上跑只会产生假阴性。tier A 全量扫描:风险样本 17%,其中 CWE-22 占 29%。
- **`extract_properties.py`** —— 从 Claude Code 的 transcript 还原
  agent **提出过的每一条 property**(策略、断言、通过/失败),而不只是最终的 bug report。
  这是分析「为什么有的 bug 找得到、有的找不到」的关键数据。

对上游 `enrich_functions.py` 的三处修复:merge commit 取 parent 1 而非丢弃、
类体内的改动回退到所在类、新增 `--cve` 过滤。

### 实验记录(`dataset/*.md`)

| 文件 | 内容 |
|---|---|
| `PILOT_SET.md` | 16 个候选样本的筛选依据与四条硬条件 |
| `PILOT_RUN_1.md` | 首轮实验完整记录:设置、过程、横向结论 |
| `PATCH_VS_FOUND.md` | 逐个样本核对:补丁修了什么、agent 找到没有、没找到为什么 |

### 运行产物(`runs/`)

每次 `/hypo` 运行写出的测试文件、复现脚本与 bug report。

## 首轮结果

4 个样本,46 条 property:

| 样本 | CVE 缺陷 | 判定 | 原因 |
|---|---|---|---|
| litestar | 文件名编码不是单射 → 缓存投毒 | **命中** | — |
| configobj | 正则二次回溯 ReDoS | 未命中 | **模板缺失**:八种模板里没有「耗时」这一类 |
| eml-parser | HTML 实体混淆的 URL 提取不到 | 未命中 | **证据缺失**:代码从未声称「提取应对编码免疫」 |
| mako | 反斜杠路径穿越(仅 Windows) | 作废 | 平台不可达 |

两种未命中指向两条完全不同的改进路线:

```
模板缺失  ->  agent 想得到这类性质,只是菜单里没有  ->  加一行 prompt 就能验证
证据缺失  ->  性质本身没写在代码任何地方           ->  要换规约来源,是研究问题
```

46 条 property 里**零条涉及耗时**;八种模板只用到四种,
**「双实现对拍」零使用** —— 而它恰恰是「规约 → 参考实现 → 对拍」这条路线要用的模板。

## 复现

```bash
python3 dataset/build_dataset.py
python3 dataset/enrich_functions.py --tier A --workers 6     # 需要 gh 已登录
python3 dataset/platform_scan.py   --tier A
python3 dataset/materialize.py     --tier A --workers 4

# 跑一个样本
python3 -m venv envs/litestar
envs/litestar/bin/pip install -e dataset/checkouts/CVE-2026-25480__litestar pytest hypothesis
bash runs/go.sh runs/litestar_module "litestar.stores.file" "envs/litestar" \
     "$PWD/dataset/checkouts/CVE-2026-25480__litestar"

# 还原它提出过的所有 property
python3 dataset/extract_properties.py --run runs/litestar_module --cve CVE-2026-25480
```

`dataset/checkouts/`、`dataset/.cache/`、`envs/` 不入库,由上面的脚本重新生成。

## 来源与署名

上游项目与论文:

> **Agentic Property-Based Testing: Finding Bugs Across the Python Ecosystem**
> Muhammad Maaz, Liam DeVoe, Zac Hatfield-Dodds, Nicholas Carlini
> [arXiv:2510.09907](https://arxiv.org/abs/2510.09907) ·
> [github.com/mmaaz-git/agentic-pbt](https://github.com/mmaaz-git/agentic-pbt)

`hypo.md`、`run.py`、`scoring.py`、`utils/`、`hypo-plugin/`、`example_packages/`、
`paper/` 均来自上游。上游仓库未附 LICENSE;此处依 GitHub 服务条款对公开仓库的
fork 规定转载,著作权归原作者所有。

上游自己的说明见 [`README.upstream.md`](README.upstream.md)。

## 负责任披露

`runs/` 里的 bug report 由 agent 自动生成,**未经人工复核,也未通知维护者**。
其中 eml-parser 的两份报告涉及上游补丁至今未修复的缺陷,已排除在本仓库之外
(见 `.gitignore`)。引用这些报告前请自行验证,并先联系维护者。
