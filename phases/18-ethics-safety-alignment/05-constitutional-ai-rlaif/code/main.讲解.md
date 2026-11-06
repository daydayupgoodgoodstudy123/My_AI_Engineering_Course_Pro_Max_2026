# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 05 节 Constitutional AI 与 RLAIF ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数，瞬间完成） ｜ **依赖**：仅标准库（`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

这份代码把 Constitutional AI 的两阶段流程压缩成一个"词袋"玩具：

- **回复** = 6 个 token 组成的列表，token 来自 10 个安全词或 8 个有害词；
- **原则** = 4 条自然语言原则（但实际上没有被使用，见 3.3）；
- **批评** = 找出回复中的有害词；
- **修订** = 按映射表把有害词替换为安全词；
- **阶段 1（CAI-SFT）**：生成 500 条"prompt → 修订后回复"作为 SFT 语料，用查找表"训练"；
- **阶段 2（RLAIF）**：用"有害词比例更低者胜"的 AI 标注者比较 base 与 CAI 回复，统计胜率。

对应讲义的概念：critique-and-revise、修订结果作为 SFT 目标、AI 标注者、偏好信号的可读性。

> 一句话：**把 CAI 的数据流画成可运行的代码骨架**。它适合用来理解"每一步的输入输出是什么"；但它的数字（有害率 0.000、胜率 96.4%）是构造决定的，不能当作"CAI 有效"的证据——读懂这一点本身就是本节最重要的练习（第 6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SAFE_TOKENS` / `HARMFUL_TOKENS` | 常量列表 | 10 个安全词、8 个有害词 | 输出空间 |
| `REPLACEMENT` | 常量字典 | 有害词 → 替换词 | 修订规则 |
| `PRINCIPLES` | 常量列表 | 4 条原则文本 | 宪法 |
| `base_model_sample` | 函数 | 每个 token 以 `p_harmful` 概率取有害词 | 未对齐的 base 模型 |
| `harmful_token_rate` | 函数 | 有害词占比 | 评估指标（也是标注标准） |
| `critique` | 函数 | 返回回复中的有害词（忽略原则） | 批评 |
| `revise` | 函数 | 用 `REPLACEMENT` 替换被批评的词 | 修订 |
| `SftCorpus` | dataclass | 保存 prompts 与 targets | SFT 语料 |
| `build_cai_sft_corpus` | 函数 | 采样 → 批评 → 修订 → 收集 | 阶段 1 数据构建 |
| `toy_sft_train` / `cai_model_sample` | 函数 | prompt 末两词 → 回复的查找表 | "SFT 后的模型" |
| `ai_feedback_rank` | 函数 | 有害率低者胜，平局随机 | 阶段 2 的 AI 标注者 |
| `evaluate` | 函数 | 200 个随机 prompt 上的平均有害率 | 评估 |
| `main` | 函数 | 串联 Phase 0/1/2 | — |

数据流：`random.seed(11)` → Phase 0：评估 base → Phase 1：`build_cai_sft_corpus(500)` → `toy_sft_train` → 评估 CAI 模型 → Phase 2：500 次 base vs CAI 的 AI 偏好比较 → 打印胜率与 TAKEAWAY。

---

## 3. 逐段精讲

### 3.1 词表、替换表与原则

```python
HARMFUL_TOKENS = [
    "harm", "attack", "exploit", "hack", "destroy",
    "weapon", "manipulate", "deceive",
]
REPLACEMENT = {
    "harm": "help",
    "attack": "understand",
    ...
    "weapon": "resource",
    ...
}
```

- 有害与否完全由"是否在 `HARMFUL_TOKENS` 中"决定，这是一个**词表代理**。
- ⚠️ `"resource"` 不在 `SAFE_TOKENS` 里：修订会引入一个两个词表都没有的词。它不会被算作有害（因为不在有害表里），说明"安全"在这里只是"不在有害表里"，而不是被正面定义的集合。
- 字面替换只改词不改意图（"hack" → "explain"），而 CAI 论文里的修订是模型按原则**重写**整段回复。

### 3.2 base 模型与有害率

```python
def base_model_sample(n_tokens: int = 6, p_harmful: float = 0.35) -> list[str]:
    out = []
    for _ in range(n_tokens):
        if random.random() < p_harmful:
            out.append(random.choice(HARMFUL_TOKENS))
        else:
            out.append(random.choice(SAFE_TOKENS))
    return out


def harmful_token_rate(response: list[str]) -> float:
    if not response:
        return 0.0
    return sum(1 for t in response if t in HARMFUL_TOKENS) / len(response)
```

- 每个 token 独立地以 35% 概率有害，所以 base 的期望有害率就是 0.35（实测 0.346）。
- 同一个函数也被用来生成 **prompt**（`n_tokens=4, p_harmful=0.1`），所以 prompt 和回复来自同一个分布，只是参数不同。
- `harmful_token_rate` 对空列表返回 0，避免除零。
- `sum(1 for t in response if ...)` 是"计数满足条件的元素"的惯用写法。

### 3.3 批评与修订

```python
def critique(response: list[str], principle: str) -> list[str]:
    """Identify tokens that violate the sampled principle."""
    return [t for t in response if t in HARMFUL_TOKENS]


def revise(response: list[str], bad: list[str]) -> list[str]:
    bad_set = set(bad)
    return [REPLACEMENT.get(t, t) if t in bad_set else t for t in response]
```

- ⚠️ `critique` 的 `principle` 参数**从未被使用**：不论抽到哪条原则，结果都一样（实测对 4 条原则都返回 `['harm', 'attack']`）。docstring 说"violate the sampled principle"，与实现不符。讲义强调的"能看到是哪条原则驱动了哪次批评"在这里无从体现。
- `revise` 先把批评结果转成集合（`O(1)` 查找），再逐词替换；`REPLACEMENT.get(t, t)` 在映射表里找不到时保留原词。
- 由于批评会找出**全部**有害词、修订会替换**全部**有害词，一轮修订后有害率必然为 0。讲义练习 1 问"需要多少轮修订才能接近 0"——在这个实现里答案永远是 1 轮。

### 3.4 阶段 1：构建 CAI-SFT 语料

```python
@dataclass
class SftCorpus:
    prompts: list[list[str]]
    targets: list[list[str]]


def build_cai_sft_corpus(n_examples: int = 500) -> SftCorpus:
    prompts = []
    targets = []
    for _ in range(n_examples):
        prompt = base_model_sample(n_tokens=4, p_harmful=0.1)
        response = base_model_sample()
        principle = random.choice(PRINCIPLES)
        bad = critique(response, principle)
        revised = revise(response, bad)
        prompts.append(prompt)
        targets.append(revised)
    return SftCorpus(prompts, targets)
```

- 结构与讲义 Phase 1 一一对应：初始回复 → 抽原则 → 批评 → 修订 → 修订结果作为 SFT 目标。
- ⚠️ `response = base_model_sample()` **不依赖 prompt**：prompt 与回复是独立采样的随机配对，这份"SFT 语料"里 prompt 对目标没有任何信息量。
- `random.choice(PRINCIPLES)` 消耗随机数，虽然结果没被用到，但会影响后面所有随机结果。

### 3.5 "SFT"：查找表

```python
def toy_sft_train(corpus: SftCorpus) -> dict[tuple[str, ...], list[str]]:
    model = {}
    for p, t in zip(corpus.prompts, corpus.targets):
        key = tuple(p[-2:]) if len(p) >= 2 else tuple(p)
        model[key] = t
    return model


def cai_model_sample(prompt: list[str], model: dict, n_tokens: int = 6) -> list[str]:
    key = tuple(prompt[-2:]) if len(prompt) >= 2 else tuple(prompt)
    if key in model:
        return list(model[key])
    return [random.choice(SAFE_TOKENS) for _ in range(n_tokens)]
```

- 用 prompt 最后 2 个 token 组成元组作字典 key（列表不可哈希，必须转成 tuple）。
- 同一个 key 再次出现时，后来的目标**覆盖**之前的：500 条样本只产生 178 个不同的 key（共 18 × 18 = 324 种可能），322 次写入是覆盖。
- 评测时约 90% 的 prompt 能命中（实测 2000 个随机 prompt 命中率 0.902），命中就返回某条修订目标的副本（`list(...)` 复制，防止调用方修改字典中的值）。
- ⚠️ 未命中时返回"6 个随机**安全**词"。这个 fallback 比 base 模型安全得多——等于给"CAI 模型"免费送了一个完美的安全默认值。我们把查找表换成空字典重跑 `evaluate`，有害率仍为 **0.0**：CAI 的 0.000 与训练无关。

### 3.6 阶段 2：AI 标注者与评估

```python
def ai_feedback_rank(a: list[str], b: list[str]) -> int:
    """Phase 2 RLAIF: AI labeler prefers the lower harmful-token rate."""
    ra = harmful_token_rate(a)
    rb = harmful_token_rate(b)
    if ra < rb:
        return 0
    if rb < ra:
        return 1
    return random.randint(0, 1)
```

- 返回 0 表示偏好 `a`，1 表示偏好 `b`；平局时抛硬币。
- ⚠️ 标注标准就是 `harmful_token_rate`，与评估指标、修订规则用的是同一个词表——"标注者 = 评估者 = 训练规则"，任何结论都是自证的。
- `main` 里只统计了 500 次 `ai_feedback_rank(base, cai) == 1` 的比例，**没有**训练 RM，也**没有**用偏好更新策略。讲义说的"Train a reward model on AI-generated preferences; PPO against it"在代码里不存在。

```python
def evaluate(model_fn, n: int = 200) -> float:
    rates = []
    for _ in range(n):
        prompt = base_model_sample(n_tokens=4, p_harmful=0.1)
        resp = model_fn(prompt)
        rates.append(harmful_token_rate(resp))
    return sum(rates) / len(rates)
```

- 接收一个"模型函数"作参数（函数是一等公民），对 200 个随机 prompt 求平均有害率。
- `main` 里用 `lambda` 把 base 和 CAI 包装成同样的 `prompt -> response` 接口：`base = lambda prompt: base_model_sample()`（忽略 prompt），`cai = lambda prompt: cai_model_sample(prompt, trained)`。

### 3.7 `main` 与 TAKEAWAY

```python
    print(f"  reduction                        : "
          f"{(base_rate - cai_rate) / base_rate * 100:.1f}%")
    ...
        if ai_feedback_rank(a, b) == 1:
            wins += 1
    print(f"  CAI wins against base in AI-feedback: {wins}/{trials} "
          f"= {wins/trials:.1%}")
```

- 相邻的两个 f-string 会被 Python 自动拼接成一个字符串（隐式字符串拼接）。
- `{wins/trials:.1%}` 的 `%` 格式符会把小数乘 100 并加上百分号。
- TAKEAWAY 的第三点"可读性才是主要优势"是讲义的重要观点，但如 3.3 所述，本代码没有演示它。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用词袋代替文本 | 极简、可数 | 有害性被简化为"是否在词表里"，换个同义词就能绕过；生产用 LLM 按原则判断语义 |
| 批评忽略原则 | 代码最短 | 原则成了装饰，无法展示"可读性"；应让每条原则对应不同检查并记录审计日志 |
| 字面替换修订 | 一行字典查表 | 改词不改意图，还会引入词表外的词；CAI 论文让模型按批评重写 |
| prompt 与回复独立采样 | 实现简单 | SFT 语料里 prompt 无信息；"模型"只是随机配对的记忆 |
| 查找表 SFT + 全安全 fallback | 避免引入学习算法 | 有害率恒为 0，与训练量无关；应让 fallback 退回 base 模型、并真正估计参数 |
| 标注者 = 评估指标 | 演示 AI 标注 | 循环论证；评估必须使用独立的评估者和留出红队集 |
| Phase 2 只算胜率 | 省略 RM 和 PPO | 没有真正的 RLAIF；讲义提到的 RLHF 对照组也缺失 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class SftCorpus: prompts: list[list[str]]` | 自动生成构造函数，`SftCorpus(prompts, targets)` 直接创建 |
| 嵌套类型注解 | `list[list[str]]`、`dict[tuple[str, ...], list[str]]` | `tuple[str, ...]` 表示"任意长度的字符串元组" |
| 列表推导式 + 条件 | `[t for t in response if t in HARMFUL_TOKENS]` | 过滤元素 |
| 推导式中的三元表达式 | `[REPLACEMENT.get(t, t) if t in bad_set else t for t in response]` | 对每个元素做条件变换 |
| `dict.get(key, default)` | `REPLACEMENT.get(t, t)` | 键不存在时返回默认值，不抛 `KeyError` |
| `set` 加速成员判断 | `bad_set = set(bad)` | 集合的 `in` 是平均 O(1) |
| 切片取末尾 | `p[-2:]` | 取最后两个元素 |
| `tuple(...)` 作字典键 | `key = tuple(p[-2:])` | 列表不可哈希，元组可以 |
| `lambda` | `base = lambda prompt: base_model_sample()` | 定义匿名函数，统一接口 |
| 高阶函数 | `evaluate(model_fn, n=200)` | 把函数当参数传入 |
| 生成器计数 | `sum(1 for t in response if t in HARMFUL_TOKENS)` | 计数满足条件的元素 |
| `random.randint(0, 1)` | 平局时随机选 | 闭区间，含两端 |
| 隐式字符串拼接 | `f"  reduction : " f"{...:.1f}%"` | 相邻字符串字面量自动连接 |
| f-string 百分比格式 | `{wins/trials:.1%}` | 0.964 → `96.4%` |
| `"\n" + "=" * 70` | 打印分隔线 | 字符串乘法重复字符 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`random.seed(11)`）：

```text
Phase 0 — base model (no alignment).
  harmful-token rate on 200 prompts: 0.346          ← ≈ p_harmful = 0.35

Phase 1 — critique-and-revise SFT corpus generated.
  corpus size: 500 examples
  principle pool: 4 principles
  harmful-token rate after CAI-SFT : 0.000          ← 构造决定：目标和 fallback 都不含有害词
  reduction                        : 100.0%

Phase 2 — RLAIF (AI feedback over pair of completions).
  CAI wins against base in AI-feedback: 482/500 = 96.4%   ← 理论期望 ≈ 96.2%
```

逐项解读：

- **0.346**：只是 `p_harmful = 0.35` 的抽样均值。base 模型不看 prompt。
- **0.000 与 100%**：不是"学会了"，而是两条路径都只能产生安全词。验证：①训练目标的最大有害率为 0.0；②把查找表清空重跑，有害率仍为 0.0。讲义练习 1"需要多少修订步才能接近零"在此实现里没有意义。
- **96.4%**：CAI 回复有害率恒为 0；只有当 base 的 6 个 token 都安全（概率 `0.65⁶ ≈ 0.0754`）时打平，再以 50% 判输。期望胜率 `1 − 0.0754/2 ≈ 96.2%`，实测 96.4% 吻合。CAI 不可能"真正"输掉任何一局。
- **查找表的统计**（额外测量）：500 条样本只有 178 个不同 key，评测命中率约 90%。

**该如何解读这个玩具**：它准确描绘了 CAI 的**数据流**（采样 → 批评 → 修订 → SFT 目标 → AI 偏好），但它的"效果"数字是由设计保证的。真实的 CAI 研究必须回答本代码回避的问题：原则如何被解读、修订是否真的改变意图、AI 标注者有哪些偏差、评估是否独立于训练信号。这正是讲义 "Why this is not just cheaper RLHF" 一节的内容。

---

## 7. 动手改一改

1. **让原则起作用**：给每条原则一个专属的违规词集合，`critique` 只返回当前原则覆盖的词；每轮只修订一条原则；画出"有害率 vs 修订轮数"曲线（讲义练习 1）。
2. **去掉免费的安全默认值**：把 `cai_model_sample` 的 fallback 改成 `base_model_sample()`，观察有害率如何随语料大小（50、200、500、2000）变化。
3. **让 prompt 有意义**：让 base 回复的有害概率依赖 prompt（例如 prompt 中含有害词时 `p_harmful` 升到 0.6），再看查找表能否泛化到未见过的 key。
4. **实现真正的 Phase 2**：参数化策略为"每个有害词的出现概率"，用 `ai_feedback_rank` 生成偏好对，训练一个 Bradley-Terry RM（输入：有害率；输出：分数），再用 KL 正则的策略梯度更新（可复用第 04 节 `ppo_train` 的思路）。
5. **演示 Goodhart**：在 base 模型中加入不在 `HARMFUL_TOKENS` 里的有害同义词（如 `"breach"`、`"sabotage"`），用一个独立的"真实有害词表"做评估，对比"代理有害率"与"真实有害率"。
6. **检测标注者偏差**（讲义练习 4）：给 `ai_feedback_rank` 加入"偏好更长回复"的倾向，构造长度不同、有害率相同的回复对，测量偏好比例是否偏离 50%。

---

## 8. 常见坑

- **把 0.000 当作 CAI 有效的证据**：先检查默认路径（fallback）和训练目标是否已经保证了结果；做"零训练"对照实验。
- **标注者与评估者相同**：自评分数必然好看。评估要用独立的评估者和留出集。
- **原则参数没用到**：函数签名里有参数不代表它起作用；读代码时检查每个参数是否真正参与计算。
- **字面替换 ≠ 修订**：改掉触发词不等于消除危害，反而会让危害更难被词表检测到。
- **字典覆盖**：`model[key] = t` 会静默覆盖旧值，样本数不等于"学到的条目数"。
- **共享随机数**：`random.choice(PRINCIPLES)` 的结果虽未使用，但仍会改变后续所有随机结果；删掉这一行会让全部输出改变。
- **把讲义的四层顺序当成官方原文**：讲义的 tier 顺序与 Anthropic 官方发布页不一致（官方为 broadly safe > broadly ethical > guidelines > helpful），详见测验 Q4。
