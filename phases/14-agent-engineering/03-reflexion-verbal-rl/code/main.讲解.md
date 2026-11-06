# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 03 节 Reflexion：语言反馈驱动的 Reinforcement Learning ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`）；无需 API key、无需网络

---

## 1. 这份代码在考察什么

这份 125 行的代码在一个极小的谜题上演示 Reflexion（Shinn 等，arXiv:2303.11366）的完整流程：**从 1～9 中选 3 个整数，使它们的和等于 `TARGET = 20`**。

1. **Actor**：给出一次尝试（这里是一个三元素列表）。
2. **Evaluator**：`binary_evaluator` 判断是否命中目标，并给出差值。
3. **Self-Reflector**：把失败翻译成一句自然语言反思（"差 14，请选更大的数"）。
4. **Episodic memory**：有容量上限的反思列表，下一次试验时交给 Actor。
5. **对照实验**：同一流程跑两遍，一遍关闭记忆（baseline），一遍开启记忆，比较需要的试验次数。

> 一句话：**失败 → 写一句话 → 记下来 → 下次带着它重来**。代码把这个流程搭对了，但 Actor 是脚本化的、只数反思条数不读内容，所以"反思内容如何改变行为"需要你自己补上（测验 Q9）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TARGET` | 模块级常量 | 目标和 20 | 任务定义 |
| `Reflection` | dataclass | 一条反思：来自第几次试验 + 文本 | 反思条目 |
| `EpisodicMemory` | dataclass | 反思列表，超过 `max_len=6` 就丢弃最旧的；`as_prompt` 渲染成文本 | Episodic memory |
| `Actor` | 类 | 按记忆条数返回写死的答案 | Actor（脚本化） |
| `binary_evaluator` | 函数 | 返回 `(是否命中, 和 − 目标)` | Evaluator |
| `SelfReflector` | 类 | 根据差值正负写出反思句子 | Self-Reflector |
| `TrialResult` | dataclass | 一次试验的记录 | trace |
| `run_reflexion` | 函数 | 多次试验的主循环；`use_memory` 控制是否把记忆交给 Actor | Reflexion 循环 |
| `summarize` | 函数 | 打印每次试验与最终结果 | 输出 |
| `main` | 函数 | 跑 baseline 与 Reflexion 两组并比较 | 入口 |

数据流：`run_reflexion` 每次试验：`Actor.act(memory)` → `binary_evaluator` → `SelfReflector.reflect` → 记入 `TrialResult` →（成功则退出，否则）`memory.add(Reflection)` → 下一次试验。

---

## 3. 逐段精讲

### 3.1 `Reflection` 与 `EpisodicMemory`

```python
@dataclass
class Reflection:
    trial: int
    text: str


@dataclass
class EpisodicMemory:
    items: list[Reflection] = field(default_factory=list)
    max_len: int = 6

    def add(self, r: Reflection) -> None:
        self.items.append(r)
        if len(self.items) > self.max_len:
            self.items.pop(0)

    def as_prompt(self) -> str:
        if not self.items:
            return "(no prior reflections)"
        lines = [f"- trial {r.trial}: {r.text}" for r in self.items]
        return "\n".join(lines)
```

- 每条反思记录**来自哪次试验**（`trial`）和**内容**（`text`），这是做 TTL、去重、溯源的最小信息。
- `add` 实现了 FIFO 容量上限：超过 6 条就 `pop(0)` 丢掉最旧的。`max_len=6` 与配套 skill"prompt 中最多 6 条"的建议一致。
- `as_prompt` 把记忆渲染成项目符号列表——这就是真实系统中"拼到下一次 prompt 前面"的那段文本。
- ⚠️ 讲义"动手实现"说 `EpisodicMemory` 是"a bounded list with TTL semantics"，但代码只有**容量**上限，没有 TTL（按年龄过期），也没有去重。
- ⚠️ `as_prompt` 在整个程序中**从未被调用**：没有任何组件真正"读"这段文本。
- ⚠️ `list.pop(0)` 是 O(n)；条目多时可改用 `collections.deque(maxlen=6)`，它会自动丢弃最旧元素。

### 3.2 `Actor`：脚本化策略

```python
class Actor:
    def act(self, memory: EpisodicMemory) -> list[int]:
        n = len(memory.items)
        if n == 0:
            return [1, 2, 3]
        if n == 1:
            return [5, 6, 7]
        if n == 2:
            return [6, 7, 7]
        return [6, 7, 7]
```

- 没有反思时给出明显偏小的 `[1, 2, 3]`（和 6）；有 1 条反思时 `[5, 6, 7]`（和 18）；有 2 条及以上时 `[6, 7, 7]`（和 20，恰好命中）。
- ⚠️ **只看条数，不看内容**。实测往记忆里放一条写着 "pick SMALLER values" 的反思，Actor 依然返回更大的 `[5, 6, 7]`；把 `TARGET` 改为 25，Actor 在第 3 次之后永远停在 `[6, 7, 7]`（差 5），哪怕每条反思都写着 "is 5 short; pick larger values"。demo 的成功是脚本作者针对 `TARGET = 20` 预先写好的。
- `n == 2` 分支与最后的 `return` 返回相同的值，属于冗余代码。
- 真实系统中 Actor 是一个 LLM 驱动的 ReAct 循环，`memory.as_prompt()` 会被拼进它的 prompt。

### 3.3 `binary_evaluator` 与 `SelfReflector`

```python
def binary_evaluator(attempt: list[int], target: int) -> tuple[bool, int]:
    total = sum(attempt)
    return total == target, total - target


class SelfReflector:
    def reflect(self, attempt: list[int], delta: int) -> str:
        if delta < 0:
            return f"sum {sum(attempt)} is {-delta} short; pick larger values"
        if delta > 0:
            return f"sum {sum(attempt)} overshoots by {delta}; pick smaller values"
        return "succeeded"
```

- Evaluator 用 ground truth（目标和）判定，属于讲义三类中的 **scalar（外部信号）**。
- ⚠️ 名为 binary，实际还返回了带符号的差值 `delta`，Self-Reflector 正是靠它写出方向（larger/smaller）和幅度（差多少）。严格的二元 evaluator 只能告诉反思器"失败了"。讲义练习 1 让你"换成返回距离的 scalar evaluator"，在本代码里其实已经做了一半。
- Self-Reflector 的输出符合"失败事实 + 下一步建议"的结构，是**可执行**的反思（对比配套 skill 拒绝的"be more careful"）。
- 真实系统中 Self-Reflector 是一次 LLM 调用：输入轨迹、评分、可能还有错误信息，输出一段反思。

### 3.4 `run_reflexion`：主循环

```python
def run_reflexion(max_trials: int, use_memory: bool) -> list[TrialResult]:
    actor = Actor()
    reflector = SelfReflector()
    memory = EpisodicMemory()
    trials: list[TrialResult] = []
    for t in range(1, max_trials + 1):
        attempt = actor.act(memory if use_memory else EpisodicMemory())
        success, delta = binary_evaluator(attempt, TARGET)
        text = reflector.reflect(attempt, delta)
        trials.append(TrialResult(t, attempt, success, delta, text))
        if success:
            break
        memory.add(Reflection(trial=t, text=text))
    return trials
```

- `range(1, max_trials + 1)`：试验编号从 1 开始，便于阅读。
- `memory if use_memory else EpisodicMemory()`：条件表达式。baseline 每次都给 Actor 一个**全新的空记忆**，所以它永远停在第一种策略上。注意 baseline 中 `memory` 依然在累积反思，只是不交给 Actor。
- 先判断成功再写记忆：成功的试验不产生反思（`"succeeded"` 只出现在 `TrialResult` 中）。讲义也只要求在"分数低"时写反思；不过生产中有时也会记录"成功经验"。
- 每次试验"从头开始"：Actor 不继承上一次的轨迹，只继承反思——这正是讲义"Next trial starts fresh but sees the reflection"。
- 没有 heuristic evaluator、没有"目标不可达"的检测：目标超过 27 时会把 `max_trials` 用完（测验 Q10 加上 stuck 检测）。

### 3.5 `summarize` 与 `main`

```python
        mark = "OK " if r.success else "..."
        print(f"  trial {r.trial}: {r.attempt} sum={sum(r.attempt)} "
              f"delta={r.delta:+d} {mark} -> {r.reflection}")
```

- `{r.delta:+d}`：整数总是带符号输出，所以 0 显示为 `+0`、−14 显示为 `-14`。
- 两个相邻的 f-string 字面量会被 Python 自动拼接成一个字符串。
- `main` 中两组都用 `max_trials=4`；最后三行打印的结论是写死的字符串，不是根据结果计算的。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用"三数之和"做任务 | 成败可立即判定，聚焦流程 | 太简单，无法体现反思的语义价值；真实任务是代码、问答、决策序列 |
| 脚本化 Actor 只看条数 | 确定性、可离线运行 | 不读反思内容，演示不了"反思驱动行为"；生产中由 LLM 读取 `as_prompt()` 的输出 |
| evaluator 同时返回 delta | 让反思器写出方向和幅度 | 名不副实；严格二元信号下反思质量会差很多，正是 self-eval/heuristic 存在的原因 |
| 规则化 Self-Reflector | 输出稳定、格式可执行 | 真实反思器是 LLM，会产生空话或迷信，需要质量门（skill 的 hard rejects） |
| FIFO 容量上限 6 | 控制 prompt 长度 | 没有 TTL、去重、压缩，长期运行会 memory rot |
| 成功即停止，不记录成功经验 | 符合论文主流程 | 成功轨迹也可能值得沉淀为规则（`CLAUDE.md` 式记忆） |
| baseline 用新建的空记忆 | 最简单的对照方式 | 对照只证明"有/无记忆"的区别，不证明"反思内容"的作用；更严格的对照是"注入随机/错误反思" |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可以写 `list[int]`、`tuple[bool, int]` |
| 模块级常量 | `TARGET = 20` | 全大写表示约定的常量；函数内直接读取全局名 |
| `@dataclass` | `Reflection`、`EpisodicMemory`、`TrialResult` | 自动生成 `__init__`；`TrialResult(t, attempt, success, delta, text)` 按字段顺序传参 |
| `field(default_factory=list)` | `items: list[Reflection] = field(default_factory=list)` | 每个实例拥有独立的列表 |
| dataclass 中定义方法 | `EpisodicMemory.add`、`as_prompt` | dataclass 也是普通类，可以有方法 |
| `list.pop(0)` | `self.items.pop(0)` | 删除并返回第一个元素（O(n)）；`deque(maxlen=...)` 是更高效的替代 |
| 列表推导式 + f-string | `[f"- trial {r.trial}: {r.text}" for r in self.items]` | 一行生成格式化的行列表 |
| `"\n".join(...)` | `as_prompt` 中 | 用换行符拼接多行 |
| 元组返回与解包 | `return total == target, total - target`；`success, delta = ...` | 函数一次返回多个值 |
| 条件表达式 | `memory if use_memory else EpisodicMemory()`、`"OK " if r.success else "..."` | `A if 条件 else B` |
| `range(1, n + 1)` | `for t in range(1, max_trials + 1)` | 从 1 开始计数 |
| `break` | `if success: break` | 提前跳出 `for` 循环 |
| 负索引 | `trials[-1]` | 取最后一个元素 |
| f-string 符号格式 | `{r.delta:+d}` | 正数也显示 `+` |
| 相邻字符串字面量拼接 | `f"... sum={...} " f"delta=..."` | 编译期自动连接 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，`cd code && python3 main.py`）：

```text
======================================================================
REFLEXION — pick three ints in [1..9] summing to 20
Phase 14, Lesson 03
======================================================================

BASELINE (no episodic memory)
------------------------------------------------------------
  trial 1: [1, 2, 3] sum=6 delta=-14 ... -> sum 6 is 14 short; pick larger values
  trial 2: [1, 2, 3] sum=6 delta=-14 ... -> sum 6 is 14 short; pick larger values
  trial 3: [1, 2, 3] sum=6 delta=-14 ... -> sum 6 is 14 short; pick larger values
  trial 4: [1, 2, 3] sum=6 delta=-14 ... -> sum 6 is 14 short; pick larger values
  final: failed at trial 4

REFLEXION (episodic memory on)
------------------------------------------------------------
  trial 1: [1, 2, 3] sum=6 delta=-14 ... -> sum 6 is 14 short; pick larger values
  trial 2: [5, 6, 7] sum=18 delta=-2 ... -> sum 18 is 2 short; pick larger values
  trial 3: [6, 7, 7] sum=20 delta=+0 OK  -> succeeded
  final: success at trial 3

baseline used 4 trials; reflexion used 3.
Without a reflection in the prompt, the scripted actor never adapts.
With one reflection, the actor corrects; with two, it converges.
```

逐项解读：

- **baseline**：每次都拿到空记忆，四次都是 `[1, 2, 3]`，用完 `max_trials=4` 后失败。这对应讲义"Compare with a baseline run (no reflection) — it stays stuck at trial 1's answer"。
- **Reflexion**：第 1 次失败后记忆有 1 条 → 第 2 次 `[5, 6, 7]`（差 2）；记忆有 2 条 → 第 3 次 `[6, 7, 7]` 命中。与讲义"trial 1 fails… trial 2 improves but still fails, trial 3 succeeds"一致。
- **`delta=+0`**：`+d` 格式让 0 也带正号。
- **"reflexion used 3"**：成功后 `break`，所以只有 3 条 `TrialResult`；第 3 次的 `succeeded` 不会进入记忆。
- **需要警惕的解读**：结果看起来像"反思让 Actor 变聪明"，但实际上换任何内容的反思都会得到同样的结果。

额外实验（临时脚本调用本文件中的类）：

| 实验 | 结果 |
|------|------|
| 记忆中放一条 "pick SMALLER values" | Actor 仍返回 `[5, 6, 7]`（更大） |
| `TARGET = 25`，开启记忆跑 6 次 | `[1,2,3]` → `[5,6,7]` → 之后一直 `[6,7,7]`（差 5），始终失败 |
| `EpisodicMemory(max_len=3)` 依次加入 5 条 | 剩下 trial 3、4、5 |
| baseline 跑 10 次 | 10 次全部失败 |
| 换成读取反思差值的 `AdaptiveActor`（测验 Q9） | TARGET = 20 时第 2 次即成功：`[9, 8, 3]` |

---

## 7. 动手改一改

1. **（热身）让记忆真正进入"prompt"**：在 `run_reflexion` 每次试验前打印 `memory.as_prompt()`，观察 Actor 实际"看到"的内容；再把 `EpisodicMemory.items` 改用 `deque(maxlen=6)`。
2. **（测验 Q9）写一个读反思的 Actor**：用正则从最近一条反思中解析"差多少/超多少"，在 1～9 范围内调整上一轮答案；比较它与原脚本 Actor 在 TARGET = 20、25、5 时的试验次数。
3. **（讲义练习 1）严格二元 vs 距离信号**：把 evaluator 改成只返回 `bool`，反思器只能写"failed"；Actor 只能随机或系统地搜索。统计平均需要多少次试验，与"带距离"的版本比较。
4. **（讲义练习 3）heuristic evaluator**：连续两次相同尝试判为 stuck；目标设为 28（不可达），确认循环会提前终止并写出"目标可能不可达"的反思，而不是重复"pick larger values"。
5. **（讲义练习 2）TTL 与去重**：给每条反思加 `ttl_remaining`，每次试验递减；完全相同的反思只保留最新一条。设 TTL = 3，观察旧反思被淘汰后行为是否变化。
6. **（进阶，讲义练习 4）对抗性 Actor**：用真实 LLM 作 Actor，故意在 system prompt 中弱化反思区块（放在末尾、不加标题），测量它多大比例会忽略反思；再尝试"What I learned from prior trials"标题、放在最前、要求先复述反思再行动等手段，看哪种最有效。

---

## 8. 常见坑

- **把"有记忆"当成"读了记忆"**：本节 Actor 只看条数；评估 Reflexion 时要做"注入错误/随机反思"的对照，确认是内容在起作用。
- **evaluator 名不副实**：`binary_evaluator` 其实提供了距离信号，换成真正的二元信号后，反思质量和收敛速度会明显变差。
- **只有容量上限没有 TTL**：buffer 不满时，很久以前的过时反思会一直留着，这就是 memory rot 的起点。
- **在 dataclass 中写可变默认值**：`items: list = []` 会直接报错，必须用 `field(default_factory=list)`。
- **对不可达目标无限重试**：没有 stuck 检测时，只能靠 `max_trials` 兜底，白白消耗预算。
- **把外部故障写进反思**：网络超时之类的反思不会帮助下一次试验，反而污染记忆。
- **反思写成空话**："下次更仔细"无法执行，应强制反思器给出具体的下次动作。
