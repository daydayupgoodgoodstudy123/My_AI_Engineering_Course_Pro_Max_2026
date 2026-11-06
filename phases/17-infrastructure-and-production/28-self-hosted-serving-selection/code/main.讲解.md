# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 28 节 自托管服务选型：让引擎匹配硬件与规模 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数，跑 7 个内置场景） ｜ **依赖**：仅标准库，无需 GPU、无需安装任何推理引擎

---

## 1. 这份代码在考察什么

这是一个约 90 行的**决策树遍历器**：输入"硬件、规模、工作负载"三元组，输出一个推荐引擎和一串理由。它把讲义的选型规则编码成 if/elif：

1. **硬件硬约束**：CPU → llama.cpp 系；Apple Silicon → llama.cpp（Metal）/ Ollama；AMD → vLLM（ROCm），TRT-LLM 不可选；Hopper → vLLM / SGLang；Blackwell → TRT-LLM。
2. **规模**：单人开发 → Ollama；企业级 → 追加"production-stack + PD 分离 + 缓存路由"的组合建议。
3. **工作负载**：agentic / 前缀密集 → SGLang。
4. **生态状态**：每个结果都附带"TGI 自 2025-12-11 进入维护模式，新项目避开"的提示。

它的价值在于把"选型不是读排行榜"这件事变成**可审查的规则**——而一旦写成代码，规则里的漏洞也变得一目了然：分支顺序与讲义"硬件 → 规模 → 负载"不一致、长上下文没有规则、未知输入静默返回 `None`。

> 一句话：**把讲义的三层选型树写成一个可执行、可测试的函数，同时让人看到"决策规则代码化"时容易出现的顺序错误与输入校验缺失。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `pick_engine(hardware, scale, workload)` | 函数 | if/elif 决策树，返回包含 `engine` 与 `reasons` 的字典 | 硬件 → 规模 → 负载三层选型 |
| 硬件分支（5 个） | if/elif | CPU、Apple Silicon、AMD、NVIDIA Hopper、NVIDIA Blackwell | 硬件硬约束 |
| `scale == "enterprise"` 附加 | if | 追加 10k+ 用户的组合建议 | 规模层 |
| TGI 提示 | 无条件追加 | 每个结果都提醒避开 TGI | 生态 / 维护状态 |
| `SCENARIOS` | 列表（元组） | 7 个演示场景 | 讲义"Use It" |
| `main()` | 函数 | 遍历场景、打印引擎与理由 | 驱动 |

数据流：`SCENARIOS` 中每个 `(hw, sc, wl)` → `pick_engine` → `{"engine": ..., "reasons": [...]}` → `main` 打印。

---

## 3. 逐段精讲

### 3.1 函数骨架与返回值

```python
def pick_engine(hardware: str, scale: str, workload: str) -> dict:
    reasons = []
    engine = None
    ...
    return {
        "hardware": hardware,
        "scale": scale,
        "workload": workload,
        "engine": engine,
        "reasons": reasons,
    }
```

- 返回"结论 + 理由列表"而不是只返回一个字符串：选型建议必须可解释，这和讲义 skill 文件要求的"Why not the alternatives"一致。
- `engine = None` 是初值。若所有硬件分支都不匹配，函数**不报错**，直接带着 `None` 返回——这是后面"静默失败"的根源。
- 三个参数都是自由字符串，没有任何校验或归一化（只有 `workload` 在比较时做了 `.lower()`）。

### 3.2 CPU 与 Apple Silicon 分支

```python
    if hardware == "CPU":
        engine = "llama.cpp"
        reasons.append("hardware is CPU — only llama.cpp is competitive")
        if scale == "single_user":
            reasons.append("single-user dev → Ollama wraps llama.cpp with one-command UX")
            engine = "Ollama (llama.cpp under the hood)"
    elif hardware == "Apple Silicon":
        engine = "Ollama" if scale == "single_user" else "llama.cpp"
        reasons.append("Apple Silicon → Metal via llama.cpp (Ollama wraps)")
```

- 对应讲义："CPU-first → llama.cpp. Ollama works too but is slower." 以及 "Apple Silicon (M-series) → llama.cpp (Metal). Ollama wraps this."
- 这里**先定硬件、再看规模**，顺序与讲义一致：单人开发在 llama.cpp 之上包一层 Ollama 的一条命令体验。
- ⚠️ 规模为 `enterprise` 时仍返回 llama.cpp，但后面的企业级提示会追加"production-stack（vLLM 的 K8s 部署）"，前后矛盾。更诚实的输出应是"CPU 不适合 10k+ 用户，请重新评估硬件"。

### 3.3 AMD 分支

```python
    elif hardware == "AMD":
        engine = "vLLM"
        reasons.append("AMD → vLLM ROCm support; TRT-LLM is NVIDIA-only")
        if "agentic" in workload.lower() or "prefix" in workload.lower():
            engine = "SGLang"
            reasons.append("agentic / prefix-heavy → SGLang RadixAttention")
```

- 对应讲义："AMD GPU → vLLM is the strongest-supported path (AMD ROCm support). SGLang also works. TRT-LLM is NVIDIA-locked, so it's out."
- 负载识别靠**子串匹配**：`"RAG with heavy prefix reuse"` 因为含 `"prefix"` 而命中；但 `"multi-turn tool use"` 不含这两个词，实测返回 vLLM。
- ⚠️ 单人开发在 AMD 上也返回 vLLM（实测 `("AMD", "single_user", "chat")` → vLLM），没有像 CPU 分支那样考虑规模。

### 3.4 Hopper 分支：顺序问题

```python
    elif hardware == "NVIDIA Hopper":
        if "agentic" in workload.lower() or "prefix" in workload.lower():
            engine = "SGLang"
            reasons.append("Hopper + agentic/prefix → SGLang is the specialist")
        elif scale == "single_user":
            engine = "Ollama"
            reasons.append("single-user on Hopper is a dev scenario → Ollama is enough")
        else:
            engine = "vLLM"
            reasons.append("Hopper production → vLLM is the broad default")
```

- ⚠️ **先判负载、后判规模**，与讲义"scale second, workload third"相反。实测 `("NVIDIA Hopper", "single_user", "agentic multi-turn")` → SGLang，而单人开发按规模层应先落到 Ollama。
- ⚠️ `else` 分支的理由写死为 "Hopper production"，但 `small_team`（10–100 用户）也走这里。讲义对 small team 的建议是"vLLM single-GPU"，理由文字与输入不符。
- ⚠️ 长上下文没有专门规则：`"long-context 128K"` 只是"碰巧"落到 vLLM；讲义的"vLLM + chunked prefill / SGLang + tiered KV"没有出现在理由里。
- 讲义把 TRT-LLM 也列为 Hopper 的第一梯队，代码在 Hopper 上从不推荐它——这是合理的简化（运维复杂度更高），但没有在理由里说明。

### 3.5 Blackwell 分支：负载被忽略

```python
    elif hardware == "NVIDIA Blackwell":
        engine = "TRT-LLM"
        reasons.append("Blackwell + throughput priority → TRT-LLM leads on B200/GB200")
        if scale in ("small_team", "production") and "agentic" not in workload.lower():
            reasons.append("vLLM Blackwell SM120 is a close second (v0.15.1 Feb 2026)")
```

- 对应讲义："NVIDIA Blackwell (B200 / GB200) → TRT-LLM is the throughput leader (Phase 17 · 07). vLLM and SGLang follow close."
- ⚠️ 无论负载、规模如何都返回 TRT-LLM。实测 `("NVIDIA Blackwell", "production", "agentic multi-turn")` → TRT-LLM，而讲义的负载层说 agentic → SGLang；`single_user` 在 B200 上也被推荐 TRT-LLM。
- 理由中的 "throughput priority" 其实是一个**隐含假设**：只有在吞吐是第一目标时 TRT-LLM 才是首选。代码没有这个输入维度。
- `scale in ("small_team", "production")` 用元组做成员判断，见第 5 节。

### 3.6 企业级与 TGI 提示

```python
    if scale == "enterprise":
        reasons.append("10k+ users → stack with production-stack (Phase 17 · 18)"
                      " + disaggregated (Phase 17 · 17) + cache-aware router (Phase 17 · 11)")

    reasons.append("TGI is in maintenance mode since Dec 11, 2025 — default AWAY from TGI for new projects")
```

- 两个相邻字符串字面量会被 Python 自动拼接（见第 5 节）。
- ⚠️ 讲义写的是"vLLM production-stack + disaggregated (Phase 17 · 17) + LMCache (Phase 17 · 18)"。代码把"cache-aware router"归到第 11 节，而第 11 节是"多区域 LLM 服务与 KV Cache 局部性"，"缓存感知路由"出现在第 18 节标题中。
- TGI 提示无条件追加，CPU 单人开发也会看到——更合适的做法是只在 GPU 生产场景或用户提到 TGI 时输出。

### 3.7 场景与主函数

```python
SCENARIOS = [
    ("CPU",              "single_user",   "chat"),
    ("Apple Silicon",    "single_user",   "coding assistant"),
    ("NVIDIA Hopper",    "production",    "general chat"),
    ("NVIDIA Hopper",    "production",    "agentic multi-turn"),
    ("NVIDIA Blackwell", "enterprise",    "MoE frontier serving"),
    ("AMD",              "production",    "RAG with heavy prefix reuse"),
    ("NVIDIA Hopper",    "small_team",    "long-context 128K"),
]
```

- 7 个场景覆盖了 5 种硬件，但没有覆盖"规模与负载冲突"（如 Hopper + 单人 + agentic）、"Blackwell + agentic"、"未知硬件"——恰好是代码出问题的地方。写决策代码时，测试用例应专门覆盖分支交界处。
- `main` 用 `for hw, sc, wl in SCENARIOS` 解包，逐条打印。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 硬编码 if/elif 决策树 | 直观、与讲义逐条对应 | 规则增多后难维护，顺序错误不易察觉；可改成表驱动规则 + 单元测试 |
| 自由字符串输入 | 演示简单 | 大小写/同义词导致静默错误；应用 `Enum` + 解析函数，未知值抛异常 |
| 子串匹配负载 | 一行代码搞定 | 同义词（tool、multi-turn、RAG）漏判；应先把负载归类，再进决策树 |
| 返回 `engine + reasons` | 选型必须可解释 | 理由文字写死，可能与实际输入不符（如 small_team 被写成 production） |
| 每个结果都附 TGI 提示 | 强调讲义的关键事件 | 噪声；应按场景条件输出 |
| Blackwell 一律 TRT-LLM | 体现"吞吐领先" | 忽略负载与运维复杂度；应把"吞吐优先"作为显式输入 |
| 不输出管线与格式转换 | 保持函数简短 | 讲义的 dev → staging → prod 与 GGUF ↔ safetensors 没有落地（测验 Q12 补上） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值；本文件里不是必需，但是常见的风格 |
| 类型注解 | `def pick_engine(hardware: str, scale: str, workload: str) -> dict:` | 只是提示，运行时不检查；传 `None` 进来也不会报错（直到调用 `.lower()`） |
| `if / elif / else` 链 | 硬件的五个分支 | 自上而下，第一个为真的分支执行，其余跳过——**顺序就是优先级** |
| 条件表达式 | `"Ollama" if scale == "single_user" else "llama.cpp"` | 三元运算 |
| `in` 子串判断 | `"agentic" in workload.lower()` | 字符串包含判断；对列表/元组则是成员判断 |
| 元组成员判断 | `scale in ("small_team", "production")` | 比连写多个 `==` 简洁 |
| 字符串方法链 | `workload.lower()` | 转小写后比较，做"大小写不敏感"匹配 |
| 相邻字符串字面量自动拼接 | `("10k+ users → ..." " + disaggregated ...")` | 括号内的多段字面量在编译期合成一个字符串，便于换行 |
| 列表 `append` | `reasons.append(...)` | 逐步积累理由 |
| 字典字面量返回 | `return {"engine": engine, "reasons": reasons, ...}` | 用字典打包多个返回值；更规范的做法是 `dataclass` 或 `TypedDict` |
| 元组列表 + 解包 | `for hw, sc, wl in SCENARIOS:` | 每个元素是三元组，循环时直接拆开 |
| f-string 与下标 | `f"  → engine: {d['engine']}"` | f-string 内部用另一种引号访问字典键 |
| `"=" * 80` | 打印分隔线 | 字符串重复 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时只提供 `pick_engine` |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时可忽略）的完整引擎结论：

```text
[CPU] [single_user] [chat]
  → engine: Ollama (llama.cpp under the hood)
[Apple Silicon] [single_user] [coding assistant]
  → engine: Ollama
[NVIDIA Hopper] [production] [general chat]
  → engine: vLLM
[NVIDIA Hopper] [production] [agentic multi-turn]
  → engine: SGLang
[NVIDIA Blackwell] [enterprise] [MoE frontier serving]
  → engine: TRT-LLM
    · Blackwell + throughput priority → TRT-LLM leads on B200/GB200
    · 10k+ users → stack with production-stack (Phase 17 · 18) + disaggregated (Phase 17 · 17) + cache-aware router (Phase 17 · 11)
    · TGI is in maintenance mode since Dec 11, 2025 — default AWAY from TGI for new projects
[AMD] [production] [RAG with heavy prefix reuse]
  → engine: SGLang
    · AMD → vLLM ROCm support; TRT-LLM is NVIDIA-only
    · agentic / prefix-heavy → SGLang RadixAttention
[NVIDIA Hopper] [small_team] [long-context 128K]
  → engine: vLLM
    · Hopper production → vLLM is the broad default      ← 输入是 small_team，理由却写 production
```

逐项解读：

- **前 6 个场景**与讲义建议一致：CPU/Apple 单人 → Ollama；Hopper 通用生产 → vLLM；agentic → SGLang；Blackwell 企业级 → TRT-LLM；AMD + 前缀复用 → SGLang（讲义说 AMD 上 SGLang"also works"）。
- **AMD 场景的两条理由**先说"vLLM ROCm support"又改成 SGLang，读者需要看到最后一条才知道为何改选；这是"逐步覆盖 engine 变量"写法的副作用。
- **第 7 个场景**结果对、理由错：既把 small team 说成 production，也没提长上下文需要 chunked prefill。
- **每个场景末尾都有 TGI 提示**（上面为节省篇幅只保留了一处）。

我们另外用脚本测试了 11 个边界输入，摘录如下：

| 输入 | 实际输出 | 问题 |
|------|---------|------|
| `("NVIDIA Hopper", "single_user", "agentic multi-turn")` | SGLang | 负载先于规模判断 |
| `("NVIDIA Blackwell", "production", "agentic multi-turn")` | TRT-LLM | 忽略负载 |
| `("CPU", "enterprise", "chat")` | llama.cpp + production-stack 提示 | 前后矛盾 |
| `("AMD", "production", "multi-turn tool use")` | vLLM | 同义词漏判 |
| `("nvidia hopper", "production", "chat")` | `None` | 大小写敏感，静默失败 |
| `("Intel Gaudi", "production", "chat")` | `None` | 未知硬件静默失败 |

---

## 7. 动手改一改

1. **（讲义练习 1）** 把你自己的硬件、规模、负载加入 `SCENARIOS`，看结果是否符合直觉；再专门加入上表中的边界输入。
2. **修正分支顺序**：把 Hopper 分支改成"先看规模（single_user → Ollama），再看负载（agentic/prefix → SGLang），最后默认 vLLM"；理由文字按实际 `scale` 生成（例如 small_team → "vLLM single-GPU"）。
3. **输入校验**：用 `Enum` 表示硬件与规模，未知值抛 `ValueError` 并列出合法取值；负载先归类为 `prefix_heavy / long_context / general`（参考测验 Q10）。
4. **补齐讲义规则**：加入长上下文规则（chunked prefill / tiered KV），让 Blackwell 分支在 agentic 负载下推荐 SGLang 或至少给出备选；企业级提示改为 "LMCache (Phase 17 · 18)"。
5. **（讲义练习 2）** 写 `pick_for_fleet`，对 12 张 H100 + 8 张 MI300X 的混合机房按集群分别选型，并断言 TRT-LLM 只出现在 NVIDIA 集群（参考测验 Q11）。
6. **进阶**：把整棵树改成**表驱动规则**（每条规则是 `(条件函数, 引擎, 理由)`，按优先级排序），再用 `unittest` 为每条讲义规则写一个测试用例，保证以后改规则时不会悄悄改变已有结论。

---

## 8. 常见坑

- **if/elif 的顺序就是优先级**：把负载判断写在规模判断之前，就等于说"负载比规模更重要"，与讲义相反。改规则时最容易在这里出错。
- **返回 `None` 而不报错**：调用方如果直接用 `d["engine"]` 拼命令，会得到 `"None"` 之类的字符串，问题被推迟到部署时才暴露。
- **大小写与同义词**：硬件没有 `.lower()`；负载只认 `agentic` / `prefix` 两个词。
- **理由文字写死**：理由与输入不一致时，比没有理由更误导人（"Hopper production" 用在 small_team 上）。
- **把"吞吐领先"当成唯一目标**：TRT-LLM 在 Blackwell 上吞吐领先，但运维复杂度、对 agentic 前缀复用的支持、团队熟悉度都会影响选择。
- **混合硬件被当作单一硬件**：AMD 与 NVIDIA 混部时必须按集群分别选型，TRT-LLM 只能用于 NVIDIA 集群。
- **以为管线中权重可以原样流转**：Ollama/llama.cpp 用 GGUF，vLLM/SGLang 用 HF safetensors，阶段之间需要格式转换（往往还要重新量化与重新评测）。
