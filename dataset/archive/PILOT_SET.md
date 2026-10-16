# Pilot Set — 适合 PBT 检测的 CVE 样本

从 `dataset.csv` 里筛出的 16 个样本,每个都已 clone 到 `checkouts/`,HEAD 停在
`patch_commit^`(打补丁前的漏洞状态),并逐个验证过漏洞代码确实存在。

筛选日期:2026-10-03

---

## 筛选标准

一个 CVE 适合 PBT 检测,要同时满足四条:

| 条件 | 含义 | 反例 |
|---|---|---|
| ① 输入可生成 | 参数是 `str`/`bytes`/`int`/`Path` 这类 Hypothesis 能造的值 | 参数是 `HttpRequest`、已登录 session |
| ② 错误可断言 | 能写成一条对所有输入成立的 `assert` | 「界面不好看」 |
| ③ 可隔离调用 | import 进来就能调,不用搭运行时 | Flask 路由、ASGI 中间件 |
| ④ 确定且廉价 | 要跑几百上千次 | 每次调用发网络请求 |

还有一条针对本实验目的(观察 agent 是否找到 patch 关心的那个 bug)的附加条件:

> **⑤ property 可发现** — agent 能从代码本身推出来,不需要安全领域知识。

这条最关键。`hypo.md` 的铁律是「只测代码明确声称的性质」,而**安全漏洞的性质代码从不声称**
(没有 docstring 会写「本函数保证不发生路径穿越」)。所以按 ⑤ 排序:

```
ReDoS / 往返 / 单射  >  编解码转义  >  C扩展崩溃  >  纯函数路径穿越
```

**判定捷径**:补丁若是「在函数里加了一个 if」,那个 if 就是缺失的断言 → 适合;
补丁若是「改权限模型 / 加鉴权 / 改配置默认值」→ 不适合。

---

## A 组:property 代码自己声称(10 个)

这组不受上面那条铁律限制,是实验的主力。

| # | CVE | 包 | CWE | 补丁规模 | 漏洞函数 | 隐含的 property |
|---|---|---|---|---|---|---|
| 1 | CVE-2026-25480 | **litestar** | 176, 20 | 1 文件 +12/-4 | `litestar/stores/file.py::_safe_file_name(name: str) -> str` | **单射性**:`k1≠k2 ⟹ f(k1)≠f(k2)` |
| 2 | CVE-2026-28348 | **lxml-html-clean** | 116 | 1 文件 +21/-1 | `lxml_html_clean/clean.py::Cleaner` | **蜕变**:`clean(转义后的x) == clean(x)` |
| 3 | CVE-2023-26112 | configobj | 1333 | **1 行正则** | `src/configobj/validate.py::Validator`(入口 `.check(check: str, value)`) | 解析耗时有界 |
| 4 | CVE-2015-5145 | django | 1333 | **1 行正则** | `django/core/validators.py::URLValidator`(`domain_re`) | 校验耗时有界 |
| 5 | CVE-2026-4539 | pygments | 1333 | **3 行正则** | `pygments/lexers/archetype.py::AtomsLexer / AdlLexer` | lexing 耗时有界 |
| 6 | CVE-2026-86000 | soupsieve | 1333 | **1 行正则** | `soupsieve/css_parser.py`(`IDENTIFIER`,入口 `sv.compile()`) | 选择器解析耗时有界 |
| 7 | CVE-2024-21503 | black | 1333 | 1 文件 +6/-12 | `src/black/strings.py::lines_with_leading_tabs_expanded(s: str) -> List[str]` | 耗时有界 |
| 8 | CVE-2026-55618 | eml-parser | 116 | 7 文件 +104/-23 | `eml_parser/routing.py::noparenthesis(line: str) -> str`<br>`eml_parser/parser.py::header_fetch_parse(name: str, value: str)` | **docstring 显式写了**:`noparenthesis('a((b)c(d') == 'a(c(d'` |
| 9 | CVE-2025-43859 | h11 | 444 | 2 文件 +13/-10 | `h11/_readers.py::ChunkedReader.__call__(buf)` | 纯状态机,畸形 chunked 不许通过 |
| 10 | CVE-2022-39280 | dparse | 1333 | 2 文件 +7/-5 | `dparse/parser.py::Parser.parse_index_server(line: str)` | 解析耗时有界 |

**两个最佳样本**:

`litestar` —— 漏洞代码是

```python
def _safe_file_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
```

`"a-b"` → `"a45b"`,而字面量 `"a45b"` 也 → `"a45b"`。两个不同的 key 落到同一个文件。
单射性是教科书级的 PBT property,Hypothesis 几秒就能撞出来,且完全不需要安全知识。

`lxml-html-clean` —— cleaner 的契约本来就是「清洗后不含危险内容」,补丁新增的
`_decode_css_unicode_escapes(style)` 是纯字符串函数,docstring 直接写明了意图。
天然有一条蜕变性质:转义不应改变清洗结果。

---

## B 组:需要安全知识的对照组(6 个)

这组的 property 代码**不会**声称,用来量化「铁律 vs 安全漏洞」的冲突有多严重。

| # | CVE | 包 | CWE | 补丁规模 | 漏洞函数 |
|---|---|---|---|---|---|
| 11 | CVE-2026-48544 | taipy | 22 | **1 文件 2 行** | `taipy/gui/extension/library.py::ElementLibrary.get_resource(self, name: str) -> Path` |
| 12 | CVE-2024-11042 | invokeai | 20, 22, 73 | 2 文件 74 行 | `invokeai/app/services/image_files/image_files_disk.py::DiskImageFileStorage.get_path(self, image_name: str, thumbnail: bool) -> Path` |
| 13 | CVE-2026-70493 | open-webui | 1333 | 3 文件 62 行 | `backend/open_webui/tools/knowledge_fs.py::build_matcher(pattern: str, case_insensitive: bool, use_regex: bool) -> tuple` |
| 14 | CVE-2026-27809 | psd-tools | 190 等 | 8 文件 391 行 | `src/psd_tools/compression/__init__.py::compress / decompress(data: bytes, ...)` — 天然往返 |
| ~~15~~ | ~~CVE-2026-44307~~ | ~~mako~~ | 22 | 4 文件 54 行 | **已排除 —— 平台不可达**,补丁标题 "Fix absolute path issue **in Windows**",CVE 在 POSIX 上不成立 |
| 16 | CVE-2026-34591 | poetry | 22 | 2 文件 57 行 | `src/poetry/installation/wheel_installer.py::WheelDestination.write_to_fs(self, scheme, path: str, stream, is_executable)` |

注:#13 open-webui 的 `build_matcher` 其实是 ReDoS,property 可发现;#14 psd-tools 有往返性质。
这两个偏 A 组,但因为是原有 12 个里保留下来的,先放在一起。

> **2026-10-03 更新**:跑完 Pilot Run 1 后,mako(#15)被排除 —— 它的 CVE 只在 Windows 上
> 成立,在 macOS 上物理不可达。详见 `PILOT_RUN_1.md` 第 7 节与横向结论 ④。
> 新增 `platform_scan.py`(stage 2b)筛查这类样本;**B 组现为 5 个**。

**A 组 10 : B 组 5 的配比是刻意的** —— 跑完之后比较两组的检出率,就能量化出
「agent 不会提出代码没声称的安全性质」这一局限到底让检出率掉多少。这个对比本身就是一个结果。

---

## 淘汰清单

### 原有 12 个 checkout 删掉 6 个

这 12 个不是挑出来的,是 `materialize.py --limit` 按 CSV 顺序截的前 12 行
(`todo = todo[:args.limit]`),所以相当于 tier A 的随机抽样。可用率 50%。

| CVE | 包 | 删除原因 |
|---|---|---|
| CVE-2022-0697 | archivy | `def login()` 无参数,Flask 路由,值从 request 取 |
| CVE-2023-30620 | mindsdb | `File.put(self, name)` 是 Flask-RESTX resource,函数体读 `request` |
| CVE-2026-29065 | changedetection-io | Flask blueprint,`download_backup(filename)` 是路由 |
| CVE-2026-28681 | irrd | `set_middleware(app)` 是 ASGI 中间件,漏洞走 Host header |
| CVE-2023-28458 | pretalx | Django management command,要 settings + models + Client 整套 |
| CVE-2026-67429 | flyto-core | 21 文件 322 行,参数全是 `context: Dict`,属于大杂烩重构 |

被删的 6 个里 4 个死于同一个原因:**Web 应用的请求处理函数**。
这正是 tier 按 CWE 分级的代价 —— CWE-22 在 tier A 占 44%,
而路径穿越最常出现的地方恰恰是 Web 应用的文件下载接口,那些全都测不了。

### 新验的 13 个淘汰 2 个 + 2 个待定

| CVE | 包 | 原因 |
|---|---|---|
| CVE-2024-3651 | idna | `patch_commit` 指向 "Release v3.7",只改了 `__version__`,不是修复 |
| CVE-2026-59925 | mistune | `patch_commit` 是 22 文件 +1199/-545 的重构,不是定点修复 |
| CVE-2026-54770 | webob | 核心是纯函数 `urljoin(str,str)->str`,但补丁 406 行属于"重写"而非"加 guard",ground truth 不干净 — 待定 |
| CVE-2025-64076 / CVE-2026-32875 | cbor2 / ujson | 修复全在 C 代码里,见下方问题 ① — 待定 |

**注意:这两个淘汰的原因都是数据质量问题(commit 指错),不是「不适合 PBT」。**

---

## 筛选过程中发现的三个数据集问题

### ① 假阴性:C 扩展的洞被丢掉了

```
cbor2  CVE-2025-64076  →  source/decoder.c       +7/-1    Python 侧只有测试
ujson  CVE-2026-32875  →  ultrajsonenc.c 等 3 个 .c       Python 侧只有测试
```

`enrich_functions.py` 会标成 `no_py_change` 丢弃。但这两个**恰恰是优秀的 PBT 目标** ——
property 是「从 Python 公开 API 喂任意输入,不许崩 / 往返相等」,根本不需要定位 Python 函数。

**建议**:若改动的是 `.c`/`.pyx` 且包有 Python 公开 API,标 `c_ext` 保留,
目标指向**模块**而非函数(对应 `hypo.md` 八种模板里的 Single entry point)。

### ② 误杀:merge commit 不该一律丢

A 组 10 个里有 **3 个是 merge commit**(dparse、configobj、h11),
现在的 `parents=2` 逻辑会直接丢掉。

但 PR 合并进主干时,**`sha^1` 恰恰就是合并前的主干 = 漏洞状态**,完全正确。
本次 clone 就是这么做的,10 个全部 checkout 成功并验证了漏洞代码存在。

**建议**:merge commit 取 parent 1,不要丢。

### ③ `patch_commit` 可能指向 release commit

idna 就是这样。**建议**:加一条检查 —— 若 commit 只改了 `__version__` / `CHANGELOG`,
标为 `release_commit` 剔除。

---

## 下一步

- [x] ~~首轮跑 4 个样本~~ → 见 `PILOT_RUN_1.md`
- [x] ~~加 `platform` 列~~ → `platform_scan.py`,tier A 全量已扫
- [ ] 对新增的 10 个跑 stage 2,把 `vuln_functions` 补进 `dataset.csv`
- [ ] 加一列 `ground_truth_property`:从每个 patch 反推出那条断言,作为比对基准
- [ ] 定义判定口径:**命中**(提的 property 蕴含 ground truth 且测出同一失败输入)/
      **擦边**(方向对但没触发,或触发了别的 bug)/ **未命中**
- [ ] A 组优先跑 —— ReDoS 和往返这两类**可自动判分**(比耗时 / 比往返是否相等),
      不需要人工读报告
- [ ] 跑完对比 A 组 vs B 组检出率

---

## 复现这批 checkout

```bash
# 克隆逻辑等价于 materialize.py,但 merge commit 也取 parent 1
git init && git remote add origin <repo_url>.git
git fetch --depth 2 origin <patch_commit>
git checkout <patch_commit>^
```

当前 `checkouts/` 共 16 个目录,604 MB(已在 `.gitignore` 中)。
