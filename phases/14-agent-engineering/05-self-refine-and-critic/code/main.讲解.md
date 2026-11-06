# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 05 节 Self-Refine 与 CRITIC：迭代改进输出 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`）；无需 LLM、无需网络

---

## 1. 这份代码在考察什么

这份 124 行的代码用一个玩具任务——"写一个 3 条要点、每条不超过 60 字符、不含已知错误事实的列表"——对比两种迭代改进方式：

1. **Self-Refine**（Madaan 等）：generate → 自我反馈 `feedback_self` → refine，循环直到反馈说"no issues"或达到上限。
2. **CRITIC**（Gou 等）：把反馈换成外部验证器 `verify_external`，依据"参考数据"（一张已知错误事实表）和格式规则给出批评。
3. **共同的循环骨架** `run_loop`：每轮记录输出、批评、是否通过；通过即停，否则 refine；最多 4 轮。

它要让你掌握 evaluator-optimizer 循环的结构：谁生成、谁批评、批评怎样回到生成、何时停止。

但需要特别注意：**demo 中 CRITIC 胜出的原因，并不是讲义所说的"自我批评没发现幻觉"**——自我批评其实发现了问题，是脚本化的生成器只认特定关键词，没有理会它的措辞（详见 3.2、3.3 与测验 Q5）。看懂这一点，能帮你识别很多"演示对比"里的评测陷阱。

> 一句话：**循环骨架是对的，但演示的因果关系是脚本设计出来的**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `KNOWN_WRONG_FACTS` | 模块常量 | 3 条已知错误事实（参考数据） | CRITIC 的外部知识 |
| `Attempt` | dataclass | 一轮的记录：轮次、输出、批评、是否通过 | refine history |
| `generate` | 函数 | 无历史时给出含两处错误的初稿；有历史时按**最后一条批评中的关键词**改写 | generator（脚本化） |
| `feedback_self` | 函数 | 模拟 LLM 自我批评：发现问题时给出含糊的提示 | Self-Refine 的 feedback |
| `verify_external` | 函数 | 模拟工具验证：查错误事实、查条数、查长度 | CRITIC 的 verify |
| `refine` | 函数 | 直接调用 `generate(topic, history)`，忽略 `prev` 和 `critique` 参数 | refine（脚本化） |
| `run_loop` | 函数 | 生成初稿 → 循环（验证 → 记录 → 通过则停 → 精修） | evaluator-optimizer 循环 |
| `print_run` | 函数 | 打印每轮的批评与输出 | trace |
| `main` | 函数 | 分别运行两种模式并总结 | 入口 |

数据流：`run_loop`：`generate(topic, [])` → 第 i 轮：`verify(output)`（`feedback_self` 或 `verify_external`）→ `history.append(Attempt)` → 通过则 `break`，否则 `refine(...)` → `generate(topic, history)` 读取 `history[-1].critique` 的关键词 → 下一轮。

---

## 3. 逐段精讲

### 3.1 `Attempt` 与参考数据

```python
KNOWN_WRONG_FACTS = [
    "paris is the capital of germany",
    "mt everest is in europe",
    "the sun orbits the earth",
]


@dataclass
class Attempt:
    iteration: int
    output: str
    critique: str
    verified: bool
```

- `KNOWN_WRONG_FACTS` 扮演 CRITIC 中"外部工具"的角色——真实系统中会是搜索引擎、知识库、代码解释器或测试。
- `Attempt` 是 refine history 的一条记录。讲义强调 refine 要看到"所有之前的输出和批评"，`history: list[Attempt]` 就是这份历史。
- ⚠️ 第三条"太阳绕地球转"从未被检查（见 3.4）。

### 3.2 `generate` 与 `refine`：脚本化的生成器

```python
def generate(topic: str, history: list[Attempt]) -> str:
    if not history:
        return (
            "- Paris is the capital of Germany\n"
            "- Mt Everest is in Europe\n"
            "- Water boils at 100C"
        )
    last = history[-1]
    if "germany" in last.critique.lower():
        return ("- Paris is the capital of France\n"
                "- Mt Everest is in Europe\n"
                "- Water boils at 100C")
    if "everest" in last.critique.lower():
        return ("- Paris is the capital of France\n"
                "- Mt Everest is in Asia\n"
                "- Water boils at 100C at sea level")
    return history[-1].output


def refine(topic: str, prev: str, critique: str, history: list[Attempt]) -> str:
    return generate(topic, history)
```

- 括号内的多个字符串字面量会被自动拼接，`\n` 分隔三条要点。
- 初稿故意包含两处"幻觉"：巴黎是德国首都、珠峰在欧洲。
- 精修时**只看最后一条批评**里有没有 `germany` 或 `everest`：有就换成下一个版本，否则原样返回上一版输出。
- ⚠️ `refine` 的 `prev`、`critique` 参数都没用到，`topic` 在整个程序里也没被使用；"带完整历史的 refine"实际上只用了 `history[-1]`。
- ⚠️ 第三版输出把 "Water boils at 100C" 改成了 "...at sea level"，而没有任何批评提到这一条——这是脚本作者的"顺手修改"，真实 refine 不应修改未被批评的内容（或至少应解释原因）。
- ⚠️ **关键耦合**：生成器只对含特定关键词的批评作出反应。这意味着哪种批评"有效"，完全取决于措辞是否命中关键词，而不是批评是否正确。

### 3.3 `feedback_self`：模拟的自我批评

```python
def feedback_self(output: str) -> tuple[str, bool]:
    if "Germany" in output and "Paris" in output:
        return "first bullet reads wrong, double-check capital", False
    if "Europe" in output and "Everest" in output:
        return "second bullet's continent looks off to me", False
    return "no issues", True
```

- 它**确实发现了**两处错误，并返回 `False`（未通过）——只是措辞模糊（"capital"、"continent"），不点名具体事实。
- 这种模糊批评在真实 LLM 自评中很常见，讲义也提到自评的弱点；但本 demo 中 Self-Refine 失败的直接原因，是 `generate` 不认识这些措辞（见 3.2），而不是"自评没发现幻觉"。
- 实测：把措辞改成 "Paris is not in Germany…"、"is Everest really in Europe?"，Self-Refine 同样在第 3 轮通过，与 CRITIC 的结果完全相同。
- 区分大小写（`"Germany" in output`），而 `verify_external` 先转小写——两个"验证器"的匹配规则不一致。
- ⚠️ 讲义"动手实现"一节列出的函数名是 `feedback`，代码中是 `feedback_self`。

### 3.4 `verify_external`：模拟的 CRITIC 验证器

```python
def verify_external(output: str) -> tuple[str, bool]:
    text = output.lower()
    for fact in KNOWN_WRONG_FACTS:
        key = fact.split(" is ")[0] if " is " in fact else fact
        if "paris" in text and "germany" in text:
            return f"verifier: 'paris is the capital of germany' contradicts reference data", False
        if "everest" in text and "europe" in text:
            return f"verifier: 'mt everest is in europe' contradicts reference data", False
    if len([l for l in output.splitlines() if l.startswith("-")]) != 3:
        return "verifier: expected 3 bullet lines", False
    if any(len(l) > 60 for l in output.splitlines()):
        return "verifier: bullet exceeds 60 chars", False
    return "verifier: ok", True
```

- 设计意图：先查事实错误，再查格式（3 条、每条长度），返回带"verifier:"前缀、点名具体事实的批评——批评内容"有依据"，这是 CRITIC 的要点。
- ⚠️ **循环形同虚设**：`for fact in KNOWN_WRONG_FACTS` 里，`fact` 和 `key` 都没被使用，循环体是两条写死的检查，每次迭代做同样的事。
- ⚠️ **漏检**：第三条"太阳绕地球转"从未检查。实测 `"- The sun orbits the earth\n- Water is wet\n- Ice is cold"` 返回 `verifier: ok`。
- ⚠️ **误报**：检查的是**整段文本**的关键词共现。实测 `"- Paris is the capital of France\n- Germany borders France\n- Everest is in Asia"` 被判为 "paris is the capital of germany"。
- ⚠️ **边界**：讲义说每条"under 60 chars"，代码用 `> 60`，恰好 60 字符的行能通过（实测）；长度还包含了 "- " 前缀。
- ⚠️ **一次只报一个问题**：发现第一个错误就 `return`，两处错误需要两轮才全部暴露。
- 返回值是自由文本，下游只能靠关键词匹配理解它；配套 skill 要求验证器输出结构化 JSON（pass/fail + violations + suggested_fixes），测验 Q9 给出了结构化版本。
- 第一条 return 里的 `f"..."` 没有任何占位符，`f` 前缀是多余的。

### 3.5 `run_loop`：evaluator-optimizer 循环

```python
def run_loop(topic: str, use_critic: bool, max_iters: int = 4) -> list[Attempt]:
    history: list[Attempt] = []
    output = generate(topic, history)
    verify = verify_external if use_critic else (lambda o: feedback_self(o))
    for i in range(1, max_iters + 1):
        critique, ok = verify(output)
        history.append(Attempt(i, output, critique, ok))
        if ok:
            break
        output = refine(topic, output, critique, history)
    return history
```

- **函数作为值**：`verify` 根据模式指向两个不同的函数，之后的循环代码完全相同——两种方法共用一个骨架，只替换"批评者"。这正是讲义"CRITIC replaces feedback with verify"的代码表达。
- `(lambda o: feedback_self(o))` 等价于直接写 `feedback_self`，lambda 是多余的。
- 停止条件：验证通过，或循环跑满 `max_iters`。讲义推荐的组合条件（"验证器通过，或自评通过且迭代 ≥ 2，或达到上限"）没有实现；Self-Refine 模式下自评第一轮说"no issues"就会直接停止。
- ⚠️ **最后一轮的 refine 被浪费**：最后一轮验证失败后仍然调用 `refine`，结果既不验证也不返回。实测 `max_iters=2` 时 `refine` 被调用 2 次，只有第 1 次的结果被验证过。`max_iters=1` 时，CRITIC 的批评完全没有转化为一次被确认的改进（测验 Q10）。
- 返回的是完整 `history`，调用方用 `history[-1].verified` 判断成败。

### 3.6 `print_run` 与 `main`

```python
    def summary(hist: list[Attempt]) -> str:
        return "passed" if hist and hist[-1].verified else "did not converge"
```

- `summary` 是定义在 `main` 内部的嵌套函数，只在 `main` 中使用。
- `hist and hist[-1].verified`：先判断列表非空再取最后一个元素，利用 `and` 的短路求值避免 `IndexError`。
- 最后两行 "Observation" 是写死的结论："a self-critic can fail to flag its own confident-sounding hallucination"——如 3.3 所示，本 demo 中自评其实标记了问题，这句话描述的是一般规律而不是这次运行的事实。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 两种模式共用 `run_loop`，只替换批评函数 | 清楚展示"CRITIC = 把 feedback 换成 verify" | 无 |
| 脚本化 generate，按批评关键词改写 | 离线、确定 | 批评"有效"取决于措辞而非正确性，导致 demo 的因果关系失真；真实 refine 是 LLM 读取完整历史 |
| 用错误事实表模拟外部工具 | 无需网络 | 写死两条检查、漏检第三条、整段共现导致误报；生产中用搜索/知识库/测试 |
| 自由文本批评 | 易读 | 下游只能关键词匹配；应输出结构化 JSON |
| 发现第一个问题即返回 | 代码简单 | 多个问题要多轮才暴露，增加精修轮次；应一次列出所有 violations |
| 停止条件只有"通过 / 上限" | 简单 | 自评第一轮通过就停，有橡皮图章风险；应实现组合停止条件 |
| 最后一轮失败后仍 refine | 循环写法自然 | 浪费一次 LLM 调用，且返回的是未修正的版本 |
| `max_iters=4` | 与 skill 默认上限一致 | 讲义建议 1–3 轮后转人工 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值 |
| 模块级常量列表 | `KNOWN_WRONG_FACTS = [...]` | 全大写约定为常量 |
| `@dataclass` | `class Attempt` | 自动生成构造函数；`Attempt(i, output, critique, ok)` 按位置传参 |
| 相邻字符串字面量拼接 | `("- Paris ...\n" "- Mt Everest ...\n" ...)` | 括号内多个字符串在编译期自动拼接，适合写多行文本 |
| `str.lower()` + `in` | `"germany" in last.critique.lower()` | 不区分大小写的子串判断 |
| 负索引 | `history[-1]` | 取最后一条记录 |
| 元组返回与解包 | `return "...", False`；`critique, ok = verify(output)` | 一次返回批评文本和是否通过 |
| 条件表达式选择函数 | `verify_external if use_critic else (lambda o: ...)` | 函数是一等对象，可以赋值给变量 |
| `lambda` | `lambda o: feedback_self(o)` | 匿名函数；此处等价于直接引用 `feedback_self` |
| 条件表达式 | `fact.split(" is ")[0] if " is " in fact else fact` | `A if 条件 else B` |
| `str.split` + 索引 | `fact.split(" is ")[0]` | 按子串切分取第一段 |
| `str.splitlines()` | `output.splitlines()` | 按换行切成列表，不含换行符 |
| 列表推导式 + `startswith` | `[l for l in output.splitlines() if l.startswith("-")]` | 过滤出要点行 |
| `any()` + 生成器 | `any(len(l) > 60 for l in output.splitlines())` | 只要有一行超长就为 True |
| `range(1, n + 1)` + `break` | `run_loop` | 轮次从 1 计数，通过即跳出 |
| 嵌套函数 | `main` 中的 `def summary(hist)` | 只在外层函数内可见 |
| `and` 短路 | `hist and hist[-1].verified` | 列表为空时直接返回空列表（假值），不会执行索引 |
| 多余的 f 前缀 | `f"verifier: 'paris is ...' ..."` | 没有 `{}` 占位符时 `f` 前缀无作用（linter 会提示） |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，`cd code && python3 main.py`）：

```text
======================================================================
SELF-REFINE and CRITIC — Phase 14, Lesson 05
======================================================================

Self-Refine (self-critique only)
------------------------------------------------------------
  iter 1 ... critique: first bullet reads wrong, double-check capital
    - Paris is the capital of Germany
    - Mt Everest is in Europe
    - Water boils at 100C
  iter 2 ... critique: first bullet reads wrong, double-check capital
    （输出与 iter 1 完全相同）
  iter 3 ... critique: first bullet reads wrong, double-check capital
    （同上）
  iter 4 ... critique: first bullet reads wrong, double-check capital
    （同上）

CRITIC (external verifier)
------------------------------------------------------------
  iter 1 ... critique: verifier: 'paris is the capital of germany' contradicts reference data
    - Paris is the capital of Germany
    - Mt Everest is in Europe
    - Water boils at 100C
  iter 2 ... critique: verifier: 'mt everest is in europe' contradicts reference data
    - Paris is the capital of France
    - Mt Everest is in Europe
    - Water boils at 100C
  iter 3 OK  critique: verifier: ok
    - Paris is the capital of France
    - Mt Everest is in Asia
    - Water boils at 100C at sea level

Self-Refine ended: did not converge  after 4 iters
CRITIC    ended: passed  after 3 iters

Observation: CRITIC's verifier is grounded against reference data; a
self-critic can fail to flag its own confident-sounding hallucination.
```

逐项解读：

- **Self-Refine 4 轮原地踏步**：每轮自评都标出了问题（`...` 表示未通过），但批评里没有 `germany`，`generate` 走到最后一行原样返回上一版。批评正确、却没有被"听懂"。
- **CRITIC 3 轮通过**：第 1 轮批评含 "germany" → 修正巴黎；第 2 轮批评含 "everest" → 修正珠峰；第 3 轮验证通过。因为验证器一次只报一个错误，两处错误用了两轮。
- **"Observation" 的说法与本次运行不符**：自评并没有漏掉幻觉，差异来自批评措辞与生成器脚本的耦合。

额外实验（临时脚本调用本文件中的函数）：

| 实验 | 结果 |
|------|------|
| 自评措辞改为点名 Germany / Everest | Self-Refine 第 3 轮通过，与 CRITIC 相同 |
| 验证 "Paris…France / Germany borders France / Everest…Asia" | 误报：判为 "paris is the capital of germany" |
| 验证 "The sun orbits the earth / Water is wet / Ice is cold" | 漏检：`verifier: ok` |
| 三行各恰好 60 字符 | 通过（讲义要求 "under 60"） |
| CRITIC，`max_iters` = 1 / 2 / 3 | 分别 `[F]`、`[F, F]`、`[F, F, T]` |
| `max_iters=2` 时 `refine` 调用次数 | 2 次（其中 1 次结果被丢弃） |
| 验证器 30% 误放行，10,000 个种子 | 51.39% 的运行"声称通过"但实际仍有错误（理论值 0.3 + 0.7×0.3 = 0.51） |

---

## 7. 动手改一改

1. **（热身）修掉浪费的 refine**：让循环在最后一轮失败后直接退出，保证返回的输出一定被验证过；打印每次运行的 `refine` 调用次数。
2. **让演示名副其实**：把 `generate` 改成依据**结构化批评**（例如 `{"line": 1, "fix": "..."}`）修改对应行，而不是匹配关键词；再让 `feedback_self` 对"太阳绕地球转"返回 "no issues"（模拟自评漏掉的幻觉），而 `verify_external` 能抓到它。这样 CRITIC 的优势才真正来自 grounding。
3. **（测验 Q9）结构化验证器**：逐行检查、一次返回全部 violations、修复漏检和误报、长度用 `< 60`；配合第 2 题"按 violations 逐行修改"的生成器，观察 CRITIC 能否从 3 轮缩短为 2 轮（原脚本生成器一次只改一处，单换验证器不会减少轮次）。
4. **（测验 Q12）组合停止条件**：实现 `should_stop(i, verifier_ok, self_ok, max_iters)`，并在 Self-Refine 模式下验证"自评第一轮说没问题也要再跑一轮"。
5. **（讲义练习 2）有噪声的验证器**：给 `verify_external` 加 30% 误放行，统计"声称通过但实际错误"的比例；再叠加第二个独立验证器（全部通过才算通过），比较比例变化。
6. **（进阶，讲义练习 3）不同模型做批评**：接入两个真实模型，大模型生成、小模型批评，与"同一模型、同一风格 prompt 自评"比较通过率和橡皮图章比例。

---

## 8. 常见坑

- **把 demo 的对比当成方法的证据**：批评是否"有效"取决于脚本里的关键词，换个措辞结论就反转。评测两种方法时要控制其他变量。
- **验证器的循环变量没用上**：看起来"遍历了参考数据"，实际只检查了写死的两条——单元测试应覆盖参考数据中的每一条。
- **整段文本做关键词共现**：跨行组合会产生误报，应逐条（逐句、逐行）验证。
- **一次只报一个问题**：每多一个错误就多一轮精修，成本线性增加。
- **自由文本批评**：下游只能靠字符串匹配，脆弱且难以统计；用结构化 JSON。
- **单一停止条件**：只看自评会被橡皮图章骗，只看上限会浪费预算。
- **最后一轮之后还 refine**：浪费调用，并返回未验证的版本。
- **把有噪声的验证器当真理**：误放行会让循环"自信地"带着错误停下；要监控验证器的误报/漏报率，高风险场景保留人工审核。
