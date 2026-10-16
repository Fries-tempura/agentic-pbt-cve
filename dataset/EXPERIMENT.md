# 用真实 CVE 评测 agentic PBT

合并自原先的 `PILOT_SET.md`(样本筛选)、`PILOT_RUN_1.md`(实验记录)、
`PATCH_VS_FOUND.md`(逐样本核对)。

---

## 0. 一句话

把 17 个真实 CVE 的项目 checkout 到**修复前一刻**,让 agent 在不知情的前提下测对应模块,
再用补丁判定它有没有找到那个缺陷。**目的不是证明工具好用,是定位它在哪里失效、为什么。**

---

## 1. 为什么用 CVE

上游论文的评测只能算 **precision**:跑 100 个包、产出 984 份报告、人工复核 56% 是真 bug。
它算不出 **recall**,因为不知道「本来应该找到多少个」。

CVE 提供了那个分母:

| | 上游论文的做法 | 本实验 |
|---|---|---|
| 问题 | 在这个模块里**找出任何 bug** | 找出**这一个特定的**缺陷 |
| 判定 | 人工复核 + LLM 打分 | **补丁即标准答案** |
| 能算 | precision | **recall** |
| 难度 | 低,瞎撞也可能中 | 高得多 |

两者互补,不能互相替代。

---

## 2. 测试集 vs 目标集

容易混,先定义清楚:

| | 目标集 | 测试集 |
|---|---|---|
| 是什么 | 工具最终要用在上面的东西 | 研发期用来衡量进步的 |
| 内容 | 任意 Python 代码库 | 17 个已知 CVE 样本 |
| 有标准答案吗 | 没有 | **必须有** |
| 规模 | 无限 | 17 |

**矛盾点**:测试集必须有标准答案,而这个要求本身会扭曲分布。CVE 集偏安全漏洞,
而安全漏洞的「正确行为」恰恰最不可能写在文档里。所以本实验测的是**规约最匮乏时的下界**。

---

## 3. 样本怎么选的

### 3.1 六条筛选标准

前四条来自 PBT 的机制,后两条是跑完实验才补上的。

| # | 条件 | 怎么验证 | 不满足的例子 |
|---|---|---|---|
| ① | **输入可生成** | 看函数签名 | 参数是 `HttpRequest`、已登录 session |
| ② | **错误可断言** | 看补丁加的 guard | 「界面不好看」 |
| ③ | **可隔离调用** | 有没有 `request`/运行时依赖 | Flask 路由、ASGI 中间件 |
| ④ | **确定且廉价** | 有没有网络/IO | 每次调用发网络请求 |
| ⑤ | **平台可达** ⭐ | `platform_scan.py` | **mako:CVE 只在 Windows 上成立** |
| ⑥ | **环境可装** ⭐ | 试装一次 | **django 1.8、taipy 在 Python 3.14 上装不上** |

**判定捷径**:补丁若是「在函数里加了个 if」,那个 if 就是缺失的断言 → 适合;
补丁若是「改权限模型 / 加鉴权 / 改配置默认值」→ 不适合。

### 3.2 一条曾经写错的标准

最初我写的是:

> 安全漏洞的性质**代码从不声称**(没有 docstring 会写「本函数防止路径穿越」)

**mako 和 h11 都反驳了这一点。** 代码里的「声称」不止 docstring:

| 声称的载体 | 实例 |
|---|---|
| **既有的安全回归测试** | mako 的 agent 从 `test_lookup.py:130` 判断出「路径穿越是本项目的 CVE 主题」 |
| **错误消息** | `mako/template.py:267` 的 `"it cannot be relative outside of the root path."` |
| **代码注释** | h11 的 `# we have to throw away the trailing \r\n` —— 注释说要扔 `\r\n`,代码只扔了 2 字节 |

所以这条应改成:**代码库里有没有某处把这个不变量写出来** —— 而且这是可以 grep 的。

### 3.3 最终的 17 个样本

| 样本 | CVE | CWE | 漏洞函数 |
|---|---|---|---|
| litestar | CVE-2026-25480 | 176, 20 | `litestar/stores/file.py::_safe_file_name` |
| configobj | CVE-2023-26112 | 1333 | `src/configobj/validate.py::Validator` |
| eml-parser | CVE-2026-55618 | 116 | `eml_parser/parser.py::CustomPolicy.header_fetch_parse` 等 5 个 |
| pygments | CVE-2026-4539 | 1333, 400 | `pygments/lexers/archetype.py::AtomsLexer / AdlLexer` |
| soupsieve | CVE-2026-86000 | 1333, 400 | (类体常量,未解析) |
| black | CVE-2024-21503 | 1333, 75 | `src/black/strings.py::lines_with_leading_tabs_expanded` |
| dparse | CVE-2022-39280 | 1333, 400 | (merge commit,未解析) |
| h11 | CVE-2025-43859 | 444 | `h11/_readers.py::ChunkedReader.__init__ / __call__` |
| lxml-html-clean | CVE-2026-28348 | 116 | `lxml_html_clean/clean.py::Cleaner` |
| psd-tools | CVE-2026-27809 | 190, 409, 617… | `src/psd_tools/compression/__init__.py::compress / decompress` |
| poetry | CVE-2026-34591 | 22 | `wheel_installer.py::WheelDestination.write_to_fs` |
| cleo | CVE-2022-42966 | 1333 | `src/cleo/ui/table.py::Table._render_cell` |
| uvicorn | CVE-2020-7694 | 116, 94 | `uvicorn/logging.py::AccessFormatter.get_path` |
| python-ldap | CVE-2025-61912 | 116, 170 | `Lib/ldap/dn.py::escape_dn_chars` |
| lxml-html-clean2 | CVE-2026-28350 | 116 | `lxml_html_clean/clean.py::Cleaner.__call__` |
| wlc | CVE-2026-22250 | 295 | `wlc/__init__.py::Weblate.invoke_request / _should_verify_ssl` |
| pypdf | CVE-2026-22691 | 1333, 400 | `pypdf/_reader.py::PdfReader` 等 5 个 |

### 3.4 排除的样本

| 样本 | 排除原因 | 这说明了什么 |
|---|---|---|
| **mako** CVE-2026-44307 | **平台不可达** —— 补丁标题 `Fix path traversal via backslash URI on Windows`,`posixpath` 不把 `\` 当分隔符,macOS 上四种攻击 URI 全被正确拒绝 | tier A 全量扫描:17% 的样本碰了平台相关原语,CWE-22 高达 29% |
| **django** CVE-2015-5145 | **环境腐烂** —— Django 1.8 内嵌 `six`,Python 3.14 导不进来 | 老 CVE 的通病 |
| **taipy** CVE-2026-48544 | **版本不兼容** —— 要求 Python <3.13 | 同上 |
| **twisted** CVE-2014-7143 | **环境腐烂** —— 依赖已从标准库移除的 `cgi` | 同上 |
| **nicotine-plus** CVE-2021-45848 | 需要 GTK/PyGObject 栈 | 重型 GUI 依赖 |
| **oauthlib** CVE-2022-36087 | 补丁改动解析不到函数 | — |

> **README 里当作「理想样本」示范的 gradio `safe_join`,补丁标题是
> `Fix absolute path issue in Windows (#12926)` —— 它也是平台不可达的。**
> 原文已经指出 `os.path.isabs("/x")` 在 Windows 上是 `False`,只是没往下推一步:
> 那意味着它作为 POSIX 上的评测样本是无效的。

---

## 4. 实验设置

### 4.1 环境

```
macOS 14.4 (arm64)        Python 3.14.7
Claude Code 2.1.285       模型 opus
hypothesis 6.168.3        pytest 9.1.1
```

每个样本一个独立 venv,包从 `checkouts/` 以 `pip install -e` 装入 ——
**agent 读到和 import 到的都是打补丁前的源码**,HEAD 停在 `patch_commit^`。

### 4.2 调用方式

复刻 `run.py`,见 `runs/go.sh`。**只给模块名,不点名函数,不提 CVE。**

```
/hypo litestar.stores.file
/hypo configobj.validate
...
```

### 4.3 对 run.py 的两处刻意偏离

两处都是踩坑之后不得不改的,详见第 7 节。

| 偏离 | 原因 |
|---|---|
| `< /dev/null` | `claude -p` 在非 TTY 下会读 stdin,批量脚本的文件重定向会被当成 prompt 吞进去 |
| `bypassPermissions` 替代 `acceptEdits` | agent 常写 `cd DIR; bin/python ...` 这类复合命令,白名单匹配不上而被静默拒绝 |

---

## 5. 结果

> **数据更新中** —— 每个样本重复 5 次的实验正在串行跑。
> 下表是单次运行的结果,方差数据见 `table3_stability.csv`。

### 5.1 单次结果

| 样本 | CVE 缺陷 | 结果 |
|---|---|---|
| litestar | 文件名编码不是单射 → 缓存投毒 | ✅ |
| black | `lines_with_leading_tabs_expanded` ReDoS | ✅ |
| pygments | archetype lexer ReDoS | ✅ |
| dparse | `parse_index_server` ReDoS | ✅ |
| cleo | `Table._render_cell` ReDoS | ✅ |
| h11 | chunk 终止符不校验 → 请求走私 | ✅ |
| psd-tools | zlib 解压无大小上限 → ZIP 炸弹 | ✅ |
| poetry | wheel 成员路径穿越 | ✅ |
| uvicorn | 访问日志未转义 → 日志注入 | ✅ |
| configobj | `_func_re` 二次回溯 ReDoS | ❌ |
| soupsieve | `IDENTIFIER` 正则 ReDoS | ❌ |
| eml-parser | HTML 实体混淆的 URL 提取不到 | ❌ |
| lxml-html-clean | CSS `@import` 过滤被 unicode 转义绕过 | ❌ |
| python-ldap / lxml-html-clean2 / wlc / pypdf | 待复核 | ⏳ |

---

## 6. 逐样本:补丁修了什么 / agent 找到没有 / 为什么

### 6.1 litestar CVE-2026-25480 —— 命中 ✅

**补丁**

```diff
 def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+    return hashlib.blake2s(name.encode()).hexdigest()
```

**缺陷**:转义产物(数字)和合法字符(数字)属于同一字符集,没有分隔符:

```
'a-b'   →  'a' + '45' + 'b'  =  'a45b'
'a45b'  →  'a'  '4' '5'  'b'  =  'a45b'     ← 两个不同的 key 落到同一个文件
```

`FileStore` 是响应缓存/session/限流的后端,缓存 key = `方法 + 路径 + 查询参数`,
完全由 URL 决定 → **一个 URL 能读到另一个 URL 的缓存**。

**agent 的过程 —— 同一条性质写了四遍**

| # | 策略 | 结果 |
|---|---|---|
| 4 | `given(k1=keys, k2=keys)` 朴素 `st.text()` | 通过 |
| 6 | 同上,收窄到 ASCII | 通过 |
| 10 | 同上,字母表收窄到 `0123456789ab-_/:.` | 通过 |
| **13** | `given(ks=st.lists(keys, unique=True))`,断言 `len(set(encoded)) == len(ks)` | **失败,撞出 `['-','45']`** |

**四条断言逻辑完全等价,差别只在搜索效率。** 实测(5000 个例子的预算):

```
两个独立 key   检验   3,251 对   12 轮撞出  4 次   命中率 33%
一组 key       检验  36,584 对   12 轮撞出 10 次   命中率 83%
```

原因是每个例子能检验多少对:

```
写法 A:  k1='.6'  k2='-'                     只能问 1 个问题
写法 B:  ['63_0','27/2','90.9','-']          一次问 6 个问题
         断言 len(set(...)) == len(...) 等价于查遍所有两两组合
```

**修复建议 vs 真实补丁**:agent 给的是 `sha256`,补丁用的是 `blake2s`,等价。
它还独立指出了补丁同样关心的两点:文件名长度无上限、`str.isalnum()` 对非 ASCII 返回 True。

### 6.2 configobj CVE-2023-26112 —— 未命中 ❌(但原因出人意料)

**补丁**:一行正则。

```diff
-    _func_re = re.compile(r'(.+?)\((.*)\)', re.DOTALL)
+    _func_re = re.compile(r'([^\(\)]+?)\((.*)\)', re.DOTALL)
```

**缺陷**:`(.+?)` 能匹配左括号本身,左括号越多回溯路径越多。实测走公开 API:

| 检查字符串长度 | 耗时 |
|---|---|
| 500 | 0.5 ms |
| 1000 | 1.8 ms |
| 2000 | 7.3 ms |
| 4000 | 28.6 ms |
| 8000 | 115.2 ms |

长度 ×16 → 耗时 ×230,**二次增长**。补丁后是常数时间。

**为什么没找到 —— 它想到了,但主动放弃** ⭐

agent 的最终报告里写着:

> *"this checkout is the pre-fix tree for **CVE-2023-26112** (ReDoS in `validate.py`'s
> argument regexes). **I didn't test for that — catastrophic backtracking isn't something
> these property tests would surface** — so it's untouched by this run, not cleared by it."*

三件事同时发生:**认出了 CVE、明确决定不测、给了理由**。而那个理由是错的 ——
pygments、black、dparse、cleo 四个 agent 都用 `time.perf_counter()` 成功测出了 ReDoS:

```python
@given(st.integers(500, 3000), st.sampled_from(['a','0','a-']), st.sampled_from(LEXERS))
def test_linear_time(n, ch, lexer):
    t = time.perf_counter()
    list(lexer.get_tokens('a-a-a.' + ch * n))
    assert time.perf_counter() - t < 2.0
```

> **诊断从「模板缺失」改成「agent 对 PBT 能力边界的自我认知是错的」。**
> 前者要加模板,后者只要在 prompt 里说明耗时性质在范围内 —— 后者便宜得多。

### 6.3 eml-parser CVE-2026-55618 —— 未命中 ❌

**这个包是干什么的**:解析邮件文件,作者是卢森堡国家级 CERT。用途是**邮件安全分析** ——
抠出 URL、域名、IP 等指标,下游拿去比对威胁情报黑名单。**它不渲染 HTML**,只做正则匹配。

**缺陷**:钓鱼邮件把 URL 用 HTML 实体混淆:

```html
<a href="https:&#47;&#47;phishing&#46;example&#46;com/verify">click here</a>
```

攻击者利用的是**渲染和扫描的差异**:

| | 看到的是什么 |
|---|---|
| 浏览器(会渲染) | `https://phishing.example.com/verify` —— 点了就中招 |
| eml-parser(只正则匹配) | 一串 `&#47;&#46;` —— **扫不出来** |

实测:

```
普通 URL        →  提取到 ['phishing.example.com']   ✅ 能检测
HTML 实体混淆   →  提取到 []                          ❌ 完全漏掉
```

**漏报就是漏洞**:域名没进黑名单比对 → 邮件放行 → 用户点开。

**为什么没找到:证据缺失,不是模板缺失**

| | configobj | eml-parser |
|---|---|---|
| 需要的模板 | 耗时/复杂度 | **蜕变性质** |
| 八种模板里有吗 | ❌ 没有 | ✅ **有** |
| 真正的障碍 | 自我设限 | **代码里没有任何地方声称过** |

`hypo.md` 的蜕变模板是现成的,而「`extract(html) == extract(entity_encode(html))`」
正是标准的蜕变性质。障碍在铁律那一侧:没有 docstring、没有注释、调用方也没体现。

> **这是「规约不在代码里」的教科书案例。** 正确行为是常识,但常识没写进代码。

**第一次运行作废的教训**

第一次我给的目标是 `/hypo eml_parser.routing`,而 CVE 在 `parser.py`。我照着
`vuln_functions` 选的,那一列里确实有 `routing.py::noparenthesis` —— 但那处改动是
**捎带的性能优化**(二次→线性),跟 CVE 无关。这个 commit 一次修了三件事:

```
- Reduce the time complexity of receive line parsing from quadratic to linear   ← routing.py
- Properly handle HTML entities in extracted URLs                               ← CVE,parser.py
- Catch the RecursionError when parsing certain headers                         ← parser.py
```

> **`vuln_functions` 是「整个 commit 碰过的函数」,不是「CVE 对应的函数」。**
> 照着它选测试目标会选错 —— 我就选错了,整次运行作废。

### 6.4 h11 CVE-2025-43859 —— 命中 ✅

**缺陷**:chunked 编码里,每个 chunk 之后应该是 `\r\n`,但代码只是**扔掉 2 个字节**,
不检查内容。两个 HTTP 解析器对畸形 body 的理解不一致 → 请求走私。

**依据在注释里**:

```python
class ChunkedReader:
    def __init__(self):
        self._bytes_in_chunk = 0
        # After reading a chunk, we have to throw away the trailing \r\n; ...
        self._bytes_to_discard = 0
```

**注释说要扔掉的是 `\r\n`,代码却只数了 2 个字节。** agent 一次就写对了:

```
test_chunked_rejects_bad_chunk_terminator   →  失败
```

不像 litestar 迭代四次。**典型的「代码里有声称」的样本。**

### 6.5 psd-tools / poetry —— 命中 ✅(推翻了「安全性质测不了」的预测)

| 样本 | agent 提的性质 | 补丁加的 |
|---|---|---|
| **poetry** | 「从 wheel 装出来的文件必须落在 scheme 目录内」,撞出 `extra_member='../payload.py'` | `if not target_path.is_relative_to(target_dir): raise ValueError(...)` |
| **psd-tools** | 「解压输出大小必须等于 w×h×depth/8」 | `_safe_zlib_decompress(data, max_length)` |

两个都是安全类性质,两个都中了。

### 6.6 mako CVE-2026-44307 —— 作废 🚫(平台不可达)

**agent 做得非常好,但找不到不存在的东西。**

它提出了精确正确的性质,依据是 `mako/template.py:267` 的**错误消息**:

```python
"it cannot be relative outside of the root path." % self.uri
```

还从 mako **自己的回归测试** `test_lookup.py:130` 判断出「路径穿越是本项目的 CVE 主题」,
然后下了死功夫:**7,500 个 Hypothesis 例子 + 149,792 个穷举 URI → 零逃逸**。

实测(macOS):

```
'ok.html'                  →  正常加载
'../secrets/creds.txt'     →  被拒绝
'..\secrets\creds.txt'     →  被拒绝
'\..\secrets\creds.txt'    →  被拒绝
```

机制:`posixpath` 不把 `\` 当分隔符,所以 POSIX 上文件根本不存在;Windows 上
操作系统把 `\` 当分隔符,于是 `os.path.isfile()` 真的找到了目录外的文件。

**测试通过是正确结果。这次未命中 100% 是平台问题,与 agent 能力无关。**

顺带找到两个真 bug:`filename_to_uri` 用 `startswith` 没查分隔符边界
(`/srv/templates_backup/x` 被当成 `/srv/templates` 的内部)、`adjust_uri("")` 抛 `IndexError`。

---

## 7. 实验过程中踩的三个坑

三个都是**失败不报错**,只能靠结果看起来不对劲才发现。记下来是因为它们会直接污染统计。

| # | 坑 | 表现 | 后果 | 修法 |
|---|---|---|---|---|
| 1 | **`claude -p` 会读 stdin** | 运行正常完成 | 批量脚本的 `done < samples.tsv` 把整个样本表(**含 CVE 编号**)喂进 prompt,**49 次运行污染** | `< /dev/null` |
| 2 | **白名单匹配不上复合命令** | `claude_result.json` 正常生成、退出码 0 | agent 写 `cd DIR; bin/python ...` 被静默拒绝,summary 里写着 "inconclusive",**整次运行作废却不报错** | 放宽到 `bypassPermissions` |
| 3 | **配额上限** | 退出码 0,1 秒返回 | 8 路并发打满配额,**66 次运行 1 秒失败**,`is_error=True` 但不影响退出码 | 改串行 + 撞上限自动等待重试 |

坑 3 最危险:如果不是「每个样本恰好 1/5」这个过于整齐的分布让我起疑,
这批空跑会被当成「未命中」直接进统计,得出「命中率 20%」的错误结论。

> **教训:批量实验必须逐条检查 `is_error` 和 summary 开头,不能只看文件存在。**

---

## 8. 曾经写下、后被数据推翻的结论

记录这些是因为它们都来自 N=4 时的过度概括,而 N=4 时每种失败模式**各只观察到一例**。

| 当时的结论(N=4) | 后来的证据 | 现状 |
|---|---|---|
| ReDoS 必然失败,因为八种模板没有耗时类 | pygments / black / dparse / cleo **四个都中了**,agent 自己会写 `perf_counter` | **推翻** |
| B 组(安全性质)会失败,因为代码不声称 | poetry、psd-tools **全中**;mako 也提出了正确性质 | **推翻** |
| 安全漏洞的性质代码从不声称 | mako 从**错误消息**、h11 从**代码注释**、mako 还从**既有回归测试**拿到依据 | **推翻** |
| 「预言强度 B0–B3」能预测命中 | configobj 判 B0(最该中)却没中;poetry/psd-tools 判难却中了 | **证伪,分类作废** |

**唯一还站得住的结构性假设**:「编码不变性」这一类(eml-parser、lxml-html-clean)
两个都没中。但这也只有 N=2,需要更多样本。

---

## 9. 数据文件

| 文件 | 内容 |
|---|---|
| `table1_cve.csv` | 测试集定义,每个 CVE 一行(含组别/平台/状态) |
| `table2_results.csv` | 每条 property 一行,`cve_id` 外键 |
| `table3_stability.csv` | 每个样本重复 N 次的命中次数与稳定性分类 |
| `properties_<包>.csv` | 按样本拆分的 property 表 |
| `hit_raw.csv` | 自动命中判定的原始输出(需人工复核) |
| `dataset.csv` | 完整 CVE 语料,2942 行 |

### 脚本

| 脚本 | 作用 |
|---|---|
| `build_dataset.py` | OSV 批量导出 → `dataset.csv` |
| `enrich_functions.py` | 补丁 diff → `vuln_functions` |
| `platform_scan.py` | 筛查只在 Windows 上成立的 CVE |
| `materialize.py` | clone 到 `patch_commit^` |
| `extract_properties.py` | 从 transcript 还原 agent 提出过的每条 property |
| `classify_hit.py` | 自动判定一次运行有没有找到 CVE |
| `aggregate.py` | 把 N 次重复折叠成稳定性分类 |

---

## 10. 下一步

- [ ] 跑完 17 样本 × 5 次,填 `table3_stability.csv`,把每个样本归入
      **稳定命中 / 不稳定 / 从未命中** 三档 —— 只有第三档才是结构性缺失
- [ ] 补充「编码绕过」类样本到 5 个以上,验证唯一还活着的假设
- [ ] 跑 `hypo_v2.md`(两步走版本)对照:强制 agent 先写下
      `CLAIM-n / evidence / claim` 再写断言,看能否
      ① 让 configobj 不再自我设限 ② 让 eml-parser 提出编码不变性
