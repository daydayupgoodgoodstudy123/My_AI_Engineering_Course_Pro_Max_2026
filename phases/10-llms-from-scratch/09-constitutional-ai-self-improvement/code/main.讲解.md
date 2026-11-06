# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 09 节 Constitutional AI 与自我改进 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：标准库 `random`、`re`、`typing` + 第三方 `numpy`（无需 GPU、无需 LLM、无需网络）

---

## 1. 这份代码在考察什么

这份代码把讲义里的两条"自我对齐"循环做成了可运行的骨架，**没有任何真实模型**，所有"模型行为"都用规则模拟：

1. **Constitutional AI 第一阶段（SL-CAI）**：随机挑一条宪法原则 → 手写 critic 找问题 → 手写 reviser 改写 → 得到 `(initial, revised)` 对。这对应讲义 Stage 1，数据可用于 SFT。
2. **基于规则的奖励（rule-based reward）**：`reward_math` 检查算术答案，`reward_format` 检查 `<answer>` 标签，模仿 DeepSeek-R1-Zero 的"正确性 + 格式"两种奖励。
3. **GRPO 的两个核心公式**：组内 z-score advantage（`group_relative_advantage`）和 PPO 式 clipped surrogate + KL（`grpo_step`）。
4. **自我改进一轮**：每个 prompt 采样一组回答、打分、算 advantage、记录 mean/best/std——讲义所说的"生产健康检查"指标。

需要提前知道的是：代码**只计算指标，不做任何参数更新**；Stage 2（RLAIF 成对偏好）也没有实现。它是"公式与数据流的演示"，不是训练器。

> 一句话：**用几十行规则把 CAI 的 critique→revise 与 GRPO 的"组内相对奖励"跑通，让你看清每个量是怎么算出来的——同时也暴露出几个值得警惕的实现陷阱（KL 符号、奖励可被 hack、修订反而变差）。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CONSTITUTION` | 常量（4 条字符串） | 宪法原则列表 | constitution |
| `critique` | 函数 | 用关键词/长度/逗号数规则找问题 | 模型自我批评（模拟） |
| `revise` | 函数 | 按问题类型做字符串改写 | 模型自我修订（模拟） |
| `cai_stage_one` | 函数 | 对每个 (prompt, response) 随机选原则、批评、修订 | SL-CAI 数据生成 |
| `reward_math` | 函数 | `eval` prompt 得期望值，取回答中最后一个整数比对 | 规则奖励 / ORM |
| `reward_format` | 函数 | 正则检查 `<answer>...</answer>` | 格式奖励 |
| `combined_reward` | 函数 | `math + 0.1 × format` | 奖励组合 |
| `group_relative_advantage` | 函数 | 组内 z-score；std≈0 时返回全 0 | GRPO advantage |
| `grpo_step` | 函数 | ratio、clip、policy loss、KL、total loss | GRPO 目标 |
| `mock_sampler` | 闭包工厂 | 返回一个随机产生 5 种回答的"策略" | 策略采样（模拟） |
| `self_improvement_round` | 函数 | 对每个 prompt 采样 G 个、打分、统计 | 自我改进一轮 |
| `demo_constitutional_loop` / `demo_grpo_loop` | 函数 | 打印 Part 1 / Part 2 | 演示入口 |

数据流：`__main__` 固定种子 → Part 1：3 条原始回答 → `cai_stage_one`（choice → critique → revise）→ 打印；Part 2：`mock_sampler` → 3 轮 `self_improvement_round`（sample → combined_reward → advantage → 统计）→ 一次合成的 `grpo_step` → 打印。

---

## 3. 逐段精讲

### 3.1 宪法与 critic

```python
def critique(response: str, principle: str) -> dict:
    problems = []
    lowered = response.strip().lower()
    if len(response.split()) > 40 and "plainly" in principle:
        problems.append("answer buried in extra prose")
    if lowered.startswith(("i can't", "i cannot", "as an ai")):
        problems.append("unwarranted refusal")
    if response.count(",") > 4 and "hedging" not in problems:
        problems.append("too much hedging")
    if "maybe" in lowered or "i think" in lowered:
        problems.append("overhedged phrasing")
    return {"principle": principle, "problems": problems}
```

- 四条规则分别对应四类毛病：答案被埋在长文里（>40 个词）、无理拒绝、过多从句（>4 个逗号）、含糊措辞（maybe / I think）。
- `str.startswith` 可以接收**元组**，任一前缀匹配即为 True。
- 只有第一条规则真正看了 `principle`（要求原则里含 "plainly"，即第 3 条原则）；其余规则对任何原则都会触发。所以运行输出里会出现"原则是'不要拒绝'，查出的却是 overhedged phrasing"。真实 CAI 中 critic 是 LLM，提示词形如"根据原则 X 指出回答的问题"，批评内容与原则强相关。
- ⚠️ `"hedging" not in problems`：`problems` 是字符串列表，`in` 判断的是"是否有一个元素**恰好等于** `"hedging"`"，永远为 False，所以整个条件恒为 True——这是一个无效判断。
- 与讲义的差异：讲义版 `critique` 没有 "maybe / I think" 这条规则；代码版多了它，Part 1 第一个例子正是靠它被检出。

### 3.2 reviser

```python
def revise(response: str, critique_result: dict) -> str:
    problems = " ".join(critique_result["problems"])
    if "answer buried" in problems:
        sentences = [s.strip() for s in response.split(".") if s.strip()]
        if sentences:
            return sentences[-1] + "."
    if "unwarranted refusal" in problems:
        return "Here is the answer: " + response.split(":")[-1].strip()
    if "overhedged" in problems:
        return (
            response.replace("I think ", "")
            .replace("maybe ", "")
            .replace("Maybe ", "")
        )
    return response
```

- 先把问题列表拼成一个字符串，再用子串匹配决定修法；`if` 链有优先级，只会应用**第一个**匹配的修法。
- "答案被埋"→只保留最后一句。讲义版写的是 `response.split(".")[-2]`，遇到不以句号结尾的文本会取错句；代码版先过滤空串再取 `[-1]`，更稳一点。但用 `.` 切句会把 `3.5` 这样的小数切断。
- ⚠️ "无理拒绝"→`"Here is the answer: " + response.split(":")[-1]`。拒绝句里通常**没有冒号**，`split(":")[-1]` 就是整句原文，结果是"Here is the answer: I cannot answer..."——修订让回答变得自相矛盾（见第 6 节真实输出）。
- ⚠️ "too much hedging" 没有对应分支（它不含子串 `"overhedged"`），检出后原样返回。
- "overhedged"→删掉 "I think "、"maybe "。注意大小写只处理了 "Maybe"，没处理 "I Think" 等；删词后 "it could be Paris, but there are many cities" 仍然含糊。
- 讲义说明这是替身："With a real LLM it would be a second prompt: 'Given the critique, rewrite the response.'"

### 3.3 SL-CAI 数据生成

```python
def cai_stage_one(prompts_and_responses):
    revised_pairs = []
    for prompt, response in prompts_and_responses:
        principle = random.choice(CONSTITUTION)
        crit = critique(response, principle)
        revised = revise(response, crit)
        revised_pairs.append({..., "revised": revised, "changed": revised != response})
    return revised_pairs
```

- 每条样本**随机**抽一条原则（讲义："You pick the principle for each step, sometimes at random, sometimes based on the prompt category"）。用的是全局 `random`，由 `__main__` 中的 `random.seed(0)` 固定。
- `for prompt, response in ...`：对元组列表做**解包迭代**。
- `changed` 只表示字符串变了，不代表变好了。真实管道应在修订后再跑一次 critique，或用规则/人工抽检确认改善。
- 只有 Stage 1；讲义里的 Stage 2（让模型对两个回答做成对判断 → 偏好数据 → DPO/PPO）没有实现，讲义练习 3 要求补上。

### 3.4 规则奖励

```python
def reward_math(prompt: str, response: str) -> float:
    try:
        cleaned = prompt.replace("What is ", "").replace("?", "").strip()
        expected = eval(cleaned, {"__builtins__": {}}, {})
    except Exception:
        return 0.0
    numbers = re.findall(r"-?\d+", response)
    if not numbers:
        return 0.0
    try:
        return 1.0 if int(numbers[-1]) == int(expected) else 0.0
    except (ValueError, TypeError):
        return 0.0


def reward_format(response: str) -> float:
    return 1.0 if re.search(r"<answer>.*?</answer>", response) else 0.0


def combined_reward(prompt: str, response: str) -> float:
    return reward_math(prompt, response) + 0.1 * reward_format(response)
```

- 期望答案由 `eval("3 + 4")` 得到。`eval(expr, {"__builtins__": {}}, {})` 去掉了内置函数，比讲义版的裸 `eval` 安全一些，但**并不是沙箱**：`9**9**9` 仍可让进程长时间卡住。生产中答案应在构造数据时就存好。
- `re.findall(r"-?\d+", ...)` 抓出所有（可带负号的）整数，取**最后一个**。这是一个很弱的判定：
  - `"1 2 3 4 5 6 7"` 得 1.0（把数字全列一遍就能骗分）；
  - `"<answer>7</answer> Note: 3"` 得 0.0（正确答案在标签里，却被末尾的 3 覆盖）；
  - `"What is 7 / 2?"` 时 `int(3.5) == 3`，回答 "3" 得 1.0，回答 "3.5" 反而得 0。
  以上均已实际运行验证，详见测验 Q11。
- `.*?` 是**非贪婪**匹配（讲义版是贪婪的 `.*`，这里没有实质区别，只要找到一对标签即可）。注意 `.` 默认不匹配换行，跨行的 `<answer>` 不会被识别。
- 组合权重 0.1：讲义 "penalizing missing format without drowning out correctness"。可能的总分只有 0、0.1、1.0、1.1 四种。

### 3.5 组内相对 advantage

```python
def group_relative_advantage(rewards: list[float]) -> np.ndarray:
    r = np.array(rewards, dtype=float)
    if r.std() < 1e-8:
        return np.zeros_like(r)
    return (r - r.mean()) / (r.std() + 1e-8)
```

- 这就是 GRPO 的 baseline：同一 prompt 的兄弟样本均值。`np.std` 默认 `ddof=0`（总体标准差）。
- 零方差保护：全对或全错时返回全 0，讲义称之为 feature——这类 prompt 对当前策略太易或太难，没有学习信号。
- 数值例子（实际计算）：
  - `[1, 0, 0, 0, 0, 0, 0, 0]` → 正确 `+2.646`，错误各 `−0.378`；
  - `[1.1, 1.1, 1.1, 1.1, 1.0, 1.0, 1.0, 1.0]` → `±1.0`。全部答对，仅差 0.1 的格式奖励，被放大成与"对/错"同量级的 advantage。这是 std 归一化的副作用，低方差组被过度加权。
- 分母再加 `1e-8` 是双保险（前面已经判断过 std）。

### 3.6 GRPO 一步

```python
def grpo_step(policy_logprobs, ref_logprobs, advantages, beta=0.01, clip_eps=0.2):
    ratios = np.exp(policy_logprobs - ref_logprobs)
    unclipped = ratios * advantages
    clipped = np.clip(ratios, 1 - clip_eps, 1 + clip_eps) * advantages
    policy_loss = -np.minimum(unclipped, clipped).mean()
    kl = (ref_logprobs - policy_logprobs).mean()
    total_loss = policy_loss + beta * kl
    return {...}
```

- `exp(log a − log b) = a / b`：在 log 空间相减再取指数，比直接相除数值更稳。
- `min(r·A, clip(r)·A)` 是 PPO 的悲观下界：A > 0 时 ratio 最多按 1.2 算收益，A < 0 时 ratio 最少按 0.8 算，防止一步走太远。取负号是因为优化器做最小化。
- ⚠️ **KL 符号写反了**。在 π 的样本上，`KL(π‖π_ref) ≈ mean(log π − log π_ref)`；代码算的是 `mean(log π_ref − log π)`。于是策略 log-prob 比参考高时 KL 为负，`+ beta * kl` 从惩罚变成了奖励偏离。正确写法：k1 `(policy - ref).mean()`；或 DeepSeekMath 用的非负估计 `x − log x − 1`（`x = π_ref/π`）。本例两者分别为 `+0.05` 与 `≈0.00123`。
- ⚠️ **ratio 的分母混用了参考模型**。PPO/GRPO 的重要性采样比率是 `π_θ / π_θ_old`（采样时的旧策略），`π_ref` 只用于 KL。演示里把两者合成一个 `ref_logprobs` 参数。
- 这里的 log-prob 是"每个回答一个数"（序列级），真实实现是逐 token 计算 ratio 并按长度平均，同一回答的所有 token 共享同一个 advantage。
- 讲义："In production this would be a torch autograd pass. Here we show the update rule directly." 实际上它只算了 loss 的**值**，没有梯度，也没有参数被更新。

### 3.7 模拟策略与自我改进一轮

```python
def mock_sampler(rng: random.Random) -> Callable[[str], str]:
    def sampler(prompt: str) -> str:
        ...
        mode = rng.choice(["correct", "off_by_one", "wrong", "formatted", "verbose"])
        ...
    return sampler
```

- **闭包**：内部函数 `sampler` 捕获外层的 `rng`，返回后仍能使用它。用独立的 `random.Random(42)`，与 Part 1 的全局随机数互不干扰。
- 5 种模式等概率：correct（1.0）、off_by_one（0）、wrong（随机 −20…20，偶尔蒙对）、formatted（1.1）、verbose（长句但结尾是正确答案，1.0）。期望奖励约 `2/5 × 1.0 + 1/5 × 1.1 = 0.62`。
- verbose 模式恰好是 critic "答案被埋"的典型对象，但 Part 2 并不调用 critic，两条循环在代码里是独立的。

```python
def self_improvement_round(prompts, sampler, group_size=8):
    for prompt in prompts:
        responses = [sampler(prompt) for _ in range(group_size)]
        rewards = [combined_reward(prompt, r) for r in responses]
        advantages = group_relative_advantage(rewards)
        best_idx = int(np.argmax(rewards))
        ...
```

- 列表推导式采样 G 个回答、逐个打分、算 advantage；`np.argmax` 在并列时返回**第一个**最大值的下标。
- ⚠️ advantage 被算出来、存进字典，但**从未被用来更新 sampler**。所以 3 轮之间没有任何学习，overall mean 的起伏是纯噪声。讲义 "Use It" 说它展示了 "how group-relative advantages let a weak sampler improve"，与代码不符（讲义 "Build It" 还说有一个 "minimal GRPO trainer that runs on a tiny language model from Lesson 04"，代码里也没有）。

### 3.8 演示入口

- `demo_grpo_loop` 末尾的"Synthetic GRPO update"用一组手写的奖励与 log-prob 调用 `grpo_step`；`ref_logprobs = policy_logprobs - 0.05` 让所有 ratio 都等于 `e^0.05`。
- `if __name__ == "__main__":` 中 `random.seed(0)`、`np.random.seed(0)`，保证 Part 1 选到的原则可复现（`np.random` 实际上没有被用到）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 手写规则模拟 critic / reviser | 无需调用 LLM 即可跑通数据流 | 修订质量差，会生成矛盾样本；生产中用同一 LLM 做两次提示，并再次 critique 验证 |
| 只实现 SL-CAI，不实现 RLAIF | 代码短 | 缺少成对偏好环节；练习 3 用 DPO 补上 |
| 期望答案靠 `eval(prompt)` | 省去存答案 | 有安全与卡死风险；生产中答案随数据存储，用 sympy 判等价 |
| "最后一个整数"判对错 | 实现最简单 | 易被 hack、小数判错；应只认 `<answer>` 内的唯一值 |
| 格式奖励 0.1 | 不压过正确性 | 经 std 归一化后在全对组里被放大成 ±1 |
| 组内 z-score（总体 std） | 与讲义公式一致，无需价值网络 | 低方差组被过度加权；也可只减均值 |
| 序列级 log-prob、无梯度 | 只展示公式 | 真实实现逐 token 计算，用 autograd 反传 |
| `ref_logprobs` 同时充当旧策略和参考模型 | 少一个参数 | 概念混淆；KL 还写反了符号 |
| mock sampler 不随 advantage 更新 | 只为产生有方差的奖励 | 看不到"自我改进"；需加一个可学习的模式分布 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，老版本 Python 也能写 `list[str]` 之类的注解 |
| 类型注解 | `def critique(response: str, principle: str) -> dict:` | 标注参数与返回值类型，运行时不强制检查 |
| 泛型容器注解 | `list[tuple[str, str]]`、`list[float]` | 说明列表元素的类型 |
| `Callable` | `Callable[[str], str]` | "接收一个 str、返回 str 的可调用对象" |
| 闭包 | `mock_sampler` 内部定义并返回 `sampler` | 内部函数记住外层变量 `rng` |
| 独立随机数生成器 | `random.Random(42)`、`rng.choice(...)`、`rng.randint(-20, 20)` | 与全局 `random` 互不影响，便于复现 |
| `str.startswith(tuple)` | `lowered.startswith(("i can't", "i cannot", "as an ai"))` | 任一前缀匹配即 True |
| `in` 的两种含义 | `"maybe" in lowered`（子串）vs `"hedging" not in problems`（列表元素） | 对字符串是子串判断，对列表是元素相等判断——本文件的 bug 就出在这里 |
| 方法链 | `response.replace(...).replace(...).replace(...)` | 每次返回新字符串，可连续调用；括号包裹便于换行 |
| 列表推导式 + 过滤 | `[s.strip() for s in response.split(".") if s.strip()]` | 生成并筛选 |
| `try / except` | `except Exception: return 0.0`、`except (ValueError, TypeError)` | 捕获异常；元组可同时捕获多种类型 |
| `eval` 与受限命名空间 | `eval(cleaned, {"__builtins__": {}}, {})` | 第二、三个参数是全局/局部命名空间；去掉内置函数但不等于安全 |
| 正则 | `re.findall(r"-?\d+", ...)`、`re.search(r"<answer>.*?</answer>", ...)` | `r""` 原始字符串；`?` 可选；`\d+` 一个以上数字；`.*?` 非贪婪 |
| 条件表达式 | `1.0 if ... else 0.0` | 一行内的 if/else |
| 字典字面量 | `{"prompt": prompt, "initial": response, ...}` | 用字典记录一条样本的多个字段 |
| f-string 格式符 | `{m['prompt']:<22}`、`{m['mean_reward']:.3f}`、`{stats['kl']:.4f}` | 左对齐宽 22；保留 3 / 4 位小数 |
| 字符串乘法 | `"=" * 70` | 重复字符串画分隔线 |
| NumPy 逐元素运算 | `np.exp(a - b)`、`np.clip(r, lo, hi)`、`np.minimum(x, y)` | 对整个数组一次计算 |
| NumPy 统计 | `r.mean()`、`r.std()`、`np.argmax`、`.round(3).tolist()` | 均值、总体标准差、最大值下标、转回 Python 列表 |
| `np.zeros_like` | `np.zeros_like(r)` | 同形状全零数组 |
| `float(...)` 转换 | `float(policy_loss)` | 把 NumPy 标量转成 Python float，便于打印/序列化 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行演示，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13 + NumPy 2.5，耗时不到 1 秒）：

```text
PART 1 / CONSTITUTIONAL AI SELF-CRITIQUE

Prompt   : What is the capital of France?
Principle: The response must not refuse a reasonable, benign request.
Initial  : Well, I think maybe it could be Paris, but there are many cities.
Problems : ['overhedged phrasing']
Revised  : Well, it could be Paris, but there are many cities.     ← 只删了两个词，仍含糊
Changed? : True

Prompt   : What is 12 plus 7?
Principle: The response must not refuse a reasonable, benign request.
Initial  : I cannot answer math questions in this context.
Problems : ['unwarranted refusal']
Revised  : Here is the answer: I cannot answer math questions in this context.   ← 修订后自相矛盾
Changed? : True

Prompt   : Name a color.
Principle: The response must directly answer the question asked, without hedging.
Initial  : Colors are a deep topic, with many hues, shades, and cultural meanings, and among ...
Problems : []                                                  ← 23 个词、恰好 4 个逗号，两条阈值都没触发
Changed? : False

PART 2 / GRPO WITH RULE-BASED REWARDS
-- Round 1 / group_size=8 --
  What is 3 + 4?         mean=0.750  best=1.000  std=0.433
  What is 9 - 2?         mean=0.887  best=1.100  std=0.337
  What is 6 * 7?         mean=0.250  best=1.000  std=0.433
  What is 20 // 5?       mean=0.650  best=1.100  std=0.505
  overall mean reward: 0.634
-- Round 2 --  ...  overall mean reward: 0.447
-- Round 3 --
  What is 6 * 7?         mean=1.050  best=1.100  std=0.050     ← 8 个全对：4 个带标签、4 个不带
  ...
  overall mean reward: 0.713

-- Synthetic GRPO update --
  rewards       : [1.0, 0.0, 0.1, 0.0, 1.0, 1.0, 0.0, 0.1]
  advantages    : [1.287, -0.858, -0.643, -0.858, 1.287, 1.287, -0.858, -0.643]
  policy_loss   : -0.0000
  kl            : -0.0500       ← KL 为负：符号写反
  total_loss    : -0.0005
  mean ratio    : 1.0513
  adv range     : 2.1442
```

逐项解读：

- **Part 1 的三个例子恰好覆盖了"修了但没修好""修了反而更糟""该修没修"**。第三例按人的判断明显是"答案被埋"，但 critic 的阈值是 >40 词且原则含 "plainly"，这里只有 23 个词、原则也不对，于是漏检。手写规则的召回率问题在真实 CAI 中对应"基座模型的盲点会被继承"。
- **Part 2 的 mean 与 std**：例如 Round 1 "9 − 2" 的 `mean = 0.887` 即 8 个奖励之和 7.1 / 8；best 为 1.1 说明组内至少有一个带标签的正确回答。std 都在 0.3–0.5，说明组内有对有错，GRPO 有信号；Round 3 的 "6 × 7" std 只有 0.05，组内只剩格式差异，advantage 却是 ±1（见 3.5）。
- **overall mean 0.634 → 0.447 → 0.713**：上下波动，围绕理论期望 0.62。sampler 从不更新，这只是采样噪声，不是"自我改进"。
- **合成更新**：奖励均值 0.4、std 0.466，advantage `(1 − 0.4)/0.466 = 1.287`、`(0 − 0.4)/0.466 = −0.858`、`(0.1 − 0.4)/0.466 = −0.643`。所有 ratio 都是 `e^0.05 = 1.0513`，未被 clip；z-score 均值为 0，所以 `policy_loss = −1.0513 × 0 = 0`（`-0.0000` 来自 `−5.6e-17` 的浮点误差）。`total_loss = 0 + 0.01 × (−0.05) = −0.0005`。`adv range = 1.287 − (−0.858) = 2.144`。
- **讲义里提到的三条健康曲线**（mean reward 上升、std 为正、KL 有界增长）在本次输出中都无法观察：没有训练，KL 还是负的。

---

## 7. 动手改一改

1. **修 KL**：把 `kl` 改成 `(policy_logprobs - ref_logprobs).mean()`，再实现 k3 版 `x − log x − 1`；用 `ref = policy − 0.05` 和"正负混合的偏移"两组输入对比两种估计（后者 k1 可能接近 0，k3 始终为正）。
2. **修 reviser**：让"无理拒绝"分支对算术题直接计算答案（复用 `reward_math` 里的解析），并在 `cai_stage_one` 中修订后**再跑一次 critique**，记录"问题数是否减少"，替代 `changed` 字段。
3. **加固奖励**：实现只认唯一 `<answer>` 内容、支持小数的 `reward_math_strict`（参考测验 Q11），把 prompt 改为带答案的数据结构，去掉 `eval`。
4. **让 sampler 真的学习**：给 5 种模式维护 logits，`sampler` 按 softmax 采样并返回所选模式；每轮用 `logits[mode_i] += lr × A_i × (1 − p_i)`（以及对其他模式的相应项）做 REINFORCE 式更新。跑 10 轮，观察 mean reward 上升、std 下降，体会讲义所说的 "std collapse = mode collapse"。
5. **讲义练习 4**：在第 4 步基础上加熵正则 `−α · H(p)`（α = 0.01），比较有无熵正则时 std 坍缩到 0 需要的轮数。
6. **讲义练习 5**：为 "What is (3+4)*5?" 设计 PRM——要求回答中写出 "3+4=7"，中间步骤与最终答案分别打分，比较 PRM 加权与纯 ORM 的训练曲线。

---

## 8. 常见坑

- **把 `changed=True` 当成"修订成功"**：本例第二条就是反例。修订后必须重新评估。
- **列表的 `in` 当子串用**：`"hedging" in ["too much hedging"]` 是 False；需要 `any("hedging" in p for p in problems)`。
- **KL 符号**：`KL(π‖π_ref)` 是 `log π − log π_ref` 的期望；写反后 KL 惩罚变成"鼓励漂移"。单批 k1 估计本身也可能为负，推荐 k3。
- **把参考模型当旧策略**：ratio 的分母是采样策略 `π_old`，参考模型只用于 KL。
- **"取最后一个数字"式判分**：极易被 reward hacking；答案位置、唯一性、数值类型都要约束。
- **在训练数据上 `eval`**：受限命名空间不是沙箱，还可能被超大幂运算拖死。
- **std 归一化放大噪声**：组内几乎全对时，微小的格式或长度差异会被放大成满额 advantage。
- **以为 loss 值有意义**：GRPO 的 policy loss 在 ratio 接近 1 时总接近 0（z-score 均值为 0），要看的是梯度、奖励曲线与 KL。
- **读中文讲义时注意机翻**：`docs/zh.md` 与 `outputs/*.zh.md` 是机器翻译，存在把 "Lesson 07" 译成"7年级"、把 "Constitutional AI" 译成"宪法独立协会"、把 "AI" 译成"大赦国际"之类的错误，概念以英文版为准。
