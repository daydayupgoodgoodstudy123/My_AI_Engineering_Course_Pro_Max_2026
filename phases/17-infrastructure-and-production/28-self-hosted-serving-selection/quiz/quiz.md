# 测验 · 自托管服务选型：让引擎匹配硬件与规模（Self-Hosted Serving Selection — Matching Engine to Hardware and Scale）

> **阶段 17 · 基础设施与生产 · 第 28 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 选型是函数，不是排行榜 | 讲义："Engine selection is a function of hardware, scale, and ecosystem — not a leaderboard read." 决策顺序：硬件第一、规模第二、工作负载第三 |
| 2 | 五个引擎的定位 | llama.cpp（CPU/边缘、模型支持最广）、Ollama（开发机一条命令）、TGI（HF 生态，已进入维护模式）、vLLM（通用生产默认）、SGLang（agentic 多轮 / 前缀密集型） |
| 3 | 硬件硬约束 | CPU-first → llama.cpp；AMD → vLLM 是支持最好的路径（ROCm），SGLang 也可用，TRT-LLM 被排除（NVIDIA-locked）；Apple Silicon → llama.cpp（Metal），Ollama 包装它 |
| 4 | NVIDIA 代际 | Hopper（H100/H200）→ vLLM / SGLang / TRT-LLM 都是第一梯队；Blackwell（B200/GB200）→ 讲义称 TRT-LLM 吞吐领先，vLLM、SGLang 紧随 |
| 5 | 规模分档 | 1 用户 → Ollama；10–100 用户 → vLLM 单卡；100–10k → vLLM production-stack 或 SGLang；10k+ → production-stack + PD 分离 + LMCache |
| 6 | 工作负载分档 | 通用对话 → vLLM；agentic 多轮、前缀复用多的 RAG → SGLang（RadixAttention）；长上下文 128K+ → vLLM + chunked prefill 或 SGLang + 分层 KV |
| 7 | TGI 维护模式 | 讲义："TGI entered maintenance mode December 11, 2025 — only bug fixes"；新项目默认避开 TGI，存量部署应逐步迁移 |
| 8 | Ollama 的边界 | 讲义称比 llama.cpp 慢约 15–30%（Go + CGo + HTTP 序列化），类生产负载下有约 3 倍吞吐差距；并发管理更简单、OpenTelemetry 支持滞后——适合单人开发，不适合共享生产 |
| 9 | dev → staging → prod 管线 | Ollama → llama.cpp → vLLM/SGLang；llama.cpp 家族用 GGUF，GPU 引擎用 HF safetensors，阶段之间可能需要格式转换 |
| 10 | 代码中的简化与偏差 | `pick_engine` 在 Hopper 分支先看负载再看规模、Blackwell 分支忽略负载、长上下文从未被识别、未知硬件静默返回 `None`、企业级提示引用了错误的小节 |

### 核心技能（能动手做到）

- [ ] 给定"硬件 + 规模 + 负载"三元组，按讲义的三层决策树说出引擎和理由，并说出每个备选方案为何落选
- [ ] 解释为什么 AMD 集群上 TRT-LLM 不可选、为什么纯 CPU 只能选 llama.cpp 系
- [ ] 为一个新项目论证"不选 TGI"，为一个存量 TGI 部署写迁移理由
- [ ] 描述从 Ollama 开发到 vLLM 生产时量化格式、配置、可观测性三方面的变化
- [ ] 读懂 `pick_engine` 的 if/elif 分支，找出它与讲义决策顺序不一致的地方，并改成输入校验更严格的表驱动规则
- [ ] 对混合硬件集群（如 H100 + MI300X）按集群分别选型

---

## 二、基础自测（选择题）

**Q1.** 讲义说某个 2025 年的事件改变了新项目的默认选择。这个事件是：

- A. vLLM 停止支持 AMD GPU
- B. SGLang 被合并进 vLLM
- C. Hugging Face TGI 于 2025 年 12 月 11 日进入维护模式，此后只修 bug
- D. Ollama 改用 Rust 重写

**Q2.** 一台没有任何加速卡的服务器要部署开源模型，按讲义应首选：

- A. llama.cpp
- B. vLLM
- C. TRT-LLM
- D. TGI

**Q3.** 你的集群全部是 AMD GPU。下列哪个引擎被讲义明确排除？

- A. vLLM
- B. SGLang
- C. llama.cpp
- D. TRT-LLM

**Q4.** 一个 agentic 产品：多轮对话、大量工具调用、每轮都带着很长且重复的系统提示与历史。讲义推荐：

- A. Ollama，因为一条命令就能装好
- B. SGLang，因为 RadixAttention 能复用共享前缀的 KV
- C. TGI，因为它的可观测性最好
- D. llama.cpp，因为它支持的模型最多

**Q5.** 关于讲义的 dev → staging → prod 管线，说法正确的是：

- A. 三个阶段必须使用同一个引擎，否则结果不可比
- B. 开发用 vLLM、预发用 Ollama、生产用 llama.cpp
- C. 所有引擎读同一种权重格式，阶段之间不需要任何转换
- D. 开发用 Ollama、预发用 llama.cpp、生产用 vLLM 或 SGLang；llama.cpp 家族用 GGUF、GPU 引擎用 HF safetensors，阶段之间可能需要格式转换

**Q6.** 运行 `pick_engine("NVIDIA Hopper", "single_user", "agentic multi-turn")`，返回的 `engine` 是：

- A. `"SGLang"`
- B. `"Ollama"`
- C. `"vLLM"`
- D. `None`

**Q7.** 运行 `pick_engine("nvidia hopper", "production", "chat")`（注意小写），结果是：

- A. 返回 `"vLLM"`，因为字符串比较不区分大小写
- B. 不抛异常，但 `engine` 为 `None`，`reasons` 只有一条 TGI 提示
- C. 抛出 `KeyError`
- D. 返回 `"TRT-LLM"`

**Q8.** 讲义不建议用 Ollama 做多人共享的生产服务，给出的理由是：

- A. Ollama 只能跑在 macOS 上
- B. Ollama 不支持量化模型
- C. Go HTTP 序列化带来额外开销、并发管理比 vLLM 简单、OpenTelemetry 支持滞后
- D. Ollama 已进入维护模式

---

## 三、动手 / 代码题

**Q9.** 讲义的决策顺序是"hardware first, scale second, workload third"。阅读 `pick_engine` 的 Hopper 与 Blackwell 分支：

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
    elif hardware == "NVIDIA Blackwell":
        engine = "TRT-LLM"
        reasons.append("Blackwell + throughput priority → TRT-LLM leads on B200/GB200")
        if scale in ("small_team", "production") and "agentic" not in workload.lower():
            reasons.append("vLLM Blackwell SM120 is a close second (v0.15.1 Feb 2026)")
```

找出至少四处与讲义不一致或不合理的地方（提示：考虑分支顺序、`small_team` 场景的理由文字、长上下文、Blackwell 上的 agentic 负载、`enterprise` 的附加提示）。

**Q10.** `pick_engine` 用字符串精确匹配硬件、用子串匹配负载。

1. 列出三种会让它"静默给出错误/空结果"的输入。
2. 把输入改成枚举（`Enum`），对未知硬件抛出 `ValueError`，并把负载识别改成"关键词集合"匹配（例如 `{"agentic", "tool", "multi-turn", "prefix", "rag"}` 视为前缀密集型）。写出关键代码。

**Q11.**（讲义练习 2）你的机房有 12 张 H100 和 8 张 AMD MI300X，生产规模，通用对话。

1. 如果把它当成一个"硬件"传给 `pick_engine`，会出现什么问题？
2. 讲义附带的 skill 文件对"混合硬件"有什么规则？
3. 写一个 `pick_for_fleet(clusters, scale, workload)`，对每个同构集群分别调用 `pick_engine`，并在出现 TRT-LLM 时检查该集群确实是 NVIDIA。给出这个例子的预期输出。

**Q12.** 讲义列出了"长上下文（128K+）→ vLLM + chunked prefill；SGLang + tiered KV"，以及 dev/staging/prod 管线，但代码都没有体现。请：

1. 在 GPU 分支里加入长上下文规则（识别 `"long-context"`、`"128k"` 等关键词），让理由里出现 chunked prefill / tiered KV。
2. 给返回值增加 `pipeline` 字段：生产或以上规模时返回 `{"dev": "Ollama", "staging": "llama.cpp", "prod": engine, "format_conversion": "GGUF ↔ HF safetensors"}`；其余规模返回 `None`。
3. 对 `("NVIDIA Hopper", "small_team", "long-context 128K")`，原代码与改后代码的输出分别是什么？

---

## 四、面试高频题

**Q13.**（基础必考）团队要上一个自托管 LLM 服务，三位工程师分别主张 Ollama、vLLM、TGI。你怎么做决定？请给出决策框架和每个选项适用的场景。

**Q14.**（原理深挖）为什么讲义把 SGLang 定位为 agentic / 前缀密集型负载的专家？前缀复用在这类负载中能省下什么？什么情况下这个优势会消失？

**Q15.**（工程实践）从"开发机上用 Ollama"迁移到"生产用 vLLM"，量化、配置、可观测性三方面分别要改什么？迁移时怎么保证模型行为一致？

**Q16.**（场景设计）一个团队想在 2026 年的新项目里继续用 TGI，理由是"我们最熟悉它"。请论证迁移（或不采用）的理由，并给出一个不冒进的过渡方案。

**Q17.**（追问型）为什么不直接看公开 benchmark 排行榜选"最快的引擎"？你会怎样在自己的场景下验证选型？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："TGI entered maintenance mode December 11, 2025 — only bug fixes going forward." 这使它成为"risky long-term bet"，新项目应默认选 vLLM 或 SGLang。

- A 错：讲义恰恰说 AMD 上 vLLM 是"strongest-supported path"。
- B、D：讲义没有这些说法，是编造的干扰项。

### Q2 — 答案：A

讲义："CPU-first → llama.cpp. Ollama works too but is slower. No other engine is competitive on CPU."

- B、C、D 都是面向 GPU 的服务引擎；TRT-LLM 只能跑在 NVIDIA GPU 上。

### Q3 — 答案：D

讲义："TRT-LLM is NVIDIA-locked, so it's out." AMD 上 vLLM 有 ROCm 支持，SGLang 也可用；llama.cpp 也能跑，但不是生产首选。

- A、B 是讲义推荐的 AMD 选项。
- C 并未被排除（讲义只说 CPU 和 Apple Silicon 时首选它）。

### Q4 — 答案：B

讲义："Agentic multi-turn (tools, planning, memory) → SGLang's RadixAttention (Phase 17 · 06) dominates." RadixAttention 用基数树组织 KV cache，多轮对话、共享系统提示、RAG 中重复的文档前缀都能命中已缓存的 KV，省掉重复 prefill。

- A：Ollama 是单人开发工具。
- C：TGI 已进入维护模式，且讲义没有把它定位为 agentic 专家。
- D：模型覆盖广与前缀复用无关。

### Q5 — 答案：D

讲义："Dev (Ollama) → staging (llama.cpp) → prod (vLLM). The engines take different weight formats — GGUF for the llama.cpp family, HF safetensors for the GPU engines — so a format conversion may sit between stages."

- A 错：管线的意义就是各阶段用最合适的引擎。
- B 顺序完全颠倒。
- C 错：讲义明确指出格式不同。注意本节的 `quiz.json` 有一道题写"on the same GGUF or HF weights"，容易误导人以为权重可以原样流转，实际上 GGUF 与 safetensors 之间需要转换（以及可能的重新量化）。

### Q6 — 答案：A

Hopper 分支**先检查 workload**：`"agentic" in "agentic multi-turn"` 为真，直接返回 SGLang，根本没走到 `scale == "single_user"` 的判断。已实际运行验证。

这与讲义"scale second, workload third"的顺序不一致：按讲义，单人开发应先落到 Ollama。

- B 是按讲义顺序"应该"得到的答案之一，但不是代码的输出。
- C、D 不符合实际运行结果。

### Q7 — 答案：B

硬件用 `==` 精确比较，`"nvidia hopper"` 不匹配任何分支，`engine` 保持初值 `None`；`scale` 不是 `enterprise`，所以 `reasons` 里只有最后那条 TGI 提示。已实际运行验证，未知硬件（如 `"Intel Gaudi"`）同样返回 `None`。

- A 错：只有 workload 做了 `.lower()`，硬件没有。
- C 错：代码不查字典，不会抛 `KeyError`。
- D 错：没有进入 Blackwell 分支。

### Q8 — 答案：C

讲义 "Ollama caveat"："Go HTTP serialization adds overhead, concurrency management is simpler than vLLM, OpenTelemetry support lags." 并建议"switch to vLLM for shared"。

- A 错：Ollama 跨平台。
- B 错：Ollama 正是用 GGUF 量化模型。
- D 错：进入维护模式的是 TGI。

### Q9 — 参考答案

1. **Hopper 分支顺序颠倒**：先判断负载、后判断规模。`(Hopper, single_user, agentic)` 得到 SGLang，而讲义的顺序会先把单人开发场景导向 Ollama（见 Q6）。
2. **理由文字与输入不符**：`(Hopper, small_team, long-context 128K)` 的理由是 "Hopper production → vLLM is the broad default"，但输入是 `small_team` 而不是 `production`。讲义对 10–100 用户的建议是"vLLM single-GPU"，代码没有区分。
3. **长上下文从未被识别**：负载字符串里只匹配 `"agentic"` 和 `"prefix"`。讲义的"Long context (128K+) → vLLM + chunked prefill; SGLang + tiered KV"完全没有落地，结果只是碰巧选中了 vLLM。
4. **Blackwell 忽略负载与规模**：无论 agentic、单人还是企业级，都返回 TRT-LLM。讲义的工作负载层说 agentic → SGLang；而且对单人开发在 B200 上推荐 TRT-LLM 也不合理（实测 `(Blackwell, single_user, agentic coding agent)` → TRT-LLM）。
5. **企业级提示引用的小节不对**：代码写 "cache-aware router (Phase 17 · 11)"，讲义写的是 "LMCache (Phase 17 · 18)"；第 11 节是"多区域 LLM 服务与 KV Cache 局部性"，而"缓存感知路由"在第 18 节标题中。另外 `(CPU, enterprise, chat)` 返回 llama.cpp，却同时追加"stack with production-stack"（那是 vLLM 的 K8s 部署），前后矛盾——更合理的做法是提示"CPU 不适合 10k+ 用户"。
6. **每个场景都追加 TGI 提示**：即使是 CPU 单人开发也会打印，属于噪声；更合理的是只在用户提到 TGI 或在 GPU 生产场景提示。

### Q10 — 参考答案

1. 静默错误的输入：
   - 大小写或拼写不同：`"nvidia hopper"`、`"H100"`、`"Hopper"` → `engine=None`；
   - 讲义没覆盖的硬件：`"Intel Gaudi"`、`"NVIDIA Ampere"` → `None`；
   - 负载用了同义词：`"multi-turn tool use"`（没有 agentic 字样）在 AMD 上返回 vLLM 而不是 SGLang；`"RAG"`（没有 prefix 字样）在 Hopper 上返回 vLLM；
   - 规模拼错：`"Production"` 不会匹配 `"production"`，但由于多数分支只特判 `single_user`，结果往往"看起来对"，更难发现。
2. 参考实现：

```python
from enum import Enum


class Hardware(Enum):
    CPU = "cpu"
    APPLE = "apple silicon"
    AMD = "amd"
    HOPPER = "nvidia hopper"
    BLACKWELL = "nvidia blackwell"


class Scale(Enum):
    SINGLE_USER = "single_user"
    SMALL_TEAM = "small_team"
    PRODUCTION = "production"
    ENTERPRISE = "enterprise"


PREFIX_HEAVY = {"agentic", "tool", "multi-turn", "prefix", "rag"}
LONG_CONTEXT = {"long-context", "128k", "long context"}


def parse_hardware(s: str) -> Hardware:
    try:
        return Hardware(s.strip().lower())
    except ValueError:
        valid = ", ".join(h.value for h in Hardware)
        raise ValueError(f"unknown hardware {s!r}; expected one of: {valid}") from None


def classify_workload(s: str) -> str:
    w = s.lower()
    if any(k in w for k in PREFIX_HEAVY):
        return "prefix_heavy"
    if any(k in w for k in LONG_CONTEXT):
        return "long_context"
    return "general"
```

要点：枚举把"合法取值"写死在一处；解析失败时抛出带候选列表的错误，而不是返回 `None`；负载先归类再进决策树，避免每个分支各写一遍 `in workload.lower()`。

### Q11 — 参考答案

1. `pick_engine` 一次只接受一个硬件字符串；传 `"H100+MI300X"` 会落到无分支，返回 `None`。若硬塞成 `"NVIDIA Hopper"`，可能对通用对话给出 vLLM（碰巧两边都能用），但对 Blackwell 类分支就可能给出 TRT-LLM，而 MI300X 根本跑不了。
2. skill 文件："If hardware is mixed (some AMD, some NVIDIA), require per-cluster engine decisions; do not force a single engine." 以及"Suggesting TRT-LLM without confirming NVIDIA-only. Refuse"。
3. 参考实现：

```python
def pick_for_fleet(clusters: dict[str, tuple[str, int]], scale: str, workload: str) -> dict:
    plan = {}
    for name, (hardware, n_gpus) in clusters.items():
        d = pick_engine(hardware, scale, workload)
        if d["engine"] == "TRT-LLM" and not hardware.startswith("NVIDIA"):
            raise ValueError(f"{name}: TRT-LLM requires NVIDIA hardware")
        plan[name] = {"gpus": n_gpus, "engine": d["engine"], "reasons": d["reasons"]}
    return plan


pick_for_fleet({"h100-pool": ("NVIDIA Hopper", 12), "mi300x-pool": ("AMD", 8)},
               "production", "general chat")
# h100-pool   → vLLM（Hopper production → vLLM is the broad default）
# mi300x-pool → vLLM（AMD → vLLM ROCm support; TRT-LLM is NVIDIA-only）
```

两边都选 vLLM 的好处是：同一套 OpenAI 兼容 API、同一套配置与监控，路由层（第 19 节 AI 网关）可以把两个池当作同一种后端，只按容量分流。TRT-LLM 被排除的原因是它只支持 NVIDIA；如果在 H100 池上单独用 TRT-LLM，就要维护两套引擎、两种模型编译产物。

### Q12 — 参考答案

1. 在 GPU 分支（AMD / Hopper / Blackwell）里，在 prefix 判断之后加：

```python
    LONG_CONTEXT = ("long-context", "long context", "128k")
    if engine in ("vLLM", "SGLang") and any(k in workload.lower() for k in LONG_CONTEXT):
        if engine == "vLLM":
            reasons.append("long context → enable chunked prefill (Phase 17 · 04)")
        else:
            reasons.append("long context → SGLang with tiered KV")
```

2. 管线字段：

```python
    pipeline = None
    if scale in ("production", "enterprise") and engine in ("vLLM", "SGLang", "TRT-LLM"):
        pipeline = {
            "dev": "Ollama",
            "staging": "llama.cpp",
            "prod": engine,
            "format_conversion": "GGUF (dev/staging) ↔ HF safetensors (prod)",
        }
    return {..., "engine": engine, "reasons": reasons, "pipeline": pipeline}
```

3. 原代码输出（实际运行）：

```text
[NVIDIA Hopper] [small_team] [long-context 128K]
  → engine: vLLM
    · Hopper production → vLLM is the broad default
    · TGI is in maintenance mode since Dec 11, 2025 — default AWAY from TGI for new projects
```

改后：引擎仍是 vLLM，理由中多出"long context → enable chunked prefill"；规模是 `small_team`，所以 `pipeline` 为 `None`。如果同时修正 Q9 第 2 点，第一条理由应改成"small team → vLLM single-GPU"。

### Q13 — 参考回答要点

- **先确认要自托管**：讲义："Self-hosted vs managed is a separate decision"，自托管的理由是数据驻留、定制微调、规模化后的 TCO、托管平台没有所需领域模型。
- **硬件第一**（硬约束）：纯 CPU → llama.cpp；Apple Silicon → llama.cpp（Metal）/ Ollama；AMD → vLLM（或 SGLang），排除 TRT-LLM；Hopper → vLLM / SGLang / TRT-LLM；Blackwell → TRT-LLM 吞吐领先，vLLM、SGLang 紧随。
- **规模第二**：单人 → Ollama；10–100 → vLLM 单卡；100–10k → vLLM production-stack 或 SGLang；10k+ → 加 PD 分离、LMCache。
- **负载第三**：通用 → vLLM；agentic / 前缀复用 → SGLang；长上下文 → chunked prefill / 分层 KV。
- **三位工程师的主张**：Ollama 对本地开发正确；vLLM 对共享生产正确；TGI 在 2026 年对新项目不建议（维护模式）。最终可以是"开发 Ollama、生产 vLLM"的组合。
- 加分点：提到格式转换（GGUF ↔ safetensors）、统一 OpenAI 兼容 API 便于切换、季度复评（skill 文件："re-evaluate engine choice when workload shape changes materially"）。

### Q14 — 参考回答要点

- **原因**：agentic 多轮对话里，每一轮请求都包含相同的系统提示、工具定义和越来越长的历史；RAG 里很多请求共享同一批文档前缀。RadixAttention 用基数树（radix tree）管理 KV cache，新请求能匹配到最长已缓存前缀，只对新增部分做 prefill。
- **省下什么**：重复前缀的 prefill 计算（降低 TTFT、释放算力给 decode）以及重复 KV 的显存占用；命中率越高，吞吐提升越大。
- **优势消失的情形**：
  - 请求之间几乎没有共享前缀（一次性短问答、每次上下文都不同）；
  - 前缀虽相同但被调度到不同实例，缓存不在本机——需要缓存感知路由（第 18 节）或多区域 KV 局部性（第 11 节）；
  - 显存紧张导致缓存频繁被逐出；
  - 提示词里早早插入了时间戳、随机 ID 等变化内容，破坏前缀一致性。
- 加分点：vLLM 也有自动前缀缓存（automatic prefix caching），两者差距取决于具体负载，应在自己的流量上测；把"可变内容放到提示末尾"是提高命中率的通用做法。

### Q15 — 参考回答要点

- **量化**：Ollama 用 GGUF（K-quants，如 Q4_K_M）；vLLM 用 HF safetensors，常见量化为 AWQ、GPTQ、FP8 等（见第 09 节）。不能直接复用 GGUF 文件；要从原始权重重新量化或选现成的 GPU 量化版本，并重新评估质量。
- **配置**：Ollama 几乎零配置；vLLM 要设最大上下文长度、显存占用比例、张量并行度、最大并发序列数、是否开启前缀缓存与 chunked prefill 等；还要设 K8s 资源、健康检查、自动扩缩容（第 03、18 节）。
- **可观测性**：讲义说 Ollama 的 OpenTelemetry 支持滞后；生产需要导出 TTFT、TPOT、队列长度、KV cache 使用率、goodput（第 08 节），接入 trace 与成本归因（第 13、27 节）。
- **行为一致性**：
  - 确认 chat template 与 tokenizer 一致（不同引擎的模板处理可能不同）；
  - 采样参数默认值对齐（temperature、top-p、停止词、最大输出长度）；
  - 用同一套评测集比较 Ollama 版与 vLLM 版的输出质量；量化差异会带来细微差别；
  - 先 shadow 流量再金丝雀发布（第 20 节）。
- 加分点：两者都提供 OpenAI 兼容接口，应用侧只改 base URL，迁移风险主要在模型格式和运维层面。

### Q16 — 参考回答要点

- **迁移理由**：
  - 维护模式意味着只有 bug 修复，新模型架构、新硬件（如 Blackwell）、新优化（投机解码、新量化格式）都不会进来，长期会落后；
  - 讲义称 TGI 原始吞吐比 vLLM 低约 10%；
  - 社区与人才会向活跃项目集中，排障资料变少；
  - 新项目从第一天就选维护中的引擎，等于预埋一次迁移。
- **承认 TGI 的优点**：讲义："historically top observability and HF-ecosystem integration"，在受监管行业有积累；团队熟悉度是真实成本。
- **不冒进的方案**：
  - 新项目直接用 vLLM（或前缀密集型用 SGLang）；
  - 存量 TGI 继续运行，skill 文件建议"not urgent but should start within 6 months"开始迁移；
  - 先在预发环境并行部署 vLLM，对比延迟、吞吐、输出质量；用网关做 shadow → 金丝雀 → 全量；
  - 把 TGI 的监控指标映射到 vLLM 的 Prometheus 指标，保持看板连续。
- 常见误区：以为"维护模式 = 立刻不能用"。它仍然可用，问题是长期风险与机会成本。

### Q17 — 参考回答要点

- **排行榜的局限**：讲义开宗明义"not a leaderboard read"。benchmark 的硬件、模型、量化、并发、输入/输出长度分布都与你不同；前缀复用率、长上下文比例等负载形态对结果影响巨大；很多榜单只报吞吐或单请求延迟，不报 P99 与 goodput。
- **硬约束先于性能**：再快的引擎，硬件不支持就不可选（AMD 不能跑 TRT-LLM、CPU 只能用 llama.cpp 系）。
- **生态与维护状态**：TGI 的例子说明"今天快"不代表"明年还在演进"。
- **自己验证**：
  - 用真实流量或回放日志构造负载（输入/输出长度分布、前缀共享率、并发曲线）；
  - 用 LLM 专用的压测方式（第 22 节：k6/Locust 会误导），测 TTFT、TPOT、P99、goodput（第 08 节）；
  - 同时测质量（量化与模板差异）和成本（每 GPU 小时可服务的请求数）；
  - 定期复评。
- 加分点：给出一个决策表，列出每个候选在"硬件支持 / 吞吐 / P99 / 运维复杂度 / 生态活跃度"上的打分。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：理解 vLLM 为什么是通用生产默认，以及长上下文的 chunked prefill。
- [阶段 17 · 06 前缀缓存服务：RadixAttention 与 KV 复用](../../06-sglang-radixattention/docs/zh.md)：SGLang 在 agentic / 前缀密集负载上的优势来源。
- [阶段 17 · 07 针对硬件的 Inference 编译：Blackwell 上的 FP8 与 NVFP4](../../07-tensorrt-llm-blackwell/docs/zh.md)：TRT-LLM 为何在 Blackwell 上领先、为何只限 NVIDIA。
- [阶段 17 · 09 生产环境中的 Quantization](../../09-production-quantization/docs/zh.md)：GGUF K-quants 与 AWQ/GPTQ/FP8 的差异，决定管线中的格式转换。
- [阶段 17 · 01 托管 LLM 平台](../../01-managed-llm-platforms/docs/zh.md)、[阶段 17 · 02 Inference 平台经济性](../../02-inference-platform-economics/docs/zh.md)：自托管与托管是先于本节的决策。
- [阶段 17 · 12 边缘 Inference](../../12-edge-inference/docs/zh.md)：Apple Silicon、CPU 等非数据中心硬件上的推理。

### 本节被哪些后续内容用到
- [阶段 17 · 18 生产服务技术栈：KV 卸载与缓存感知路由](../../18-vllm-production-stack-lmcache/docs/zh.md)、[阶段 17 · 17 Prefill 与 Decode 分离](../../17-disaggregated-prefill-decode/docs/zh.md)：选定 vLLM 后在 100+ / 10k+ 用户规模上的组合方式。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)、[阶段 17 · 22 对 LLM APIs 进行负载测试](../../22-load-testing-llm-apis/docs/zh.md)：验证选型的指标与方法。
- [阶段 17 · 20 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../20-shadow-canary-progressive/docs/zh.md)：从 TGI 或 Ollama 迁移时的发布方式。
- [阶段 17 · 27 LLMs 的 FinOps](../../27-finops-llms/docs/zh.md)：自托管后的成本归因从 token 单价变成 GPU 小时分摊。
- [阶段 10 · 12 Inference Optimization](../../../10-llms-from-scratch/12-inference-optimization/docs/zh.md)：引擎内部各类优化的原理。

### 延伸关键词
`llama.cpp` · `Ollama` · `vLLM` · `SGLang` · `TGI maintenance mode` · `TensorRT-LLM` · `ROCm` · `Metal` · `GGUF` · `safetensors` · `RadixAttention` · `automatic prefix caching` · `chunked prefill` · `production-stack` · `LMCache` · `OpenAI-compatible API`
