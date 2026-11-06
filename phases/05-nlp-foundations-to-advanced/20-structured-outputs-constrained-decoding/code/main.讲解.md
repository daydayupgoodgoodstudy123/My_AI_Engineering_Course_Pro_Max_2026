# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 从基础到进阶 · 第 20 节 Structured Outputs & 约束解码 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`、`re`），不需要真实 LLM 或 API key

---

## 1. 这份代码在考察什么

这份代码用一个"假 LLM"（每步随机输出 logits）演示约束解码的核心机制。它刻意让模型**毫无能力**，以便证明：输出合法与否，完全取决于有没有在采样前做掩码。

1. **FSM 表示语法**：把正则 `^\d{3}-\d{3}-\d{4}$` 手工写成 13 个状态的有限状态机。
2. **logit 掩码**：每一步把 FSM 不允许的字符的 logit 设为 `-inf`。
3. **带 `-inf` 的 softmax**：被掩码的位置概率严格为 0。
4. **采样 + 状态转移**：采到字符后推进 FSM，直到接受状态。
5. **对照实验**：同样的随机 logits，无约束 0/20 合法，有约束 20/20 合法。

> 一句话：**约束解码 = 在 softmax 之前加一层"语法掩码"**。真实系统只是把 11 个字符的字母表换成 10 万级词表、把手写 FSM 换成从 JSON Schema 编译出来的 FSM 或 CFG。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PHONE_REGEX` | 常量 | 目标格式 `^\d{3}-\d{3}-\d{4}$`，用于最终校验 | 语法 / 正则 |
| `PhoneFSM` | 类 | 状态 0–12，给出每个状态的合法下一字符、状态转移、是否接受 | 编译后的 FSM |
| `softmax(xs)` | 函数 | 支持 `-inf` 的数值稳定 softmax | logits → 概率 |
| `sample(probs, rng)` | 函数 | 按累积概率做轮盘赌采样 | 采样器 |
| `mask_logits(logits, valid_indices)` | 函数 | 非法位置置为 `-inf` | logit processor |
| `fake_llm_logits(alphabet, rng)` | 函数 | 每个字符一个 `gauss(0, 1.5)` 随机 logit | 假 LLM |
| `generate_constrained(...)` | 函数 | FSM 驱动的约束生成循环 | 约束解码 |
| `generate_unconstrained(...)` | 函数 | 不掩码，生成固定 12 个字符 | 对照组 |
| `main()` | 演示入口 | 各跑 20 个种子，用正则校验并统计合法率 | — |

数据流（约束版）：`state → fake_llm_logits → valid_next(state) → mask_logits → softmax → sample → transition → 新 state`，循环到 `is_accept`。

---

## 3. 逐段精讲

### 3.1 把正则手写成 FSM

```python
class PhoneFSM:
    def __init__(self):
        self.accept_state = 12

    def valid_next(self, state):
        if state in (0, 1, 2, 4, 5, 6, 8, 9, 10, 11):
            return list("0123456789")
        if state in (3, 7):
            return ["-"]
        if state == 12:
            return []
        raise ValueError(f"unknown state {state}")

    def transition(self, state, ch):
        if ch not in self.valid_next(state):
            return None
        return state + 1

    def is_accept(self, state):
        return state == self.accept_state
```

- **状态 = 已经生成了几个字符**。电话号码格式 `ddd-ddd-dddd` 共 12 个字符，所以状态 0–11 各对应一个位置，状态 12 是接受状态。
- 位置 3 和 7 是连字符，其余是数字——`valid_next` 就是把这张"位置 → 允许字符"表写成了 `if`。
- `transition` 对非法字符返回 `None`，而不是抛异常，让调用方自己决定怎么处理。
- 这个 FSM 是**线性链**（每个状态只有一个后继），因为电话号码格式固定。真实正则（含 `|`、`*`、`?`）编译出的 FSM 会有分支和回边；Outlines 做的就是把 JSON Schema/正则自动编译成这样的状态机。
- ⚠️ 简化：状态和字符一一对应。真实 LLM 的 token 是多字符的（如 `"45-"`），需要把每个 token 的字符逐个喂给 FSM 才知道它是否合法（见测验 Q11）。

### 3.2 支持 `-inf` 的 softmax

```python
def softmax(xs):
    finite = [x for x in xs if x != float("-inf")]
    if not finite:
        return [0.0] * len(xs)
    m = max(finite)
    exps = [math.exp(x - m) if x != float("-inf") else 0.0 for x in xs]
    z = sum(exps)
    return [e / z for e in exps]
```

- **减去最大值**：`exp(x - m)` 与 `exp(x)` 归一化后结果相同，但能避免大 logit 溢出——这是数值稳定 softmax 的标准写法。
- **为什么只在有限值里取最大值**：如果所有值都是 `-inf`，`max` 会得到 `-inf`，而 `-inf - (-inf)` 是 `nan`。先过滤掉 `-inf` 就避开了这个坑。
- **显式把 `-inf` 映射为 0.0**：其实 Python 的 `math.exp(float("-inf"))` 本身就返回 `0.0`，这里显式写出来让意图更清楚，也与 `x - m` 可能产生的 `nan` 隔离开。
- **全部被掩码时返回全 0**：这是一种"没有合法续写"的信号。`generate_constrained` 在调用前已用 `if not valid_chars: break` 挡住这种情况。

### 3.3 轮盘赌采样

```python
def sample(probs, rng):
    r = rng.random()
    acc = 0.0
    for i, p in enumerate(probs):
        acc += p
        if r <= acc:
            return i
    return len(probs) - 1
```

- 在 `[0, 1)` 上取随机数 `r`，沿着累积概率前进，第一个让 `acc ≥ r` 的下标被选中。概率为 0 的位置不会让 `acc` 增加，正常情况下不会被选中。
- 最后一行是**浮点误差兜底**：概率之和可能是 `0.9999999999999999`，`r` 落在它和 1 之间时循环会走完。
- ⚠️ 隐患：兜底返回的是最后一个下标，即字母表中的 `-`。在数字位置上 `-` 的概率是 0，一旦触发兜底就会选中非法字符，`transition` 返回 `None`，生成提前结束。概率极低（约 1e-16 量级），但它破坏了"构造上 100% 合法"的承诺。应回退到最后一个概率大于 0 的下标（修复见测验 Q9）。

### 3.4 logit 掩码：logit processor 的全部工作

```python
def mask_logits(logits, valid_indices):
    return [logits[i] if i in valid_indices else float("-inf") for i in range(len(logits))]
```

- 一行列表推导式：合法位置保留原 logit，其余设为 `-inf`。
- **为什么设 `-inf` 而不是直接把概率设为 0**：在 logit 空间操作，softmax 会自动在剩余 token 上**重新归一化**，合法 token 之间的相对大小（模型的"偏好"）被完整保留。
- `valid_indices` 在调用处是一个 `set`，所以 `i in valid_indices` 是 O(1)；如果传的是 list，每次判断都是 O(k)。
- 这正是讲义中 Key Terms 的 logit processor：`(logits, state) -> masked_logits`。

### 3.5 假 LLM

```python
def fake_llm_logits(alphabet, rng):
    return [rng.gauss(0.0, 1.5) for _ in alphabet]
```

- 每个字符一个独立的正态随机数（均值 0、标准差 1.5）。标准差越大，softmax 后的分布越"尖"，每一步更倾向于某个随机字符。
- 这个"模型"对电话号码一无所知。用它做实验的意义：任何合法率的提升都只能归功于掩码。
- ⚠️ 程序结尾打印 "the toy LLM emits uniform-random logits"，严格说 logits 是**正态分布**随机数而非均匀分布；不过由于各字符对称，每个字符被选中的**期望**概率确实是 1/11。

### 3.6 约束生成循环

```python
def generate_constrained(alphabet, fsm, seed):
    rng = random.Random(seed)
    alphabet_idx = {ch: i for i, ch in enumerate(alphabet)}
    state = 0
    out = ""
    while not fsm.is_accept(state):
        logits = fake_llm_logits(alphabet, rng)
        valid_chars = fsm.valid_next(state)
        if not valid_chars:
            break
        valid_ids = {alphabet_idx[ch] for ch in valid_chars}
        masked = mask_logits(logits, valid_ids)
        probs = softmax(masked)
        pick = sample(probs, rng)
        ch = alphabet[pick]
        out += ch
        state = fsm.transition(state, ch)
        if state is None:
            break
    return out
```

- 与讲义 Step 1 的伪代码一一对应：`model.next_token_logits` → `fake_llm_logits`；`fsm.valid_tokens` → `valid_next`；然后 `mask_logits → sample → transition`。
- `random.Random(seed)` 创建**独立的**随机数生成器，而不是用全局 `random.seed()`。这样每个样本可复现，也不会被其他代码的随机调用干扰。
- `alphabet_idx` 是"字符 → 下标"的反查表，相当于真实系统中的 tokenizer 词表。
- 终止条件是"到达接受状态"，而不是固定长度——真实的 JSON 生成就是这样，长度由语法决定。
- 两个 `break` 是防御性代码：没有合法字符（死状态）或转移失败时停止，避免死循环。

### 3.7 无约束对照组与主函数

```python
def generate_unconstrained(alphabet, max_len, seed):
    rng = random.Random(seed)
    out = ""
    for _ in range(max_len):
        logits = fake_llm_logits(alphabet, rng)
        probs = softmax(logits)
        pick = sample(probs, rng)
        out += alphabet[pick]
    return out
```

```python
    for seed in range(20):
        s = generate_unconstrained(alphabet, max_len=12, seed=seed)
        ok = bool(re.fullmatch(PHONE_REGEX, s))
        unc_valid += int(ok)
```

- 对照组用**同样的** `fake_llm_logits` 和 `sample`，唯一区别是不掩码。
- 校验用 `re.fullmatch`：要求整个字符串匹配（正则里的 `^…$` 与 `fullmatch` 意思重复，但无害）。
- `int(ok)` 把布尔值转成 0/1 再累加，是统计计数的常用写法。
- 一个有趣的细节：两种生成方式每步都恰好消耗 11 次 `gauss` + 1 次 `random`，所以**同一个种子下每一步看到的 logits 和随机数 `r` 完全相同**。差别只来自掩码后的重新归一化，因此有些样本前几位一模一样（见第 6 节 seed 12）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 随机 logits 的假模型 | 排除"模型本身会不会"的干扰，突出掩码的作用 | 真实模型的 logits 有语义，约束后质量还取决于模型 |
| 字符级字母表（11 个符号） | 状态与字符一一对应，易懂 | 真实词表 10 万级，token 跨越多个语法位置，需要预计算每个状态的合法 token 集 |
| 手写线性 FSM | 电话号码格式固定，13 个状态足够 | Outlines 从正则/JSON Schema 自动编译；递归结构要用 CFG（XGrammar、llguidance） |
| 在 logit 空间设 `-inf` | softmax 自动重新归一化，保留合法 token 间的相对偏好 | 需要处理全 `-inf` 的边界情况 |
| 每个样本独立 `random.Random(seed)` | 可复现、互不干扰 | — |
| 用正则 `fullmatch` 做最终校验 | 独立于 FSM 的"第二道检查"，验证 FSM 本身写对了 | 生产中还需要语义校验（格式合法 ≠ 内容正确） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 原始字符串 | `r"^\d{3}-\d{3}-\d{4}$"` | `r` 前缀让 `\d` 不被当作转义序列，写正则必备 |
| 类与实例属性 | `self.accept_state = 12` | 在 `__init__` 中初始化实例状态 |
| `in` 判断成员 | `state in (0, 1, 2, ...)`、`i in valid_indices` | 对元组/列表是 O(n)，对 `set`/`dict` 是 O(1) |
| `list("...")` | `list("0123456789-")` | 把字符串拆成单字符列表 |
| `raise` 与 f-string | `raise ValueError(f"unknown state {state}")` | 遇到不应出现的状态立即报错 |
| 返回 `None` 表示失败 | `transition` 返回 `None`；`if state is None: break` | 用 `is None` 判断，而不是 `== None` |
| `float("-inf")` | `float("-inf")` | 负无穷；`math.exp(-inf)` 为 0.0，但 `-inf - (-inf)` 为 `nan` |
| 列表推导式 + 条件表达式 | `[logits[i] if i in valid_indices else float("-inf") for i in range(len(logits))]` | `A if 条件 else B` 写在推导式里 |
| 字典推导式 / 集合推导式 | `{ch: i for i, ch in enumerate(alphabet)}`、`{alphabet_idx[ch] for ch in valid_chars}` | 花括号 + 冒号是字典，没有冒号是集合 |
| `enumerate` | `for i, p in enumerate(probs)` | 同时拿到下标和值 |
| `random.Random(seed)` | `rng = random.Random(seed)` | 独立的随机数生成器实例，`rng.random()`、`rng.gauss(mu, sigma)` |
| `math.exp` | `math.exp(x - m)` | 指数函数 |
| `re.fullmatch` | `re.fullmatch(PHONE_REGEX, s)` | 整个字符串都匹配才返回 Match 对象，否则 `None` |
| `bool()` / `int()` 转换 | `bool(re.fullmatch(...))`、`unc_valid += int(ok)` | Match 对象 → True/False；True → 1 |
| f-string 补齐 | `f"  [{tag}] {s}"`，`tag = "  OK"` | 手动在 `OK` 前加空格，与 `FAIL` 对齐 |
| `while` + `break` | `while not fsm.is_accept(state): ... break` | 条件循环与提前退出 |

---

## 6. 运行结果解读

实际运行 `python3 main.py` 的输出（节选）：

```text
=== phone number generation: 20 samples ===
target pattern: ^\d{3}-\d{3}-\d{4}$

UNCONSTRAINED (random-logit, no masking):
  [FAIL] 15974683892-
  [FAIL] 559431274914
  [FAIL] 03777--20762
  ...
  [FAIL] 404-07102573
  ...
  => valid: 0 / 20

CONSTRAINED (FSM-masked logits):
  [  OK] 059-468-8919
  [  OK] 259-302-4913
  [  OK] 037-789-0742
  ...
  [  OK] 404-061-2573
  ...
  => valid: 20 / 20

note: the toy LLM emits uniform-random logits.
masking invalid tokens at each step is the only difference.
real constrained decoding uses the same mask over a 100k+ vocabulary.
```

逐行解读：

- **无约束 0/20**：每个位置选中 `-` 的期望概率是 1/11，整串合法的期望概率约为 `(10/11)^10 × (1/11)^2 ≈ 0.32%`，20 个样本里期望不到 0.1 个合法，0/20 完全符合预期。失败形态多样：`-` 太多（`03777--20762`）、没有 `-`（`559431274914`）、位置不对（`15974683892-`）。
- **有约束 20/20**：logits 一样随机，但每一步只能在合法字符里选，输出**必然**匹配。这就是讲义说的 "100% valid by construction"。
- **seed 12 的对照**：无约束 `404-07102573`，有约束 `404-061-2573`。前 5 个字符 `404-0` 完全相同：两者每步看到的 logits 和随机数相同，无约束版本在第 4 位恰好随机选中了 `-`，约束版本则被强制选 `-`；第 5 位无约束版选中的是 `0`（字母表下标 0），掩码掉 `-` 后 `0` 的概率只增不减，同一个 `r` 依然落在它的区间里。从第 6 位开始，重新归一化把累积分布的各个边界整体前移，同一个 `r` 落到了另一个数字上，两者才开始不同。
- **最后三行提示**：真实的约束解码用的是同一个掩码思路，只是作用在 10 万+ 的词表上。

---

## 7. 动手改一改

1. 把 `fake_llm_logits` 的标准差从 1.5 改成 0.1 和 5，观察约束生成的数字分布有何变化（合法率应始终 20/20）。
2. 修复 `sample` 的兜底逻辑：回退到最后一个概率大于 0 的下标，或改用 `rng.choices(..., weights=probs)`（参考测验 Q9）。
3. 写一个 `TemplateFSM(["dddd-dd-dd", "unknown"])`，让日期字段可以输出哨兵值 `unknown`，体会讲义中"语法过严"的坑（参考测验 Q10）。
4. 把字符级提升到 token 级：构造一个包含 `"12"`、`"45-"`、`"-5678"` 的小词表，写 `valid_token_ids(fsm, state, vocab)`（参考测验 Q11）。
5. 实现讲义说的"跳过强制 token"：当 `valid_next(state)` 只有一个字符时，不调用 `fake_llm_logits` 直接写入，统计能省下多少次"模型调用"（本例每个样本 12 步中有 2 步可省）。
6. 进阶：为 `\d{3}-\d{3}-\d{4}|\d{10}`（带或不带连字符）手写一个有分支的 FSM，状态不再是简单的"位置计数"。

---

## 8. 常见坑

- **全 `-inf` 的 softmax**：直接 `max(xs)` 再相减会得到 `nan`；必须先判断有没有合法 token。
- **浮点累积误差**：轮盘赌采样的兜底分支可能选中概率为 0 的 token，约束保证因此失效。
- **把掩码加在概率上而不是 logits 上**：直接把概率置 0 后忘了重新归一化，采样分布就错了。
- **用全局 `random.seed`**：多处代码共享全局随机状态，结果难以复现；本代码用独立的 `random.Random(seed)` 规避了这一点。
- **只验证格式**：正则/FSM 只保证"形状"对；真实系统还需要语义校验（例如日期月份不超过 12）。
- **字符级思维套用到 token 级**：真实 token 会跨越语法边界，不能只检查 token 的第一个字符。
