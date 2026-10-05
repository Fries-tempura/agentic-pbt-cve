# Pilot Run 1 — 4 个 CVE 样本的首轮实验

**日期**:2026-10-03
**目的**:检验 `agentic-pbt` 的 agent(`hypo.md`)能否在已知 CVE 的修复前代码上,
独立提出补丁所隐含的那条 property,并据此发现同一个缺陷。

---

## 1. 实验设计

### 1.1 要回答的问题

| 编号 | 问题 |
|---|---|
| Q1 | agent 能不能提出补丁隐含的那条 property? |
| Q2 | 提出之后,能不能写出**撞得出来**的策略? |
| Q3 | hypo.md 的铁律(只测代码声称的性质)会不会挡住安全类 property? |
| Q4 | 私有函数(带下划线)会不会因为"优先公开 API"的指引被跳过? |

### 1.2 样本选取

从 `PILOT_SET.md` 的 16 个样本里取 4 个,**刻意覆盖不同的 property 类型**,
而不是取最容易的 4 个:

| # | 样本 | 组 | 补丁隐含的 property | 选它是为了测 |
|---|---|---|---|---|
| 1 | litestar | A | **单射性**(八种模板里的 Invariants) | Q1/Q2/Q4 的基线 —— 如果这个都不行,说明流程有问题 |
| 2 | eml-parser | A | **蜕变**:提取结果对编码不变 | 铁律挡不挡得住安全性质 |
| 3 | configobj | A | **ReDoS**(耗时有界) | 八种模板里**没有**这一类,看会不会漏 |
| 4 | mako | B | **路径穿越**(代码不会声称) | Q3 的对照组 |

### 1.3 判定口径

| 判定 | 含义 |
|---|---|
| **命中** | agent 提的 property 蕴含 ground truth,且测出同一类失败输入 |
| **擦边** | 测了正确的函数/方向,但 property 太弱没触发,或触发了别的 bug |
| **未命中** | 完全没往这个方向提 |
| **平台不可达** | property 提对了,但 CVE 在当前操作系统上物理不可能成立 |

(第四类是跑完之后才发现需要的 —— 见实验 4。)

---

## 2. 实验设置

### 2.1 环境

```
macOS 14.4 (arm64)          Python 3.14.7
Claude Code 2.1.236         模型 opus
hypothesis 6.168.3          pytest 9.1.1
```

### 2.2 被测代码

每个样本一个**独立 venv**,包从 `checkouts/` 以可编辑模式装入 —— 即
**agent 读到和 import 到的都是打补丁前的源码**:

```bash
python3 -m venv envs/<pkg>
envs/<pkg>/bin/pip install -e dataset/checkouts/<CVE>__<pkg>
envs/<pkg>/bin/pip install pytest hypothesis
```

| venv | 装入的版本 | 来源 checkout |
|---|---|---|
| litestar | 2.19.0 | `CVE-2026-25480__litestar` |
| eml-parser | 0.1.dev1+gc18bbb2b | `CVE-2026-55618__eml-parser` |
| configobj | 5.0.8 | `CVE-2023-26112__configobj` |
| mako | 1.3.12.dev0 | `CVE-2026-44307__mako` |

每个 checkout 的 HEAD 都停在 `patch_commit^`,跑之前逐个验证过漏洞代码确实在位。

### 2.3 调用方式

**复刻 `run.py` 的做法**,写成 `runs/go.sh`:

```bash
export VIRTUAL_ENV="$ROOT/$VENV"
export PATH="$ROOT/$VENV/bin:$PATH"     # 让 agent 裸写的 python/pytest 落到这个 venv
unset PYTHONHOME
cd "$ROOT/$WORKER"
claude --output-format json -p "/hypo $TARGET" \
  --allowedTools "Bash(python:*)" "Bash(pytest:*)" \
     "Edit(*.py)" "Edit(*.md)" "Write(*.py)" "Write(*.md)" \
     "Update(*.py)" "Update(*.md)" "Todo" "WebFetch" \
  --add-dir "$ROOT/$VENV" --add-dir "$CHECKOUT" \
  --permission-mode acceptEdits --model opus
```

每个 run 一个独立沙箱 `runs/<name>/`,里面放一份 `.claude/commands/hypo.md`。
**`hypo.md` 用的是仓库里的原版,未做任何修改。**

### 2.4 给 agent 的目标

**只给模块名,不点名函数,也不提 CVE。** agent 不知道自己在被考。

```
/hypo litestar.stores.file
/hypo eml_parser.routing
/hypo configobj.validate
/hypo mako.lookup
```

### 2.5 开销

4 个 run 并行跑:

| run | 耗时 | turns | 成本 |
|---|---|---|---|
| litestar | 950 s | 59 | $3.03 |
| eml-parser | 223 s | 37 | $1.68 |
| configobj | 413 s | 42 | $2.96 |
| mako | 384 s | 42 | $2.39 |
| **合计** | **墙钟 ~16 min** | **180** | **$10.06** |

折合**每个样本约 $2.5**。按这个单价,跑完 PILOT_SET 全部 16 个约 $40,
跑完 tier A 全部 621 条约 $1,550。

---


## 3. 结果总表

| # | 样本 | 组 | 预期 property | 判定 | 说明 |
|---|---|---|---|---|---|
| 1 | litestar | A | 单射性 | **命中** ✅ | 找到 CVE,修复建议与真实补丁等价 |
| 2 | eml-parser | A | HTML 实体绕过(蜕变) | **未命中** ❌ | 模板现成,但**代码从未声称「URL 提取应对编码免疫」** |
| 3 | configobj | A | ReDoS | **未命中** ❌ | 零耗时测试 |
| 4 | ~~mako~~ | B | 路径穿越 | **作废** 🚫 | CVE 只在 Windows 上成立,在 macOS 上物理不可达 —— **不计入命中率** |

> **命中率:1/3**(litestar ✅ / configobj ❌ / eml-parser ❌)。mako 作废,不计入分母。
>
> eml-parser 首跑因目标指错作废,2026-10-05 用 `eml_parser.parser` 重跑,仍未命中,
> 但原因与 configobj 不同 —— 见第 5 节与 `PATCH_VS_FOUND.md`。
> mako 被剔出分母 —— 它测的是操作系统,不是 agent。详见第 7 节。

**副产物**:4 次运行共产出 **6 份 bug report,全部不是 CVE**,但看上去都是真 bug。

---

## 4. 实验 1:litestar — 命中

**目标**:`/hypo litestar.stores.file`(模块级,不点名函数)

### agent 的推理轨迹

1. 先写朴素写法:`@given(st.text(), st.text())` + `k1 != k2 ⟹ f(k1) != f(k2)`,**通过了**
   —— 两个独立随机字符串几乎撞不出碰撞对
2. 撞到了另一个失败(非 BMP 字符导致 `set()` 静默失败)
3. **按 hypo.md 第 5 步做了 triage**:写了 ASCII-only 版本排除 unicode 干扰
4. **缩小字母表**到 `"0123456789ab-_/:."`(数字 + 分隔符),让碰撞空间变得可探索
5. 加了集合式写法 `len({f(k) for k in ks}) == len(ks)`
6. 撞出 `['-', '45'] -> ['45', '45']`
7. 写了**应用层复现**:`GET /a45b` 被返回 `GET /a-b` 的缓存响应

### 与真实补丁对比

```diff
真实补丁:  return hashlib.blake2s(name.encode()).hexdigest()
agent 建议: return hashlib.sha256(name.encode("utf-8")).hexdigest()
```

agent 还独立指出了真实补丁同样关心的两点:文件名长度无上限、`str.isalnum()` 对大量非 ASCII
字符返回 True。

### 推翻了一个事前预测

`_safe_file_name` 是**私有函数**,而 hypo.md 明确写着优先测公开 API。
我事前预测 agent 会跳过它 —— **没有**。它同时在私有函数层和公开 API 层(`set`/`get`/`delete`
互不干扰)写了等价性质。

### 附带发现的第二个 bug

```python
except OSError:
    pass          # file.py:_write_sync
```

长 key 展开后文件名超过 255 字节 → `OSError` → **被静默吞掉,`set()` 什么也没存**;
而 `get()` 只捕获 `FileNotFoundError`,`OSError` 直接抛出 → HTTP 500。

---

## 5. 实验 2:eml-parser — 未命中(证据缺失)

**目标**:`/hypo eml_parser.routing`

补丁前的 docstring 写着:

```
Remove nested parenthesis, until none are present.
Returns: str: Return a string with all parenthesis removed.
```

这是一条**代码公开违反的显式声称**(`noparenthesis(')')` 返回 `')'`)。
按铁律,这应该是最容易命中的样本。

### 实际发生了什么

agent **确实测了这个函数**,但它写的是:

```python
# Property 3: noparenthesis() -- "Remove nested parenthesis, until none are
# present." -> running it again must be a no-op (fixed point).
def test_noparenthesis_idempotent(line):
    once = routing.noparenthesis(line)
    assert routing.noparenthesis(once) == once
```

实测对比:

```
agent 的写法(幂等性)            → 通过 ✅
docstring 字面承诺(无括号残留)  → 失败 ❌,失败输入 ')'
```

### 结论

> **铁律被遵守了,但从英文声称翻译成断言的过程中,强度丢失了。**

「until none are present」被读成了「不动点」,而不是「none are present」。
**一条后置条件被弱化成了不变量。** 不变量成立,后置条件不成立。

这不是 hypo.md 的哪条规则出了问题 —— 规则说「只测代码声称的」,agent 照做了;
问题出在**声称的强度在翻译时被削弱**,而 hypo.md 对此没有任何约束。

### 另外

**更正(2026-10-05)**:这个样本的判定后来被推翻了。本节原本把 CVE 写成 ReDoS,
这是错的 —— CVE-2026-55618 是 **CWE-116,HTML 实体导致 URL 提取被绕过**,代码在
`eml_parser/parser.py`。那个 commit 一次修了三件事,`routing.py::noparenthesis` 的改动
只是捎带的性能优化(二次→线性)。

**我把 agent 指向了 `eml_parser.routing`,而 CVE 在 `eml_parser.parser`** ——
它根本够不到。本次实验作废,不计入命中率。详见 `PATCH_VS_FOUND.md` 第 3 节。

上面那条"后置条件被弱化成不变量"的观察仍然成立,只是它与本样本的 CVE 无关。
agent 另外找到了一个真 bug:`parserouting` 在 Received 头的括号注释里含 `" from "` 时抛 `KeyError`。

---

## 6. 实验 3:configobj — 未命中

**目标**:`/hypo configobj.validate`

补丁是**一行正则**:

```diff
-    _func_re = re.compile(r'(.+?)\((.*)\)', re.DOTALL)
+    _func_re = re.compile(r'([^\(\)]+?)\((.*)\)', re.DOTALL)
```

agent 写了 5 个文件、多条性质,**没有一条涉及耗时**。

找到的是另一个真 bug:`Validator._parse_with_caching` 刻意复制了 `fun_args`/`fun_kwargs`
(注释说明「to work with *copies* of the data」),却**没复制 `default`**,
于是 `default=list(...)` 的结果是同一个 list 对象,被所有调用共享。

---

## 7. 实验 4:mako — 作废(平台不可达,不计入命中率)

**目标**:`/hypo mako.lookup`

### agent 提出了精确正确的性质

```python
def test_get_template_never_escapes_lookup_directories(uri):
    """TemplateLookup documents that a URI is "appended to each directory and the
    filesystem checked", and Template explicitly rejects a uri that "cannot be
    relative outside of the root path"."""
```

**它引用的不是 docstring,是一条错误消息** —— `mako/template.py:267`:

```python
"it cannot be relative outside of the root path." % self.uri
```

这句话真实存在。agent 没有编造,它从错误消息里挖出了安全不变量。

### 但测试通过了,因为 CVE 在 macOS 上物理不可达

补丁标题:**Fix path traversal via backslash URI on Windows**

```diff
-            u = re.sub(r"^\/+", "", uri)
+            u = re.sub(r"^\/+", "", uri.replace("\\", "/"))
```

`posixpath` 不把 `\` 当分隔符,所以 macOS/Linux 上 `os.path.isfile` 找不到那个文件,
逃逸走不通。实测四种 URI 全部被正确拒绝。


### agent 对正确的性质下了极大功夫 —— 这坐实了"不是 agent 的锅"

最终报告里写着:

> 7,500 个 Hypothesis 例子 + **149,792 个穷举 URI**(由 `..`、`.`、`""`、真假路径段
> 和 0–3 个前导斜杠组合而成)→ **零逃逸**。

而且它自己判断出了这是重点:

> "The path-traversal property is **the project's CVE theme**, so I pushed on it hard."

**它是从 mako 自己的回归测试里看出来的** —— 报告里引用了 `test_lookup.py:130`
对 `//` 前缀绕过的回归测试。这是铁律第三个来源(「别的代码怎么用它」)的一个新形态:
**回归测试本身就是一份安全需求说明书。**

结论很干净:**这次未命中 100% 是平台问题,与 agent 能力无关。**

### 补充:agent 仍找到了同家族的另外两个 bug

`filename_to_uri()` 用 `startswith` 判断文件是否在某个 directory 下,**没做分隔符边界检查**:

```python
TemplateLookup(directories=['/srv/templates'])
filename_to_uri('/srv/templates_backup/secret.html')   # -> '_backup/secret.html'
```

兄弟目录 `templates_backup` 被当成了 `templates` 的内部,返回的 URI 会悄悄解析到**另一个文件**。

以及 `adjust_uri("")` → `IndexError`(`lookup.py:264` 写的是 `uri[0] == "/"`),
从模板代码 `<%include file="${name}"/>` 传空串即可触发。`IndexError` 不是 `MakoException`,
接住模板异常去渲染错误页的应用会漏掉它,变成未处理的 500。

两个都与 CVE 同属路径处理家族,但不是同一个缺陷 —— 仍记为未命中 CVE。

---

## 8. 五条横向结论

### 回到最初的四个问题

| | 问题 | 答案 |
|---|---|---|
| **Q1** | 能不能提出补丁隐含的 property? | **3/4 能**。litestar 单射性 ✅、mako 路径穿越 ✅、eml-parser 测了对的函数但选了弱形式 ⚠️、configobj ❌ |
| **Q2** | 提出之后能不能写出撞得出来的策略? | **能,而且会自我修正**。litestar 的朴素写法先通过了,agent 主动缩小字母表、换集合式写法,然后撞出来 |
| **Q3** | 铁律会不会挡住安全类 property? | **不一定**。mako 从**错误消息**和**既有回归测试**里拿到了依据。铁律的三个来源比想象中宽 |
| **Q4** | 私有函数会不会被跳过? | **不会**。`_safe_file_name` 带下划线,agent 照测不误,而且同时在公开 API 层写了等价性质 |

**一句话**:真正的瓶颈不是 Q1 那种"想不到性质",而是
**Q1 的变体 —— 想到了但写弱了(eml-parser),和模板库里压根没有那一类(configobj)**。


### ① ReDoS 没测,原因是模板库里缺这一类

`hypo.md` 的**八种性质模板里没有「耗时/复杂度」这一类**。
**42 条 property 跨四个样本,零耗时测试。**

→ **要改 prompt。** 建议在八种模板后加第九种:
> **Complexity bounds**: 对任何用户可控输入做正则匹配/解析的函数,
> 运行时间不得随输入长度超线性增长。

这个改动很小,但 tier A 里 ReDoS 占 68 条,影响面大。

### ② 「声称」的翻译会丢强度 —— 这是 hypo.md 的一个真空

eml-parser 的案例说明:铁律只约束了「性质必须有依据」,
**没有约束「翻译时不得削弱」**。后置条件变不变量,测试就从会挂变成会过。

→ 建议加一句:
> 当文档描述的是「函数返回后某条件成立」,直接断言那个条件,
> 不要替换成更弱的不变量(幂等、不动点、类型正确)。

### ③ 我之前对 B 组的悲观预测是错的

我说过「安全漏洞的性质代码从不声称」。mako 反驳了这一点 ——
**错误消息也是一种声称**,而且 agent 会用。

→ B 组不是必然失败。能不能命中,取决于**代码库有没有在某处把那个不变量写出来**。
mako 这一例给出了两个可 grep 的信号,按强度排:

1. **既有的安全回归测试** —— agent 正是靠 `test_lookup.py:130` 判断出"路径穿越是本项目的 CVE 主题"
2. **错误消息** —— `template.py:267` 的 "cannot be relative outside of the root path"

这给数据集提供了一个新筛选维度 `claimed_in_code`:
**grep 代码里有没有相关的回归测试 / 错误消息 / assert / 注释。**

### ④ 平台依赖会制造假阴性,实测影响面 27% ⭐

mako 的 CVE 只在 Windows 上成立。这让我去量了一下这类样本到底有多少。

**已对 tier A 全量扫描**(621 条,612 条可判定),标记来自补丁 diff 里的平台相关原语
(`os.sep` / `os.altsep` / `os.name` / `ntpath` / `isabs` / `splitdrive` / 字面 `\\` / 标题含 Windows):

```
any     511   补丁没碰平台原语,本机可跑
check    95   碰了,方向不明,需人工读 diff
windows   6   标题明说 Windows,当前平台不可达
-------------------
风险样本 101 / 612 = 17%
```

**而风险几乎全部集中在 CWE-22:**

| CWE | 总数 | any | check | windows | 风险率 |
|---|---|---|---|---|---|
| **CWE-22 路径穿越** | 268 | 191 | 73 | 4 | **29%** |
| CWE-601 开放重定向 | 67 | 60 | 7 | 0 | 10% |
| CWE-1333 ReDoS | 68 | 62 | 6 | 0 | 9% |
| CWE-295 证书校验 | 36 | 33 | 1 | 2 | 8% |
| CWE-444 请求走私 | 36 | 34 | 2 | 0 | 6% |
| **CWE-190 整数溢出** | 99 | 99 | 0 | 0 | **0%** |

**这个陷阱基本上是 CWE-22 独有的**,其余类别 0–10%,可以忽略。

#### 一个意外的好处

`PILOT_SET.md` 里提过的另一个问题是 **tier A 严重偏科 —— CWE-22 占 44%**。
而平台过滤恰好最狠地打在 CWE-22 上:

```
过滤前  CWE-22 = 268 / 612 = 44%
过滤后  CWE-22 = 191 / 511 = 37%
```

**一个改动同时缓解了两个问题。**

**注意**:「补丁碰了平台原语」≠「在 POSIX 上一定不可达」,它只是个**筛查信号**,
方向还需要读 diff 确认。所以列名用 `check` 而不是直接判死。

#### 一个必须说的后果:README 的范例样本本身就不可达

`dataset/README.md` 里当作「理想 tier-A 样本」示范的 gradio `safe_join`,补丁标题逐字是:

```
Fix absolute path issue in Windows (#12926)
```

它加的那行 `filename.startswith("/")` 之所以需要,**只因为 `os.path.isabs("/x")`
在 Windows 上返回 `False`**。POSIX 上原有的 guard 本来就拦得住 ——
**这个漏洞在 macOS/Linux 上不存在。**

README 里的解释(「`os.path.isabs("/x")` is `False` on Windows」)其实已经点明了这一点,
只是没往下推一步:**那意味着它作为 POSIX 上的评测样本是无效的。**

#### 已落地的改动

新增 `dataset/platform_scan.py`(stage 2b),给 `dataset.csv` 加两列:

| 值 | 含义 |
|---|---|
| `any` | 补丁没碰任何平台相关原语 → 可以在本机跑 |
| `check` | 碰了,方向不明 → 需人工读 diff |
| `windows` | 提交标题明说 Windows → **当前平台不可达,排除** |

配套 `platform_evidence` 列记录命中了哪些标记,便于复核。

**评测时只收 `platform ∈ {any}`,`check` 人工过一遍,`windows` 留着等 Windows CI。**

### ⑤ 「找到真 bug」≠「找到那个 bug」

4 次运行产出 5 份报告,**4 份不是 CVE**,但看上去都是真的:

```
litestar   长 key → 文件名超 255 字节 → except OSError: pass 静默丢数据 → get() 抛 500
eml-parser parserouting 在 Received 头含 " from " 的括号注释时 KeyError
configobj  default=list(...) 的结果跨调用共享同一个对象
mako       filename_to_uri 用 startswith 没查分隔符,兄弟目录被当成内部
mako       adjust_uri("") → IndexError,不是 MakoException,漏出成 500
```

4 次运行,6 份报告,**CVE 命中率 1/4,但"找到真 bug"率看起来接近 100%**。

这是论文那个「56% valid」现象在 CVE 评测场景下的新形态:
**valid 率可能很高,但 CVE 命中率是另一回事。** 两者必须分开统计。

→ 坐实了 `PILOT_SET.md` 里那条待办:**必须加 `ground_truth_property` 列**,
否则没法机械判定一份报告算不算命中。

---

## 9. 下一步

- [ ] 给 `hypo.md` 加第九种模板(复杂度/耗时),然后**重跑 configobj 和 eml-parser**
      —— 这是一个干净的消融实验,能直接量化那一条 prompt 改动值多少
- [ ] 给 `dataset.csv` 加 `platform` 列,从补丁 diff 自动判定
- [ ] 给 `dataset.csv` 加 `ground_truth_property` 列
- [ ] 加 `claimed_in_code` 列:grep 代码里有没有把该不变量写出来的错误消息/断言/注释
      (mako 证明这个信号有预测力)
- [ ] 扩到 A 组剩余 6 个:pygments、soupsieve、black、dparse、h11、lxml-html-clean

---

## 10. 产物清单

所有运行产物在 `runs/<name>/`(未纳入版本控制)。

```
runs/
├── go.sh                      调用脚本(复刻 run.py)
├── litestar_module/           命中
│   ├── .claude/commands/hypo.md
│   ├── test_file_store.py             朴素写法 —— 通过,没撞出碰撞
│   ├── test_file_store_ascii.py       triage:排除 unicode 干扰
│   ├── test_file_store_collision.py   缩小字母表后 —— 撞出来了
│   ├── test_file_store_longkey*.py    第二个 bug 的追查
│   ├── repro_cache_collision.py       应用层复现:HTTP 缓存投毒
│   ├── repro_longkey_500.py
│   ├── bug_report_..._8yha.md         ← CVE 命中报告
│   └── bug_report_..._qycw.md         ← 长 key 静默丢数据
├── emlparser/                 擦边
│   ├── test_routing_props.py          含 test_noparenthesis_idempotent(弱形式)
│   ├── probe.py / repro.py
│   └── bug_report_eml_parser_routing_..._d72m.md
├── configobj/                 未命中
│   ├── test_validate_props.py
│   ├── probe1.py / probe2.py
│   ├── repro_nan.py / repro_shared_default.py
│   └── bug_report_..._onsx.md
└── mako/                      平台不可达
    ├── test_lookup_props{,2,3}.py
    ├── brute_traversal.py             149,792 个穷举 URI
    ├── probe.py / repro1.py / repro2.py / check_fixes.py
    ├── bug_report_mako_lookup_adjust_uri_..._llio.md
    └── bug_report_mako_lookup_filename_to_uri_..._jioe.md
```

虚拟环境在 `envs/{litestar,eml-parser,configobj,mako}/`。

### 复现这次实验

```bash
# 1. 建环境(以 litestar 为例)
python3 -m venv envs/litestar
envs/litestar/bin/pip install -e dataset/checkouts/CVE-2026-25480__litestar
envs/litestar/bin/pip install pytest hypothesis

# 2. 建沙箱
mkdir -p runs/litestar_module/.claude/commands
cp hypo.md runs/litestar_module/.claude/commands/hypo.md

# 3. 跑
bash runs/go.sh runs/litestar_module "litestar.stores.file" "envs/litestar" \
     "$PWD/dataset/checkouts/CVE-2026-25480__litestar"
```

注意结果**不可复现到逐字相同** —— agent 的每次采样不同(见 `PILOT_SET.md` 提到的
"结果不可复现"这条本质性质)。要得到统计意义上的结论,同一个样本需要重复跑 N 次。
**本次每个样本只跑了 1 次,所有结论都应视为单次观察,不是测量。**
