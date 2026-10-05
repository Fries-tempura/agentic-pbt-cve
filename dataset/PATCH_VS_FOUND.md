# 补丁修了什么 vs agent 找到了什么

Pilot Run 1 的四个样本,逐个核对:**补丁针对的 CVE 缺陷是什么,agent 有没有找到,没找到是为什么。**

数据来源:`properties_all.csv`(42 条 agent 提出的 property)、各 run 的 bug report、
以及每个 CVE 的补丁 diff。

---

## 总表

| 样本 | CVE 缺陷 | 判定 | 没找到的原因 |
|---|---|---|---|
| **litestar** | 文件名编码不是单射 → 缓存投毒 | **命中** ✅ | — |
| **configobj** | 正则二次回溯 ReDoS | **未命中** ❌ | 八种模板里没有「耗时」这一类,42 条 property 零耗时测试 |
| **eml-parser** | HTML 实体混淆的 URL 提取不到 | **未命中** ❌ | 蜕变模板是现成的,但**代码里没有任何地方声称「URL 提取应对编码免疫」** |
| **mako** | 反斜杠路径穿越(仅 Windows) | **实验作废** 🚫 | CVE 在 macOS 上物理不可达 |

**有效样本 3 个,命中 1 个。** mako 作废(平台不可达)。

eml-parser 第一次跑是作废的 —— 我把目标指成了 `eml_parser.routing`,而 CVE 在
`eml_parser.parser`。**2026-10-05 用正确目标重跑后仍未命中**,原因与 configobj 不同,
见第 3 节。

两种未命中指向两条完全不同的改进路线:

```
configobj   →  模板缺失   →  给 hypo.md 加「复杂度/耗时」模板(改 prompt,当天能做)
eml-parser  →  证据缺失   →  补规约来源(真正的研究点)
```

---

## 1. litestar CVE-2026-25480 —— 命中 ✅

### 补丁修了什么

```diff
 def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+    return hashlib.blake2s(name.encode()).hexdigest()
```

### CVE 缺陷是什么

`FileStore` 把 key 转成磁盘文件名。转换规则是「字母数字保留,其他字符换成它的十进制码点」。
**问题是转义产物(数字)和合法字符(数字)属于同一字符集**,没有分隔符也没有转义标记:

```
'a-b'   →  'a' + '45' + 'b'  =  'a45b'
'a45b'  →  'a'+'4'+'5'+'b'   =  'a45b'     ← 原样,因为全是字母数字
```

两个不同的 key 落到同一个文件。NFKD 规范化又加一重(`'①'` 和 `'1'` 都变成 `'1'`)。

`FileStore` 是 litestar 响应缓存、session、限流的后端,所以后果是
**一个 URL 被返回另一个 URL 的缓存内容**(CWE-176 + CWE-20)。

### agent 做了什么

提出了 18 条 property。关键的那条性质(单射性)写了四遍:

| # | 策略 | 结果 |
|---|---|---|
| 4 | `given(k1=keys, k2=keys)`,朴素 `st.text()` | 通过 |
| 6 | 同上,收窄到 ASCII | 通过 |
| 10 | 同上,字母表收窄到 `"0123456789ab-_/:."` | 通过 |
| **13** | `given(ks=st.lists(keys, unique=True))`,断言 `len(set(encoded)) == len(ks)` | **失败,撞出 `['-','45']`** |

前三次用「两个独立 key」,每个例子只检验 1 对;第 13 条用「一组 key 比集合大小」,
每个例子检验最多 28 对。实测在 5000 个例子的预算下:

```
两个独立 key   检验   3,251 对   12 轮撞出 4 次   命中率 33%
一组 key       检验  36,584 对   12 轮撞出 10 次   命中率 83%
```

**四条断言逻辑完全等价,都正确;差别在搜索效率,相差 11 倍。**

### 修复建议 vs 真实补丁

```diff
真实补丁:  hashlib.blake2s(name.encode()).hexdigest()
agent:    hashlib.sha256(name.encode("utf-8")).hexdigest()
```

agent 还独立指出了真实补丁同样关心的两点:文件名长度无上限、`str.isalnum()` 对大量
非 ASCII 字符返回 True。

---

## 2. configobj CVE-2023-26112 —— 未命中 ❌

### 补丁修了什么

```diff
 class Validator(object):
-    _func_re = re.compile(r'(.+?)\((.*)\)', re.DOTALL)
+    _func_re = re.compile(r'([^\(\)]+?)\((.*)\)', re.DOTALL)
```

一行正则。

### CVE 缺陷是什么

`Validator.check()` 用 `_func_re` 解析 check 字符串(如 `integer(0, 10)`)。
原正则的 `(.+?)` 可以匹配左括号本身,于是输入里的左括号越多,回溯路径越多。
实测(全是左括号、没有右括号的输入):

```
输入长度    补丁前       补丁后
   200      0.1 ms     0.001 ms
   400      0.3 ms     0.000 ms
   800      1.1 ms     0.000 ms
  1600      4.8 ms     0.000 ms
  3200     19.1 ms     0.002 ms
```

长度 ×16 → 耗时 ×190,**二次增长**(不是指数)。补丁后是常数时间。
严重度 LOW,场景是「开发者把用户可控的值放进服务端配置文件」。

### agent 做了什么

提出了 13 条 property,质量相当好——**7 条是往返性质**,把八种模板里的 Round-trip
用得很熟:

```
dottedQuadToNum(numToDottedQuad(n)) == n
is_integer(str(n)) == n
v.check(check, o) == o
```

还找到了两个真 bug(`default=list(...)` 跨调用共享对象、`is_float` 边界越界)。

**但 13 条里没有任何一条涉及耗时。**

### 为什么没找到

`hypo.md` 的八种性质模板:

```
不变量 / 往返 / 互逆 / 双实现对拍 / 数学性质 / 合流 / 蜕变 / 单入口不崩
```

**没有「复杂度 / 耗时有界」这一类。**

这不是运气问题——重跑一百次也一样,因为 agent 的性质菜单里压根没有这个选项。
42 条 property 跨四个样本,零耗时测试,是结构性的。

→ 修法:给 `hypo.md` 加第九种模板。tier A 里 ReDoS 有 68 条,影响面不小。

---

## 3. eml-parser CVE-2026-55618 —— 未命中 ❌

### 这个包是干什么的

解析邮件文件(.eml)的库,作者是卢森堡国家级 CERT(GOVCERT-LU)。用途是
**邮件安全分析** —— 把可疑邮件丢进去,它抠出 URL、域名、IP 等"指标",
下游拿去比对威胁情报黑名单。

**它不渲染 HTML**,只对原始文本做正则匹配。

### 补丁修了什么

这个 commit(`Address security advisories (#90)`)**一次修了三件事**,CHANGELOG 写得很清楚:

```
- Reduce the time complexity of receive line parsing from quadratic to linear
- Properly handle HTML entities in extracted URLs            ← 这条才是 CVE
- Catch the RecursionError that can occur when parsing certain headers
```

### CVE 缺陷是什么

CWE-116,代码在 `eml_parser/parser.py`。钓鱼邮件把 URL 用 HTML 实体混淆:

```html
<a href="https:&#47;&#47;phishing&#46;example&#46;com/verify">click here</a>
```

`&#47;` 是 `/`,`&#46;` 是 `.`。**攻击者正是利用了"渲染"和"扫描"的差异**:

| | 看到的是什么 |
|---|---|
| 浏览器(会渲染) | `https://phishing.example.com/verify` —— 正常链接,点了就中招 |
| eml-parser(只正则匹配) | 一串 `&#47;&#46;` —— **匹配不上,扫不出来** |

实测:

```
普通 URL        →  提取到 ['phishing.example.com']   ✅ 能检测
HTML 实体混淆   →  提取到 []                          ❌ 完全漏掉
```

**漏报就是漏洞**:域名没进黑名单比对 → 邮件放行 → 用户点开。

补丁的做法是在匹配之前先解码实体,再从每个已解析的 URL 重新提取一次域名:

```diff
+                # URLs do not necessarily appear as-is in the body, as they may
+                # contain escaped entities. For this reason, we have to extract
+                # the domains again from each parsed URL.
+                for url in list_observed_urls + list_observed_urls_noscheme:
+                    for match in eml_parser.regexes.dom_regex.findall(url):
+                        valid_domain = self.get_valid_domain_or_ip(match.lower())
+                        if valid_domain:
+                            list_observed_dom[match.lower()] = 1
```

### agent 做了什么(2026-10-05 用正确目标 `eml_parser.parser` 重跑)

提出 9 条 property:

```
✅ 滑动窗口覆盖正文每个字符
✅ 切片扫描 == 整体扫描
✅ URL 不论在什么字节偏移都能找到
✅ 任意 header 不崩
✅ 嵌套/畸形 MIME 不崩（2000 例）
❌ ipv4_regex 匹配到的"IP"未必是真 IP
❌ email_force_tld 不是 per-instance 选项
```

**没有一条关于编码或 HTML 实体。**

注意第 2、3 条已经很接近了 —— 都在测"URL 提取"。但它问的是
**「换个位置还找得到吗」**,而不是 **「换个编码还找得到吗」**。差一步。

### 为什么没找到:证据缺失,不是模板缺失

这与 configobj 的失败是两回事:

| | configobj | eml-parser |
|---|---|---|
| 需要的模板 | 耗时/复杂度 | **蜕变性质** |
| 八种模板里有吗 | ❌ **没有** | ✅ **有** |
| 真正的障碍 | 模板缺失 | **没有证据支撑** |

`hypo.md` 的蜕变模板是现成的:

> *Metamorphic: some relationship between `f(x)` and `g(x)` holds, even without
> knowing the correct value for `f(x)`. For example, `sin(π − x) = sin(x)`.*

而「`extract(html) == extract(entity_encode(html))`」正是一条标准的蜕变性质,模板完全够用。

**障碍在铁律那一侧**:代码里没有任何地方写着「URL 提取应当对 HTML 实体免疫」——
没有 docstring,没有注释,调用方也没体现。按
「only test properties that the code is explicitly claiming to have」,
agent 不该提,也确实没提。

> **这是「规约不在代码里」的教科书案例。** 正确行为是常识,但常识没写进代码。

### 顺带:一次 D1(补丁前后对照)实测 ⭐

把补丁后的版本也 checkout 出来(`git worktree`),同一份测试在两版各跑一遍:

| 性质 | 漏洞版 | 修复版 | 自动判定 |
|---|---|---|---|
| **CVE:HTML 实体绕过** | ✗ 域名提不出 | ✓ 提出来了 | **就是这个 CVE** |
| agent bug 1:全局污染 | ✗ 存在 | ✗ **仍存在** | 不是 CVE |
| agent bug 2:假 IP 通过校验 | ✗ 存在 | ✗ **仍存在** | 不是 CVE |

**全自动,不需要人工复核,也不需要 LLM 打分。** 这是 CVE 数据集相比论文那套
「LLM 评分 + 人工抽检 21 份」评测的结构性优势。

另外顺带发现:**agent 找到的两个 bug,补丁一个都没修** —— 它们是真实存在、至今未修的缺陷。
bug 1 尤其严重:构造一个 `EmlParser(email_force_tld=True)` 实例会改写模块级全局变量,
**让进程里所有其他 parser 永久失效**,补丁加的 `else` 分支只在构造新的默认 parser 时才重置。

### 第一次跑为什么作废(保留作为教训)

第一次我给的目标是 `/hypo eml_parser.routing`,而 CVE 在 `parser.py`。

我照着 `vuln_functions` 这一列选的,那一列里确实有 `routing.py::noparenthesis` ——
但那处改动是**捎带的性能优化**(二次→线性),跟 CVE 无关。

> **`enrich_functions.py` 解析出的 `vuln_functions` 是「整个 commit 碰过的函数」,
> 不是「CVE 对应的函数」。** 一个 commit 修多件事时,两者混在同一列,照着选就会选错。

→ 这就是为什么 `ground_truth_property` 必须**按 CVE** 而不是按 commit 标注。

作废的那次运行留在 `runs/emlparser/`,property 表留在
`properties_emlparser_routing_作废.csv`。

### 顺带的一个发现(与本 CVE 无关,但很重要)

第一次运行里 agent 测了 `routing.py::noparenthesis`,那个函数的 docstring 明写着:

```
Returns: str: Return a string with all parenthesis removed.
```

但它写的断言是:

```python
assert noparenthesis(noparenthesis(x)) == noparenthesis(x)    # 幂等 → 通过 ✅
```

而字面承诺:

```python
assert '(' not in out and ')' not in out                       # 失败,输入 ')'
```

**一条后置条件被读成了不变量**,强度丢失,测试照样绿。

这是「散文 → 可执行断言」会**沉默失败**的直接实证 ——
对「喂设计文档给 agent」这个方向是个重要警告。

## 4. mako CVE-2026-44307 —— 实验作废 🚫(平台)

### 补丁修了什么

```diff
# mako/lookup.py
-            u = re.sub(r"^\/+", "", uri)
+            u = re.sub(r"^\/+", "", uri.replace("\\", "/"))

# mako/template.py
-        u_norm = self.uri.lstrip("/")
+        u_norm = self.uri.replace("\\", "/").lstrip("/")
```

提交标题:**`Fix path traversal via backslash URI on Windows`**

### CVE 缺陷是什么

`TemplateLookup` 用 `posixpath` 做路径规范化,而 `posixpath` **不把 `\` 当分隔符**。
所以 `..\..\secrets\creds.txt` 这种 URI 能绕过 `u_norm.startswith("..")` 的 guard。

在 **Windows** 上,操作系统把 `\` 当分隔符,于是 `os.path.isfile()` 真的找到了
目录外的文件 → 逃逸成功。在 **POSIX** 上,`\` 只是个普通字符,文件根本不存在 → 逃逸失败。

实测(macOS):

```
'ok.html'                  -> 命中(正常)
'../secrets/creds.txt'     -> 被拒绝
'..\secrets\creds.txt'     -> 被拒绝
'\..\secrets\creds.txt'    -> 被拒绝
```

**这个漏洞在当前平台上不存在。**

### agent 做了什么

提出了精确正确的性质,依据是 `mako/template.py:267` 的**错误消息**:

```python
"it cannot be relative outside of the root path." % self.uri
```

它还从 mako **自己的回归测试** `test_lookup.py:130` 判断出「路径穿越是本项目的 CVE 主题」,
然后下了大功夫:**7,500 个 Hypothesis 例子 + 149,792 个穷举 URI**,零逃逸。

测试通过是**正确结果** —— 在 POSIX 上确实逃不出去。

顺带找到两个真 bug:`filename_to_uri` 用 `startswith` 没查分隔符边界
(`/srv/templates_backup` 被当成 `/srv/templates` 的内部)、`adjust_uri("")` 抛 `IndexError`。

### 为什么没找到

**不是 agent 的问题。** 它提对了性质、穷举了近 15 万个输入。
CVE 在这个操作系统上物理不可达。

→ 修法:已加 `dataset/platform_scan.py`。tier A 全量扫描结果:
`any=511 / check=95 / windows=6`,风险样本 17%,**且几乎全部集中在 CWE-22(29%)**。

---

## 失败原因归类

「没找到」有四种,原因完全不同,**必须分开统计**:

| 类型 | 样本 | 性质提出了吗 | 重跑有用吗 | 该改什么 |
|---|---|---|---|---|
| **采样没中** | litestar 的 4/6/10 条 | ✅ 提了 | **有**(33% → 多跑几次) | 提示 agent 用高效写法 |
| **模板缺失** | configobj | ❌ 没提 | **没用** | 给 `hypo.md` 加耗时模板 |
| **证据缺失** ⭐ | eml-parser | ❌ 没提 | **没用** | **补规约来源 —— 真正的研究点** |
| **平台不可达** | mako | ✅ 提了 | **没用** | 过滤样本,或上 Windows CI |
| ~~目标指错~~ | ~~eml-parser 第一次~~ | — | — | 已重跑修正 |

**只有「模板缺失」和「证据缺失」是 agent 的真实能力边界**,而且两者的修法完全不同:

```
模板缺失 →  agent 想得到这类性质,只是菜单里没有   →  加一行 prompt 就能验证
证据缺失 →  性质本身没写在代码里任何地方           →  要换规约来源,是研究问题
```

eml-parser 这个案例特别干净:**蜕变模板是现成的,agent 也会用,
但「URL 提取应对编码免疫」这件事代码从没声称过**,所以铁律把它挡在门外。

## property 统计(46 条)

| 包 | property | 失败 | 通过 | 未跑 |
|---|---|---|---|---|
| litestar | 18 | 11 | 5 | 2 |
| configobj | 13 | 3 | 10 | 0 |
| eml-parser | 9 | 3 | 6 | 0 |
| mako | 6 | 3 | 3 | 0 |
| **合计** | **46** | **20** | **24** | **2** |

**46 条 property,零条涉及耗时。** 这是 configobj 失败的结构性原因。

按模板分类,八种模板只用到了四种:

```
不变量          28
往返            12
单入口不崩       4
数学性质(幂等)   2
----------------------
从未用过:  双实现对拍 / 合流 / 蜕变 / 互逆
```

**「双实现对拍」零使用**,而它恰恰是「规约 → 参考实现 → 对拍」这条路线要用的模板。

## 对实验设计的三条修正

1. **选目标要按 CVE,不能按 commit。** eml-parser 的教训:一个 commit 修三件事,
   `vuln_functions` 把 CVE 相关和无关的函数混在一列,照着选就会选错 —— 我第一次就选错了,
   整次运行作废。

2. **跑之前先过 `platform_scan.py`。** mako 的教训:平台不可达的样本只会产生假阴性。

3. **N=1 不足以判定。** litestar 的教训:同一条正确性质,命中率 33%,
   连续三次没中的概率 30%。单次运行区分不了「写法低效」和「运气不好」。

---

## 附:数据文件

| 文件 | 内容 |
|---|---|
| `properties_all.csv` | 42 条 property,15 列(8 列 CVE 元数据 + 7 列 property) |
| `properties_<pkg>.csv` | 按样本拆分 |
| `PILOT_RUN_1.md` | 完整实验记录(设置、过程、横向结论) |
| `PILOT_SET.md` | 16 个候选样本的筛选依据 |
