# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 18 节 百万 Token 上下文中的长视频理解 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`），无需 GPU、无需网络

---

## 1. 这份代码在考察什么

讲义把长视频理解归纳为四条路线：brute context、ring attention、token compression、agentic retrieval。代码用三个模拟把其中的"量级感"和"流程感"落地：

1. **token 预算表**：1 分钟到 2 小时的视频在不同 FPS、每帧 token 数下会产生多少 token，能放进多大的上下文——对应学习目标"Compute total visual-token counts for long-form video"。
2. **needle-in-a-haystack 模拟**：在视频随机位置插入"针"，按各模型的假设召回曲线查出召回概率——对应讲义 "Needle-in-a-haystack benchmarks"。
3. **VideoAgent 式检索流程**：打印 LLM → 工具 → VLM → LLM 的调用轨迹，并与 brute context 比较 token 用量——对应讲义 "Path 4: Agentic retrieval"。

> 一句话：**先算清楚"长视频到底有多少 token"，再决定是硬塞、压缩还是检索**。代码里的召回率、检索结果都是设定好的假数据，学习重点是公式和流程，而不是数字本身。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `tokens(duration_s, fps, per_frame)` | 函数 | `int(时长 × FPS × 每帧 token)` | token 预算公式 |
| `budget_table()` | 函数 | 打印 7 种场景的 token 数和"能放进哪里" | 规模直觉 |
| `Needle` | dataclass | 针的位置与标记文字（实际未被使用） | NIAH 中的"针" |
| `nih_trial(duration_s, curve)` | 函数 | 随机插针，按位置百分比查召回曲线 | NIAH 单次试验（简化） |
| `nih_simulation()` | 函数 | 对 4 个模型各做 1 次试验并打印 | 不同模型的召回对比 |
| `agentic_retrieval_sim(question, duration)` | 函数 | 生成 5 步调用轨迹和 token 用量 | VideoAgent 流程 |
| `agentic_demo()` | 函数 | 打印轨迹并与 brute context 比较 | 成本对比 |
| `main()` | 函数 | 串起三个演示，最后打印策略选择表 | 路线选择 |

数据流：`random.seed(5)` → `budget_table`（纯计算）→ `nih_simulation`（4 次 `random.uniform`）→ `agentic_demo`（3 次 `random.uniform`）→ 打印 STRATEGY PICKER。

---

## 3. 逐段精讲

### 3.1 token 预算公式与预算表

```python
def tokens(duration_s: float, fps: float, per_frame: int) -> int:
    return int(duration_s * fps * per_frame)
```

- 这是整节最重要的一行：**token = 秒数 × 每秒帧数 × 每帧 token 数**。`int()` 向下取整，FPS 可以是小数（如 0.25）。
- 每帧 81 token 的来历（讲义）：384 分辨率约 729 token（27×27 的 patch 网格），3×3 池化后变成 9×9 = 81。

```python
    cases = [
        (60, 1, 81,     "32k+"),
        (300, 1, 81,    "32k"),
        (300, 2, 81,    "128k"),
        (1800, 1, 81,   "256k"),
        (3600, 1, 81,   "1M / LongVILA"),
        (7200, 1, 81,   "Gemini 2.5 only"),
        (7200, 1, 32,   "agentic retrieval"),
    ]
    for dur, fps, pf, fits in cases:
        t = tokens(dur, fps, pf)
        print(f"{dur//60}min{' ':<8}{fps:>5}{pf:>12}{t:>12,}   {fits}")
```

- 每个 case 是一个四元组，`for dur, fps, pf, fits in cases` 直接解包。
- `{t:>12,}`：右对齐、占 12 位、加千分位逗号。
- ⚠️ **列对不齐**：`f"{dur//60}min{' ':<8}"` 先输出变长的 "1min"/"120min"，再固定加 8 个空格，导致分钟数位数不同的行整体错位（运行输出里清晰可见）。应写成 `label = f"{dur//60}min"` 再 `f"{label:<14}"`。
- ⚠️ "fits in" 列是手写的说明，不是计算结果，有两处值得商榷：60 分钟 291,600 token 超过讲义给出的 LongVILA 训练上下文（约 268,800）；最后一行 230,400 token 实际是"更狠的池化后直接塞进 256k"，与 agentic retrieval 无关（详见测验 Q9）。

### 3.2 needle-in-a-haystack：只查表，不判分

```python
@dataclass
class Needle:
    t: float
    marker: str


def nih_trial(duration_s: float, model_recall_curve: list[tuple[float, float]]) -> dict:
    needle_t = random.uniform(0, duration_s)
    needle = Needle(t=needle_t, marker="unique sticker")
    pct_into_video = needle_t / duration_s
    for thresh, recall in model_recall_curve:
        if pct_into_video <= thresh:
            return {"needle_time": needle_t,
                    "pct_into_video": pct_into_video,
                    "recall_prob": recall}
    return {"needle_time": needle_t,
            "pct_into_video": pct_into_video,
            "recall_prob": model_recall_curve[-1][1]}
```

- `model_recall_curve` 是"分段常数"的召回曲线：`[(0.1, 0.98), (0.5, 0.90), (1.0, 0.85)]` 表示针在前 10% 时召回 0.98、10%–50% 时 0.90、后半段 0.85。
- 循环按顺序找第一个 `pct_into_video <= thresh` 的档位，返回对应召回率；最后的 `return` 是兜底（曲线最后一个阈值小于 1.0 时才会走到）。
- ⚠️ **没有真正"测试"**：`needle` 对象创建后没有使用，`marker` 没有出现在任何提问中，函数只返回一个概率，不抛硬币也不统计命中。讲义 "Use It" 说 "inject a marker at a random timestamp, ask a question, score recall"，代码只做了第一步。
- ⚠️ **曲线是假设值**：例如 30 分钟曲线后半段设为 0.75，按位置均匀分布的期望召回只有 `0.1×0.95 + 0.4×0.85 + 0.5×0.75 = 0.81`，低于讲义 "Open 72B models ... score ~85-90% at 30 minutes"。
- 把它改成多次试验的 `nih_recall` 见测验 Q10（10,000 次实测 0.8153，与理论值 0.81 吻合）。

```python
    models = [
        ("Qwen2.5-VL-72B @ 15min",   900,  [(0.1, 0.98), (0.5, 0.90), (1.0, 0.85)]),
        ("Qwen2.5-VL-72B @ 30min",   1800, [(0.1, 0.95), (0.5, 0.85), (1.0, 0.75)]),
        ("Gemini 2.5 Pro @ 90min",   5400, [(0.1, 0.99), (0.5, 0.99), (1.0, 0.99)]),
        ("VideoAgent (retrieval) 2h", 7200, [(0.1, 0.92), (0.5, 0.92), (1.0, 0.92)]),
    ]
```

- 曲线的"形状"传达了讲义的定性结论：开源 72B 随位置靠后、视频变长而衰减；Gemini 2.5 Pro 全程 >99%；检索方案的召回与位置无关（只取决于检索工具好不好），所以是一条水平线。
- 每个模型只做**一次**试验，结果完全取决于那一个随机位置，不能用来比较模型优劣。

### 3.3 VideoAgent 式检索模拟

```python
def agentic_retrieval_sim(question: str, video_duration: float) -> dict:
    trace = []
    trace.append(("LLM  ", f"reading question: '{question}'"))
    query = question.split()[-1].lower()
    trace.append(("LLM  ", f"calling tool: find_clips(keyword='{query}')"))
    hits = sorted([random.uniform(0, video_duration) for _ in range(3)])
    trace.append(("TOOL ", f"returned 3 clips: {[round(h,1) for h in hits]}"))
    trace.append(("VLM  ", f"encoding 3 x 30s clips (~7290 tokens total)"))
    trace.append(("LLM  ", "composing answer from clip descriptions"))
    tokens_used = 3 * 30 * 81 + 200
    return {"steps": trace, "tokens": tokens_used}
```

- 轨迹 `trace` 是 `(角色, 消息)` 元组的列表，正好对应讲义 VideoAgent 的 5 步：读问题 → 调工具 → 工具返回时间戳 → VLM 读片段 → LLM 作答。
- "关键词提取"只是取问题的最后一个词（`"at what point does the cat jump"` → `"jump"`）。真实系统由 LLM 生成结构化查询（如 `{"object": "cat", "action": "jump"}`）。
- 工具返回的是 3 个**随机时间戳**，与关键词毫无关系——这正说明了讲义的观点：检索质量才是瓶颈，代码把这一环直接假设掉了。
- token 估算：每个片段 30 秒 × 1 FPS × 81 = 2,430，3 个片段 7,290，再加 200 个文本 token，共 7,490。
- 第 4 步的字符串 `f"encoding 3 x 30s clips (~7290 tokens total)"` 虽然写了 `f` 前缀，但里面没有 `{}` 占位符，数字是写死的。

```python
    print(f"  vs brute context 2h @ 1 FPS: ~583,000 tokens")
    print(f"  -> 99% cheaper inference for single-event queries")
```

- `7,490 / 583,200 ≈ 1.28%`，即便宜约 98.7%。
- ⚠️ 这个对比**没有计入建立检索索引的成本**：要让 `find_clips` 真正找到"猫跳"的片段，必须事先把整段视频切片、生成描述或嵌入——这一步要处理全部视频，只是可以离线完成、被多次查询摊薄。另外多轮 LLM 调用的延迟也没算。

### 3.4 策略选择表

```python
    print("  <15 min            : brute context (Qwen2.5-VL-72B)")
    print("  15-60 min          : LongVILA / Video-XL / Gemini 2.5")
    print("  >1h general QA     : Gemini 2.5 Pro (closed frontier)")
    print("  >1h specific query : VideoAgent (agentic retrieval)")
```

- 与讲义 "Which path to pick" 一致：时长越长越倾向检索；同时区分"general QA"（需要通盘理解，用长上下文）和"specific query"（单事件定位，用检索）。这个"问题类型"维度和时长同样重要，skill 文件也强调 "For holistic-summary questions it loses to brute context"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用一个乘法公式算 token | 帮助建立量级直觉 | 真实模型还有特殊 token、文本 prompt、动态分辨率等开销，需按模型 tokenizer 实测 |
| "fits in" 列手写 | 简洁 | 容易与讲义数字不一致；可改为根据上下文表自动判断 |
| 召回曲线分段常数、单次试验 | 让每个模型的"衰减形状"一目了然 | 不是测量；真实 NIAH 要插入可见标记、提问并自动判分，多次试验画热力图 |
| 检索工具返回随机时间 | 避免依赖检索系统 | 把最难的部分（检索质量）假设掉了；生产中需评估检索 recall |
| 关键词 = 问题最后一个词 | 一行代码 | 对 "when does the cat jump?"（带问号）就会得到 `jump?`；应由 LLM 生成查询 |
| token 成本只算在线部分 | 突出检索的推理优势 | 遗漏离线索引成本与多轮调用延迟 |
| `random.seed(5)` | 保证每次运行输出相同 | 7 次随机调用的顺序一旦改变，所有结果都会变 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 延迟求值类型注解 |
| 类型注解中的嵌套泛型 | `list[tuple[float, float]]` | "由二元浮点元组组成的列表" |
| `@dataclass` | `class Needle: t: float; marker: str` | 自动生成构造函数 |
| 元组列表 + 循环解包 | `for dur, fps, pf, fits in cases:` | 一次取出四个字段 |
| 整除 `//` | `dur//60` | 秒转分钟，结果为整数 |
| f-string 宽度与千分位 | `{t:>12,}`、`{fps:>5}` | 右对齐占 12 位并加逗号；右对齐占 5 位 |
| f-string 浮点格式 | `{r['needle_time']:>6.1f}`、`{r['recall_prob']:.2f}` | 宽 6、1 位小数；2 位小数 |
| f-string 中的表达式 | `{[round(h,1) for h in hits]}` | 花括号里可以放任意表达式，包括列表推导式 |
| 不必要的 f 前缀 | `f"encoding 3 x 30s clips (~7290 tokens total)"` | 没有占位符时 f 前缀无作用（无害，但会被 linter 提示） |
| 字符串方法链 | `question.split()[-1].lower()` | 按空白切分 → 取最后一个 → 转小写 |
| `random.uniform(a, b)` | `random.uniform(0, duration_s)` | 区间内均匀分布的随机浮点数 |
| `random.seed` | `random.seed(5)` | 固定随机序列，保证可复现 |
| `sorted` + 列表推导式 | `sorted([random.uniform(...) for _ in range(3)])` | 生成 3 个随机数并排序；`_` 表示不用的循环变量 |
| 函数返回字典 | `return {"steps": trace, "tokens": tokens_used}` | 用字典打包多个返回值，调用方按键取用 |
| `if __name__ == "__main__":` | 文件末尾 | 作为脚本运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，耗时不到 1 秒）：

```text
LONG-VIDEO TOKEN BUDGETS
------------------------------------------------------------
duration        FPS   per_frame      tokens       fits in
1min            1          81       4,860   32k+
5min            1          81      24,300   32k
5min            2          81      48,600   128k
30min            1          81     145,800   256k        ← 两位数分钟，整行右移一格
60min            1          81     291,600   1M / LongVILA   ← 超过 LongVILA 的 ~268,800
120min            1          81     583,200   Gemini 2.5 only
120min            1          32     230,400   agentic retrieval   ← 其实是"激进池化塞进 256k"

NEEDLE-IN-A-HAYSTACK SIMULATION (single trial per model)
------------------------------------------------------------
  Qwen2.5-VL-72B @ 15min            needle@ 560.6s  p(recall)=0.85
  Qwen2.5-VL-72B @ 30min            needle@1335.2s  p(recall)=0.75
  Gemini 2.5 Pro @ 90min            needle@4294.0s  p(recall)=0.99
  VideoAgent (retrieval) 2h         needle@6785.6s  p(recall)=0.92

VIDEOAGENT-STYLE RETRIEVAL (2-hour video)
------------------------------------------------------------
  [LLM  ] reading question: 'at what point does the cat jump'
  [LLM  ] calling tool: find_clips(keyword='jump')
  [TOOL ] returned 3 clips: [208.8, 5327.3, 6640.7]
  [VLM  ] encoding 3 x 30s clips (~7290 tokens total)
  [LLM  ] composing answer from clip descriptions

  total tokens used: ~7,490
  vs brute context 2h @ 1 FPS: ~583,000 tokens
  -> 99% cheaper inference for single-event queries
```

逐项解读：

- **预算表**：每一行都可以用 `时长 × FPS × 81` 心算验证，例如 30 分钟 `1,800 × 81 = 145,800`。注意 FPS 翻倍（5min 那两行）token 也翻倍，而 3×3 池化让每帧从 729 降到 81，相当于省掉 89%。
- **NIAH**：四根针分别落在视频的 62.3%、74.2%、79.5%、94.2% 处，全都在后半段，所以两个 Qwen 配置都取到曲线的最后一档（0.85 和 0.75）。Gemini 和 VideoAgent 的曲线是平的，位置无关。由于每个模型只试一次，这一段只能说明"查表逻辑"，不能说明模型强弱。
- **检索轨迹**：工具返回的 208.8、5327.3、6640.7 秒是 `random.seed(5)` 之后第 5–7 次随机数，与"jump"没有任何关系。token 用量 7,490 约为 brute context 的 1.28%。
- **结论**：数字本身是示意性的，真正要带走的是三件事——预算公式、NIAH 的"长度 × 位置"二维评测思路、检索路线把成本转移到了离线索引与检索质量上。

---

## 7. 动手改一改

1. **修表格**：把 `budget_table` 的时长列改成固定宽度对齐；再增加一列 `fits_128k`，用 `t <= 128_000` 自动判断，而不是手写说明。
2. **讲义练习 1**：加一行 `(2700, 1, 81, ...)`，验证 45 分钟讲座为 218,700 token；再算出 80k 上下文下 1 小时视频的最大 FPS（约 0.27，见测验 Q11）。
3. **真正的 NIAH**：实现 `nih_recall(duration_s, curve, n_trials)`，多次插针并按概率判定答对，输出经验召回率；再把位置分成 10 个桶，打印每个桶的召回率（模拟热力图的一行）。
4. **更真实的检索**：给 2 小时视频构造一个"片段描述"列表（如每 30 秒一句话，其中只有 2 段包含 "cat jumps"），让 `find_clips` 用关键词匹配返回真实命中的片段，再统计检索 recall。
5. **讲义练习 4**：用 NumPy 实现玩具 ring attention（online softmax 合并），验证与完整注意力误差在 1e-15 量级；再去掉轮转步骤观察误差（参考测验 Q12）。
6. **进阶**：写一个 `pick_strategy(duration_s, question_type, open_only, context_limit)` 函数，把讲义 "Which path to pick" 和 skill 文件的硬性否决规则编码成可执行逻辑。

---

## 8. 常见坑

- **只算视觉 token**：系统 prompt、问题、对话历史、时间戳特殊 token 也占上下文；skill 文件建议视觉 token 超过上下文 40% 就要警惕。
- **把 ring attention 当成线性复杂度**：它分摊的是单卡显存和计算，总 FLOPs 仍是 O(n²)，推理成本依旧随长度二次增长。
- **单次试验下结论**：NIAH 必须多次插针、覆盖多个位置和多个时长，单次结果只是一枚硬币。
- **忽略检索的离线成本**：检索方案的"便宜"是在线推理便宜，索引构建同样要处理全部视频。
- **把检索当万能**：全局摘要类问题、线索分散的问题，检索方案会以偏概全。
- **混淆"能放进上下文"与"能用好上下文"**：放得进 1M token 不代表在第 800k 个 token 处仍能准确召回，这正是 NIAH 要测的东西。
