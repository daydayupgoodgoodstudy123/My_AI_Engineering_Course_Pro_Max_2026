# 测验 · Qwen-VL 系列与动态帧率视频（Qwen-VL Family and Dynamic-FPS Video）

> **阶段 12 · 多模态 AI · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 注：中文讲义为机器翻译（例如 "Qwen" 多处被译成 "Quen"），有疑义以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 四代演进 | Qwen-VL（2023）→ Qwen2-VL（2024）→ Qwen2.5-VL（2025）→ Qwen3-VL（2025），每代押注一个关键设计，开放社区一年内跟进 |
| 2 | Qwen-VL（2023） | 讲义：OpenCLIP ViT-bigG/14 encoder + 256 个 query 的单层 Q-Former 式适配器 + Qwen-7B；448×448；以文本形式输出 `<box>` 坐标做 grounding；中英双语 |
| 3 | 原生动态分辨率 | Qwen2-VL 的 ViT 接受任意能被 28 整除的 H×W（patch 14 + 2×2 空间合并）；1120×672 → 40×24 = 960 个视觉 token；不 resize、不切块、无缩略图 |
| 4 | M-RoPE | 每个 token 带 3D 位置 (t, h, w)；hidden 维切成时间、高、宽三个 band，各自按本轴位置旋转；图像 t = 0，视频 t = 帧序号；**不需要位置 embedding 表** |
| 5 | RoPE 的相对性 | 旋转后 q·k 只依赖两者在每个轴上的位置**差**，所以 M-RoPE 天然编码 2D/3D 相对位置 |
| 6 | MLP projector | Qwen2-VL 去掉 Q-Former，在合并后的 patch token 上接 2 层 MLP |
| 7 | Qwen2.5-VL 的视频升级 | 动态 FPS + 绝对时间（看到的是秒数而不是帧号）；ViT 中使用 window attention（每隔几层一次全局注意力）；JSON 工具调用输出；MRoPE 位置随输入尺度缩放 |
| 8 | 动态 FPS 算法 | `fps_max = B / (T × tokens_per_frame)`，在候选 FPS 中按运动强度挑一个 ≤ fps_max 的；均匀采样并插入时间信息 |
| 9 | 结构化 agent 输出 | 输出 JSON 后用 `json.loads` 确定性解析，取代自由文本 + 正则；讲义：ScreenSpot 从 Qwen2-VL 的 55% 升到 84% |
| 10 | Qwen3-VL 与 `min/max_pixels` | Qwen3-VL 是"整合而非重造"：更大的 LLM 底座、更多数据、thinking mode，ViT 与 M-RoPE 不变；`min_pixels` / `max_pixels` 限定总像素数，从而限定 token 数 |

### 核心技能（能动手做到）

- [ ] 给定图像尺寸，手算 Qwen2-VL 风格的视觉 token 数（除以 28 后相乘）
- [ ] 手算 M-RoPE 在给定 (t, h, w) 下各 band 前几对维度的旋转角，并说清"按 band 维度"与"按整个 hidden 维度"计算频率的区别
- [ ] 用代码验证 RoPE 的相对位置性质：位置整体平移后 q·k 不变
- [ ] 给定时长、token 预算和运动强度，算出动态 FPS 采样的帧率、帧数和总 token 数，并发现本节采样器的超预算 bug
- [ ] 为 VLM 的 JSON 工具调用输出写一个健壮的解析器（处理多余文字、多个对象、截断、类型校验）
- [ ] 按任务（网球、菜谱、UI agent、监控）给出 FPS、分辨率与输出格式配置

---

## 二、基础自测（选择题）

**Q1.** Qwen2-VL 的 ViT 使用 patch 14，并把相邻 2×2 个 patch 合并成 1 个 token。一张 1120×672 的图像会产生多少个视觉 token？

- A. 3840
- B. 960
- C. 1920
- D. 576

**Q2.** 关于 M-RoPE，下列说法正确的是：

- A. 它为 (t, h, w) 学习一张三维位置 embedding 表，加到输入上
- B. 它只对时间轴做旋转，空间位置交给 ViT 自己处理
- C. 它把三个轴的正弦位置向量相加后加到 token embedding 上
- D. 它把 hidden 维分成时间、高、宽三个 band，每个 band 按本轴位置旋转 query/key；图像 t = 0、视频 t = 帧位置；不需要位置表

**Q3.** 用本节 `VideoPlan`（`tokens_per_frame=81`，`budget=32768`）规划一段 10 分钟、低运动（`motion="low"`）的监控视频，结果是：

- A. fps = 0.5，300 帧，24300 个 token
- B. fps = 1，600 帧，48600 个 token
- C. fps = 0.25，150 帧，12150 个 token
- D. fps = 0.1，60 帧，4860 个 token

**Q4.** 按讲义，Qwen-VL 系列四代的主要升级顺序是：

- A. Qwen-VL 引入 M-RoPE → Qwen2-VL 引入 Q-Former → Qwen2.5-VL 引入 grounding → Qwen3-VL 引入动态 FPS
- B. Qwen-VL 引入动态 FPS → Qwen2-VL 引入 JSON 输出 → Qwen2.5-VL 引入 448 分辨率 → Qwen3-VL 引入 MLP projector
- C. Qwen-VL：448 分辨率 + grounding + Q-Former → Qwen2-VL：M-RoPE + 原生分辨率 + MLP → Qwen2.5-VL：动态 FPS + 绝对时间 + window attention + JSON agent → Qwen3-VL：更大底座、更多数据、thinking mode
- D. 四代架构完全相同，只是参数量不同

**Q5.** Qwen2.5-VL 用真实时间（秒）而不是帧序号来标记视频帧，最主要的原因是：

- A. 秒数比帧序号占用更少的 token
- B. 帧序号无法用 RoPE 编码
- C. 动态 FPS 下同一个帧序号在不同视频里对应不同的真实时刻；只有真实时间才能让模型回答"什么时候发生""持续了多久"
- D. 为了兼容 Q-Former

**Q6.** 本节 `parse_tool_call` 收到 `'Sure, clicking at {"tool": "mouse_click", "coords": [800, 400]} now.'`，返回：

- A. `{'tool': 'mouse_click', 'coords': [800, 400]}`——第一次 `json.loads` 失败后，截取第一个 `{` 到最后一个 `}` 再解析成功
- B. `{'tool': 'PARSE_ERROR', 'raw': ...}`，因为前后有多余文字
- C. 抛出 `json.JSONDecodeError`
- D. 字符串 `'mouse_click'`

**Q7.** Qwen2.5-VL 在 ViT 中使用 window attention 的主要目的是：

- A. 让视频帧之间可以互相注意
- B. 取代 M-RoPE 的位置编码作用
- C. 减少 LLM 的上下文长度
- D. 提升吞吐：大多数层只在局部窗口内做空间注意力，每隔几层再做一次全局注意力，高分辨率输入下计算量不再随 token 数平方增长

**Q8.** 本节 `demo_mrope()` 对 "text token i=12" 打印的 first-pair angles (t, h, w) 是：

- A. `[12.0, 12.0, 12.0]`
- B. `[12.0, 0.0, 0.0]`
- C. `[0.0, 0.0, 0.0]`
- D. `[12.0, 1.2, 0.12]`

---

## 三、动手 / 代码题

**Q9.**（讲义练习 1）对位置 (t=3, h=5, w=7)、hidden = 48（每个 band 16 维）、base = 10000：

1. 按本节代码 `mrope_angles` 的公式 `theta = base ** (-2 * i / dim)`（`dim` 是 **band** 维度 16），写出每个 band 前三对的旋转角。
2. 若按讲义 RoPE 公式 `theta_i = 10000^(-2i/d)` 中的 `d` 理解为整个 hidden（48），前三对的旋转角又是多少？
3. 两种做法的频率谱有什么区别？

**Q10.** 代码把文本 token 的位置设为 `(t = text_index, h = 0, w = 0)`，图像 patch 设为 `(0, h, w)`：

```python
    positions = [
        ("text token i=0",      0, 0, 0),
        ("text token i=12",     12, 0, 0),
        ("image patch (h=5, w=7)", 0, 5, 7),
        ("video frame t=3 (h=5, w=7)", 3, 5, 7),
    ]
```

1. 对文本 token 调用 `mrope_rotate(cfg, q, 5, 0, 0)`，高、宽两个 band（后 32 维）发生了什么变化？这对"把一个预训练好的 1D RoPE 语言模型改造成 M-RoPE"意味着什么？
2. Qwen2-VL 论文的做法是：文本 token 的三个分量取**相同**的位置 ID（M-RoPE 退化为 1D RoPE）；每种模态的起始位置 = 前一模态最大位置 ID + 1。请写一个函数 `pack_positions(segments)`，为"5 个文本 token + 一张 2×3 的图像 + 3 个文本 token"生成 (t, h, w) 列表。
3. 讲义 "Use It" 说代码实现了 "M-RoPE position computation for a packed sequence mixing text, image patches, and video frames"，代码实际做到了吗？

**Q11.** 阅读 `VideoPlan.fps()`：

```python
    def fps(self) -> float:
        fps_max = self.budget / (self.duration_s * self.tokens_per_frame)
        if self.motion == "high":
            candidates = [8, 4, 2, 1, 0.5, 0.25]
        elif self.motion == "medium":
            candidates = [4, 2, 1, 0.5, 0.25]
        else:
            candidates = [1, 0.5, 0.25, 0.1]
        for f in candidates:
            if f <= fps_max:
                return f
        return candidates[-1]
```

1. 对 2 小时（7200 秒）的低运动视频，`fps()`、帧数、`total_tokens()` 分别是多少？是否超过 `budget = 32768`？
2. 讲义练习 2："10 分钟监控录像按 1 FPS、384 分辨率 3 倍池化，共多少 token？Qwen2.5-VL 默认 32k 上下文放得下吗？"请计算并与代码选择的方案对比。
3. 讲义的算法里每帧之间要插入 `<time>t</time>`，skill 文件要求为 prompt 和输出"leave 20% slack"。`total_tokens()` 考虑了这两点吗？请修改 `fps()` 与 `total_tokens()`，使其在超预算时报错、并计入每帧的时间标记开销（假设每个时间标记 4 个 token）。

**Q12.** `parse_tool_call` 的健壮性测试（以下结果均为实际运行所得）：

| 输入 | 返回 |
|------|------|
| `'[1,2]'` | `[1, 2]` |
| `'null'` | `None` |
| `'click {"tool":"a"} then {"tool":"b"}'` | `{'tool': 'PARSE_ERROR', ...}` |
| `'{"tool":"click","coords":[1,2],}'`（尾逗号） | `{'tool': 'PARSE_ERROR', ...}` |
| 包在 ```` ```json ... ``` ```` 代码块里的合法 JSON | 正确解析 |

1. 指出这些结果暴露的三类问题。
2. 写一个改进版 `parse_tool_calls(raw) -> list[dict]`：能从文本中依次提取**多个** JSON 对象，只接受 `dict`，并校验 `tool` 字段存在、`coords`（若有）是两个数字。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 M-RoPE？它与 1D RoPE、学习式 2D 位置 embedding 相比有什么优势？为什么需要三个轴？

**Q14.**（原理深挖）（讲义练习 4）Qwen-VL（2023）用 Q-Former，Qwen2-VL 起改用简单的 MLP。为什么 MLP 在 2024–2025 年够用，而在 2023 年不够？

**Q15.**（工程实践）（讲义练习 3）分别为 30 秒网球对打、30 秒菜谱演示、30 秒 UI agent 操作录屏选择 FPS，并说明理由；如果是 10 分钟监控录像呢？

**Q16.**（场景设计）你要用 Qwen2.5-VL 做一个 GUI agent。请设计从"截图输入"到"执行点击"的完整输出与解析链路：输出格式、解析与校验、失败重试、坐标处理。

**Q17.**（追问型）"原生动态分辨率"（Qwen2-VL）和"AnyRes 切块"（LLaVA 系）各有什么优缺点？线上服务如何控制原生分辨率带来的 token 成本？

---

## 五、参考答案与解析

### Q1 — 答案：B

每个 token 对应 `14 × 2 = 28` 像素见方。`1120 / 28 = 40`，`672 / 28 = 24`，`40 × 24 = 960`，与讲义一致。A（3840 = 80 × 48）是忘了 2×2 合并、按 14 像素 patch 计算的结果；C、D 无对应计算。

### Q2 — 答案：D

讲义："Each token carries a 3D position (t, h, w) instead of 1D... RoPE rotates query/key vectors by a frequency per axis. No positional embedding table." skill 文件甚至把"声称 M-RoPE 需要位置表"列为 hard reject。A、C 描述的是加性位置编码；B 漏掉了空间轴，而空间轴正是原生分辨率能工作的关键。

### Q3 — 答案：A

`fps_max = 32768 / (600 × 81) ≈ 0.674`。低运动候选 `[1, 0.5, 0.25, 0.1]` 中第一个 ≤ 0.674 的是 0.5；帧数 `int(600 × 0.5) = 300`，token `300 × 81 = 24300`，与实际运行输出一致。B 是讲义练习 2 的固定 1 FPS 方案，48600 超出预算；C、D 是更靠后的候选，代码不会选到。

### Q4 — 答案：C

与讲义各小节标题和代码最后的 "LINEAGE SUMMARY" 一致。A、B 把各代的创新张冠李戴；D 错，Qwen2-VL 是一次真正的架构更换（"The architecture change was the decisive move"），只有 Qwen3-VL 才是"整合而非重造"。

### Q5 — 答案：C

动态 FPS 下，同样是"第 8 帧"，在 1 FPS 视频里是第 8 秒，在 4 FPS 视频里是第 2 秒。只用帧序号，模型无法学到"真实时间"这个量，也就无法做时间定位和时长估计。讲义："Instead of positional indices (frame 0, 1, 2...), use actual timestamps." A 错，时间信息反而增加开销；B 错，帧序号完全可以用 RoPE 编码（Qwen2-VL 就是这样做的）；D 无关。

### Q6 — 答案：A

整串不是合法 JSON，第一次 `json.loads` 抛 `JSONDecodeError`；`find("{")` 和 `rfind("}")` 截出 `{"tool": "mouse_click", "coords": [800, 400]}`，再次解析成功。实际运行输出 `parsed : {'tool': 'mouse_click', 'coords': [800, 400]}`。B 是第三个示例（缺右括号）的结果；C 错，异常被 `except` 捕获；D 无依据。

### Q7 — 答案：D

讲义："Spatial attention is windowed (local within blocks) for throughput; global attention every few layers." 原生分辨率下一张大图可能有上万个 patch，全局注意力代价是平方级；窗口注意力把大部分层的代价降到线性。A 是时间维的事；B 错，位置编码仍由 RoPE 负责；C 错，window attention 发生在 ViT 内部，不改变送入 LLM 的 token 数。

### Q8 — 答案：B

代码中文本 token 的位置是 `(12, 0, 0)`，每个 band 第一对的 `theta = base ** 0 = 1`，所以角度就是位置本身：`[12.0, 0.0, 0.0]`。注意 A 恰恰是 **Qwen2-VL 论文**对文本 token 的做法（三个分量取相同 ID，退化为 1D RoPE），而本节代码和讲义采用了 `h = w = 0` 的简化，见 Q10。C 是 i=0 的结果；D 是把三个 band 当成同一 band 的前三对。

### Q9 — 参考答案

1. 代码公式（band 维度 16）：`theta_i = 10000^(-2i/16) = 10000^(-i/8)`，即 `1, 0.3162, 0.1`。旋转角 = 位置 × theta（已用代码运行验证）：
   - t = 3：`3.0, 0.9487, 0.3`
   - h = 5：`5.0, 1.5811, 0.5`
   - w = 7：`7.0, 2.2136, 0.7`
2. 若用整个 hidden 48：`theta_i = 10000^(-2i/48)`，即 `1, 0.6813, 0.4642`，旋转角为：
   - t = 3：`3.0, 2.0439, 1.3925`
   - h = 5：`5.0, 3.4065, 2.3208`
   - w = 7：`7.0, 4.769, 3.2491`
3. 区别：代码让每个 band **各自**从最高频（theta = 1）衰减到 `10000^(-14/16) ≈ 3.2e-4`，三个 band 的频率谱完全相同；"整体计算后再切分"的做法则只有一个 band 拿到最高频，另外的 band 拿到中、低频，频率谱互不相同。前者让三个轴在"分辨率"上对称；后者与原 LLM 的 1D RoPE 频率表兼容（切分方式只是把同一张频率表分给三个轴）。讲义的 `theta_i = 10000^(-2i/d)` 写的是经典 RoPE，没有说明 M-RoPE 里 `d` 指什么，代码选择了 band 维度。

### Q10 — 参考答案

1. 实际验证：`mrope_rotate(cfg, q, 5, 0, 0)` 的后 32 维与输入**完全相同**（位置 0 的旋转是恒等变换）。也就是说，对文本而言只有前 16 维（1/3）编码了顺序信息，后 2/3 维度对所有文本 token 都"位置不变"。预训练 LLM 的 1D RoPE 是在全部维度上编码位置的，这样改造会让它原有的位置感知大幅退化，需要大量重新训练。Qwen2-VL 的做法（三个分量取相同 ID）让纯文本时 M-RoPE 与原 1D RoPE 完全等价，能无缝继承 LLM 的能力。
2. 参考实现：

```python
def pack_positions(segments):
    """segments: [("text", n)] 或 [("image", H, W)]；返回 [(t, h, w), ...]"""
    pos, nxt = [], 0
    for seg in segments:
        if seg[0] == "text":
            for i in range(seg[1]):
                pos.append((nxt + i, nxt + i, nxt + i))   # 三分量相同 → 1D RoPE
            nxt += seg[1]
        else:                                             # image: t 固定，h/w 为网格坐标
            _, H, W = seg
            for h in range(H):
                for w in range(W):
                    pos.append((nxt, nxt + h, nxt + w))
            nxt = nxt + max(H, W)                         # 前一模态最大 ID + 1
    return pos

print(pack_positions([("text", 5), ("image", 2, 3), ("text", 3)]))
```

   输出：文本 `(0,0,0)…(4,4,4)`；图像 6 个 patch 为 `(5,5,5) (5,5,6) (5,5,7) (5,6,5) (5,6,6) (5,6,7)`；图像中最大 ID 是 7，后续文本从 8 开始：`(8,8,8) (9,9,9) (10,10,10)`。视频则让 t 随帧（或真实时间）递增。
3. 没有。`demo_mrope` 只对 4 个手写位置分别计算角度，没有"打包"一段混合序列，也没有处理模态之间的位置偏移；图像 patch 的 t = 0 与第一个文本 token 的 t = 0 重叠。另外 `mrope_rotate` 从未在 `main()` 中被调用，`MRoPEConfig.hidden` 也没有被检查是否等于三个 band 之和。

### Q11 — 参考答案

1. `fps_max = 32768 / (7200 × 81) ≈ 0.056`，低运动候选 `[1, 0.5, 0.25, 0.1]` 全都大于 0.056，循环结束后 `return candidates[-1]` 返回 **0.1**；帧数 `int(7200 × 0.1) = 720`，`total_tokens = 720 × 81 = 58320`，**超出预算 78%**（实际运行验证）。兜底分支没有检查预算，这正是 skill 文件拒绝规则要防止的情况（"If requested FPS * duration * tokens_per_frame exceeds the context window, refuse and propose pooling or frame reduction"）。
2. 讲义练习 2：`600 秒 × 1 FPS = 600` 帧，`600 × 81 = 48600` 个 token，超过 32768，放不下。代码选择了 0.5 FPS（300 帧、24300 个 token），能放进去，但每 2 秒才看一帧，可能漏掉短暂事件。另一种办法是保持 1 FPS、加大每帧的池化或降低分辨率（例如每帧 40 个 token → 24000）。
3. 都没有。`total_tokens()` 只算 `帧数 × tokens_per_frame`，既没有时间标记开销，也没有留 20% 余量。参考修改：

```python
TIME_TOKENS = 4

def fps(self) -> float:
    usable = self.budget * 0.8                                    # 留 20% 给 prompt + 输出
    fps_max = usable / (self.duration_s * (self.tokens_per_frame + TIME_TOKENS))
    candidates = {"high": [8, 4, 2, 1, 0.5, 0.25],
                  "medium": [4, 2, 1, 0.5, 0.25]}.get(self.motion, [1, 0.5, 0.25, 0.1])
    for f in candidates:
        if f <= fps_max:
            return f
    raise ValueError(f"{self.duration_s}s video does not fit; pool harder or trim frames")

def total_tokens(self) -> int:
    return len(self.frame_times()) * (self.tokens_per_frame + TIME_TOKENS)
```

   顺带一提：`frame_times()` 用 `int(duration × fps)` 向下取整，2.5 秒的视频按 1 FPS 只采到 0 秒和 1 秒两帧，最后 0.5 秒没有被采样（已运行验证）；视频极短时 `max(1, ...)` 保证至少 1 帧。

### Q12 — 参考答案

1. 三类问题：
   - **返回类型不受控**：合法但不是对象的 JSON（`[1,2]`、`123`、`null`）会原样返回 `list` / `int` / `None`，与注解 `-> dict` 不符，下游 `parsed["tool"]` 会崩溃。
   - **只能处理单个对象**：从第一个 `{` 截到最后一个 `}`，遇到"两个工具调用"或"JSON 后面还有带花括号的文字"就失败。
   - **对常见的"近似 JSON"零容错且无校验**：尾逗号、单引号、截断都直接 `PARSE_ERROR`；解析成功时也不检查 `tool` 是否存在、`coords` 是否是两个数。
2. 参考实现（用 `json.JSONDecoder.raw_decode` 从任意位置解析一个完整对象）：

```python
import json

def parse_tool_calls(raw: str) -> list[dict]:
    dec, out, i = json.JSONDecoder(), [], 0
    while (i := raw.find("{", i)) != -1:
        try:
            obj, end = dec.raw_decode(raw, i)
        except json.JSONDecodeError:
            i += 1
            continue
        if isinstance(obj, dict) and isinstance(obj.get("tool"), str):
            c = obj.get("coords")
            if c is None or (isinstance(c, list) and len(c) == 2
                             and all(isinstance(v, (int, float)) for v in c)):
                out.append(obj)
        i = end
    return out

print(parse_tool_calls('click {"tool":"a"} then {"tool":"b","coords":[3,4]}'))
# [{'tool': 'a'}, {'tool': 'b', 'coords': [3, 4]}]
```

   对截断、尾逗号这类错误，常见的恢复策略有：把错误信息和原始输出回传给模型请求重新生成；使用受约束解码（constrained decoding / JSON schema 引导生成）从源头保证格式。讲义练习 5 提到 "the Qwen cookbook" 的恢复策略，但讲义没有给出具体内容，这里不做转述。

### Q13 — 参考回答要点

- **定义**：M-RoPE（Multimodal RoPE）把每个 token 的位置扩展为 (t, h, w)，把 query/key 的维度分成三段，分别按时间、行、列位置做 RoPE 旋转。
- **为什么三个轴**：图像需要 2D 位置（h, w），视频还需要时间 t；只用 1D 会把二维网格"展平"，相邻行的 patch 在序列上相距 W 个位置，空间邻近关系丢失；只有 h、w 又无法区分不同帧。
- **相对于学习式位置表**：不需要为每种分辨率准备位置表，也不需要插值，任意 H×W、任意帧数都能直接编码——这是原生动态分辨率能成立的前提；RoPE 的 q·k 只依赖位置差，天然编码相对空间关系（Q9/Q10 已用代码验证：(3,5,7)/(1,2,2) 与 (13,8,9)/(11,5,4) 两组位置差相同，点积完全相同）。
- **与文本兼容**：文本 token 三分量取相同 ID 时等价于 1D RoPE，能继承预训练 LLM。
- 加分点：讲义提到 Qwen2.5-VL 的 "MRoPE-v2 scaling"——位置随输入尺度缩放，避免 10 分钟视频把频率范围"用完"；可以联系 LLM 长上下文中的 RoPE 外推问题。

### Q14 — 参考回答要点

- 讲义提示："data scale and encoder quality"。
- **2023 年**：视觉-语言对齐数据较少，encoder 输出的 patch 特征与 LLM 空间差距大；Q-Former 用少量可学习 query 先"提炼"出与文本相关的信息，既压缩 token 数（Qwen-VL 固定 256 个），也降低了对齐难度。另外当时 LLM 上下文较短，固定少量 token 是刚需。
- **2024–2025 年**：encoder 更强（SigLIP 类、大规模图文预训练），对齐数据规模和质量（dense caption、OCR、指令数据）大幅提升，LLM 上下文变长；此时简单 MLP 足以完成映射，而且保留全部 patch 的空间结构，对 OCR、grounding 更有利。第 07 节的结论也是：在相同 token 数下 connector 架构几乎不影响结果。
- **token 数的控制方式变了**：从 Q-Former 的固定 query 变成"2×2 合并 + `min/max_pixels`"。
- 常见误区：认为 Q-Former 被淘汰是因为"效果差"——更准确的说法是它作为成本杠杆的优势被其它手段替代了，同时它会丢掉空间网格结构。

### Q15 — 参考回答要点

以 81 tokens/帧、32k 上下文为例（代码的同一设定）：

- **网球对打（30 秒、高运动）**：球速快、动作短促，需要高 FPS。代码选 8 FPS、240 帧、19440 tokens，预算允许（`fps_max ≈ 13.5`）。
- **菜谱演示（30 秒、中等运动）**：动作慢、步骤清晰，2–4 FPS 足够；代码选 4 FPS、120 帧、9720 tokens。也可以只用 1–2 FPS，把预算省下来提高每帧分辨率，以便看清食材和文字。
- **UI agent 录屏（30 秒）**：画面多数时间静止、变化是离散的点击和跳转；关键是**每帧分辨率**（要看清按钮和文字），FPS 可以低（1–2），或者按画面变化做关键帧采样。
- **10 分钟监控**：固定 1 FPS 需要 48600 tokens，放不下；可降到 0.5 FPS（代码的选择），或加大池化、或先用运动检测筛选片段再送入模型。
- 加分点：说明"FPS × 每帧 token"是一个预算平面，网球偏 FPS、UI 偏分辨率；任何需要时间定位的任务都要打开绝对时间编码。

### Q16 — 参考回答要点

- **输出格式**：在系统提示中预先声明工具 schema（`mouse_click`、`type_text`、`scroll` 等），要求模型只输出 JSON（skill 文件："If user requests free-form output for an agent task, refuse and recommend JSON output mode with the tool schema pre-declared in the prompt"）。
- **解析**：先尝试整串 `json.loads`；失败则用 `raw_decode` 扫描提取对象（Q12）；只接受 `dict`；有条件时使用受约束解码直接保证 JSON 合法。
- **校验**：工具名必须在白名单；`coords` 必须是两个数且落在截图尺寸内；参数类型逐项检查。
- **坐标处理**：明确坐标所对应的图像尺寸——模型看到的是经过 `min/max_pixels` 缩放后的图像，执行前要按缩放比例映射回真实屏幕分辨率。
- **失败处理**：解析或校验失败时，把错误信息与原输出回传给模型请求重试（设置最大重试次数）；高风险操作（支付、删除）需要二次确认；记录每一步截图和动作以便回放。
- 加分点：讲义：结构化输出使 ScreenSpot 从 55% 升到 84%；说明"确定性解析"对 agent 可靠性的意义。

### Q17 — 参考回答要点

- **原生动态分辨率**：
  - 优点：保留原始长宽比，没有切块边界把文字或物体切断，不需要缩略图；token 数与图像面积成正比，小图省 token；配合 M-RoPE 位置天然正确。
  - 缺点：大图 token 数可能非常多，成本与延迟难以预测；ViT 中需要 window attention 才能承受。
- **AnyRes 切块**：
  - 优点：复用固定分辨率的 encoder；token 数由切块数决定，可预测。
  - 缺点：切块边界会割裂内容；需要缩略图提供全局视野；长宽比极端时浪费 padding。
- **成本控制**：用 `min_pixels` / `max_pixels` 限定总像素数（讲义 Key Terms："Per-request Qwen2.5-VL controls bounding total pixel count and therefore token count"）；文档/UI 类请求给高上限，普通照片用默认，视频帧用低上限以保住帧数（skill 文件）；按请求类型路由；对超大输入先裁剪感兴趣区域。
- 加分点：给出估算公式 `tokens ≈ (H / 28) × (W / 28)`，并据此设置每类请求的 P95 延迟预算。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 06 任意分辨率视觉：Patch-n'-Pack 与 NaFlex](../../06-any-resolution-patch-n-pack/docs/zh.md)：讲义的先修要求，原生分辨率与 patch 打包的基础。
- [阶段 07 · 04 位置编码 — 正弦、RoPE、ALiBi](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：1D RoPE 的推导，是理解 M-RoPE 的前提。
- [阶段 12 · 03 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former](../../03-blip2-qformer-bridge/docs/zh.md)：Qwen-VL 第一代使用的 Q-Former 式适配器。
- [阶段 12 · 08 LLaVA-OneVision：统一处理单图、多图与视频](../../08-llava-onevision-single-multi-video/docs/zh.md)：与本节"随输入增长"相对的"固定预算"路线。
- [阶段 07 · 15 Attention 变体 — 滑动窗口、稀疏、差分](../../../07-transformers-deep-dive/15-attention-variants/docs/zh.md)：window attention 的原理。

### 本节被哪些后续内容用到
- [阶段 12 · 10 InternVL3：原生多模态 Pretraining](../../10-internvl3-native-multimodal/docs/zh.md)：另一条主流开放 VLM 路线，与 Qwen 系列对比。
- [阶段 12 · 17 视频语言模型：时间 Tokens 与 Grounding](../../17-video-language-temporal-grounding/docs/zh.md)：绝对时间与时间定位的深入讨论。
- [阶段 12 · 18 百万 Token 上下文中的长视频理解](../../18-long-video-million-token/docs/zh.md)：当动态 FPS 也放不下时的长视频方案。
- [阶段 12 · 25 多模态 Agents 与计算机操作（综合项目）](../../25-multimodal-agents-computer-use/docs/zh.md)：JSON 工具调用与 GUI grounding 的实战。
- [阶段 13 · 27 Skill 评估、打包与可移植性](../../../13-tools-and-protocols/27-skill-evals-packaging-and-portability/docs/zh.md)：本节 `outputs/` 中 skill 文件的打包与评估方式。

### 延伸关键词
`M-RoPE` · `RoPE` · `native dynamic resolution` · `2x2 patch merge` · `min_pixels / max_pixels` · `dynamic FPS` · `absolute time encoding` · `window attention` · `GUI grounding` · `ScreenSpot` · `JSON mode` · `constrained decoding` · `raw_decode`
