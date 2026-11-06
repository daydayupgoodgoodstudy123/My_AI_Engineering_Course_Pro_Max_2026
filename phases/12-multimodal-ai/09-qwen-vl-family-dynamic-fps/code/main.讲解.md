# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 09 节 Qwen-VL 系列与动态帧率视频 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`json`、`math`、`dataclasses`、`__future__`）

---

## 1. 这份代码在考察什么

Qwen-VL 系列的三个关键工程点，各对应代码里的一个玩具实现：

1. **M-RoPE**（Qwen2-VL）：位置从 1D 变成 3D (t, h, w)，hidden 维分成三段分别旋转。代码给出角度计算 `mrope_angles` 和真正执行旋转的 `mrope_rotate`。
2. **动态 FPS 采样**（Qwen2.5-VL）：给定时长、token 预算和运动强度，自动选帧率并生成采样时间戳（`VideoPlan`）。
3. **结构化 agent 输出**（Qwen2.5-VL）：把模型输出的 JSON 工具调用解析成 Python 字典，带一层"截取花括号"的容错（`parse_tool_call`）。

最后打印四代模型的演进摘要。

> 一句话：**用纯 Python 把"位置怎么编码、帧怎么采、输出怎么解析"这三件事各写成几十行可运行的代码**。它们都是"心智模型"级别的简化（docstring："The intent is a working mental model, not production code"），其中有几处与真实 Qwen2-VL 做法不同、或在边界情况下出错的地方，值得重点看。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `MRoPEConfig` | `@dataclass` | hidden 总维度、三个 band 的维度、频率底数 base | M-RoPE 配置 |
| `mrope_angles(cfg, t, h, w)` | 函数 | 返回三个 band 每一对维度的旋转角 `pos × theta_i` | RoPE 频率与角度 |
| `mrope_rotate(cfg, vec, t, h, w)` | 函数 | 对长度为 hidden 的向量按三个 band 分别做 2D 旋转 | M-RoPE 旋转（**main 中未调用**） |
| `VideoPlan` | `@dataclass` + 3 个方法 | `fps()` 选帧率、`frame_times()` 生成时间戳、`total_tokens()` 计算 token 数 | 动态 FPS |
| `parse_tool_call(raw)` | 函数 | `json.loads`，失败则截取第一个 `{` 到最后一个 `}` 再试，仍失败返回 `PARSE_ERROR` | JSON agent 输出 |
| `demo_mrope()` | 函数 | 打印 4 个位置的第一对旋转角 | — |
| `demo_sampler()` | 函数 | 4 段视频在 32768 预算下的采样方案 | — |
| `demo_tool_parser()` | 函数 | 4 条模型输出的解析结果 | — |
| `main()` | 函数 | 依次运行三个 demo，打印演进摘要 | 入口 |

数据流：`main()` → `demo_mrope()`（`MRoPEConfig` → `mrope_angles`）→ `demo_sampler()`（`VideoPlan.fps` → `frame_times` → `total_tokens`）→ `demo_tool_parser()`（`parse_tool_call`）→ 打印 LINEAGE SUMMARY。三个 demo 相互独立。

---

## 3. 逐段精讲

### 3.1 `MRoPEConfig` 与 `mrope_angles`：三个 band 的旋转角

```python
@dataclass
class MRoPEConfig:
    hidden: int
    temporal_dim: int
    height_dim: int
    width_dim: int
    base: float = 10000.0


def mrope_angles(cfg: MRoPEConfig, t: int, h: int, w: int) -> list[float]:
    angles = []
    for dim, pos in [(cfg.temporal_dim, t), (cfg.height_dim, h), (cfg.width_dim, w)]:
        band = []
        pairs = dim // 2
        for i in range(pairs):
            theta = cfg.base ** (-2 * i / dim)
            band.append(pos * theta)
        angles.append(band)
    return angles
```

- 一个 band 有 `dim` 维，两两成对，共 `dim // 2` 对；第 i 对的频率 `theta_i = base^(-2i/dim)`，旋转角 = 位置 × 频率。i = 0 时 `theta = 1`，角度就等于位置本身，所以 demo 打印的"第一对角度"就是 (t, h, w)。
- 返回值实际是"列表的列表"（三个 band 各一个列表），类型注解写成 `list[float]` 并不准确，应为 `list[list[float]]`。
- ⚠️ **频率按 band 维度计算**：讲义的经典 RoPE 公式是 `theta_i = 10000^(-2i/d)`，这里的 `dim` 却是 band 维度（16），而不是 hidden（48）。于是三个 band 都拥有从 1 到 `10000^(-14/16) ≈ 3.2e-4` 的完整频率谱。若"先按 hidden 算出一张频率表再切给三个轴"，各轴的频率范围就不同。两种做法都能编码位置，但与预训练 LLM 原有 RoPE 频率表的兼容程度不同（测验 Q9 给出了两种算法的具体数值）。
- ⚠️ `cfg.hidden` 从未使用，也没有检查 `temporal_dim + height_dim + width_dim == hidden`。

### 3.2 `mrope_rotate`：真正执行旋转

```python
    axes = [
        (cfg.temporal_dim, t, 0),
        (cfg.height_dim, h, cfg.temporal_dim),
        (cfg.width_dim, w, cfg.temporal_dim + cfg.height_dim),
    ]
    for dim, pos, start in axes:
        pairs = dim // 2
        for i in range(pairs):
            theta = cfg.base ** (-2 * i / dim)
            angle = pos * theta
            idx0 = start + 2 * i
            idx1 = start + 2 * i + 1
            c, s = math.cos(angle), math.sin(angle)
            v0, v1 = out[idx0], out[idx1]
            out[idx0] = v0 * c - v1 * s
            out[idx1] = v0 * s + v1 * c
```

- 三元组 `(维度, 位置, 起始下标)`：时间 band 占 `[0, 16)`，高度 band 占 `[16, 32)`，宽度 band 占 `[32, 48)`。
- 每一对 `(v0, v1)` 按角度 `angle` 做二维旋转矩阵 `[[c, -s], [s, c]]`，与讲义公式 `q_rot[2i] = q[2i]cos − q[2i+1]sin` 完全对应。
- `v0, v1 = out[idx0], out[idx1]` 先把旧值存下来再覆盖，避免用已更新的 `out[idx0]` 计算 `out[idx1]`。
- 我们额外验证了两个性质（测验 Q13 引用）：
  - **保范数**：旋转前后向量长度都是 5.993526；
  - **相对位置性**：q 在 (3,5,7)、k 在 (1,2,2) 的点积，与 q 在 (13,8,9)、k 在 (11,5,4) 的点积完全相同（都是 −0.900823），因为两组的位置差都是 (2,3,5)。这正是 RoPE 能编码相对位置的原因。
- ⚠️ 这个函数是全文件最接近"M-RoPE 本体"的代码，但 `main()` 从未调用它。

### 3.3 `demo_mrope`：四个示例位置

```python
    positions = [
        ("text token i=0",      0, 0, 0),
        ("text token i=12",     12, 0, 0),
        ("image patch (h=5, w=7)", 0, 5, 7),
        ("video frame t=3 (h=5, w=7)", 3, 5, 7),
    ]
    for name, t, h, w in positions:
        angles = mrope_angles(cfg, t, h, w)
        first_pair = [round(a[0], 4) for a in angles]
```

- `first_pair` 用列表推导式取每个 band 的第 0 个角度。
- 讲义："Text tokens use `t = text_index, h = 0, w = 0` (or a normalized choice)... Single images use `t = 0`." 代码照此实现。
- ⚠️ **文本 token 的 h = w = 0 是一种简化**：这样所有文本 token 的后两个 band（2/3 的维度）都不旋转，只有时间 band 编码文本顺序（已验证：`mrope_rotate(cfg, q, 5, 0, 0)` 的后 32 维与输入完全相同）。Qwen2-VL 论文的做法是文本 token 的三个分量取相同 ID，使 M-RoPE 在纯文本上等价于 1D RoPE，从而无缝继承语言模型。
- ⚠️ **没有模态间的位置偏移**：图像 patch 的 t = 0 与第一个文本 token 重合。真实的打包序列中，每种模态的位置要接在前一模态的最大位置之后。讲义 "Use It" 说代码实现了 "M-RoPE position computation for a packed sequence"，实际并没有打包。参考实现见测验 Q10。

### 3.4 `VideoPlan`：动态 FPS 采样器

```python
@dataclass
class VideoPlan:
    duration_s: float
    tokens_per_frame: int
    budget: int
    motion: str

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

- 第 1 步就是讲义的公式 `fps_max = B / (T × tokens_per_frame)`：预算能负担的最大帧率。
- 第 2 步按运动强度选候选列表（从高到低），返回第一个 ≤ `fps_max` 的值。运动强度决定"上限从哪里开始"：高运动最高 8 FPS，低运动最高 1 FPS。讲义说候选是 `{1, 2, 4, 8}`，代码扩展了 0.5、0.25、0.1 以支持长视频。
- ⚠️ **兜底超预算**：所有候选都大于 `fps_max` 时，`return candidates[-1]` 不再检查预算。2 小时低运动视频：`fps_max ≈ 0.056`，返回 0.1，720 帧 × 81 = 58320 tokens，比 32768 多 78%（已运行验证）。
- `tokens_per_frame=81` 来自 demo 的设定（"after 3x pool"，即第 08 节 OneVision 的 384 分辨率 3 倍池化）。按 Qwen2-VL 的"每 28 像素一个 token"换算，81 个 token 相当于约 252×252 的帧。

```python
    def frame_times(self) -> list[float]:
        f = self.fps()
        n_frames = max(1, int(self.duration_s * f))
        step = 1.0 / f
        return [round(i * step, 3) for i in range(n_frames)]

    def total_tokens(self) -> int:
        return len(self.frame_times()) * self.tokens_per_frame
```

- 均匀采样：第 i 帧的时间是 `i / fps` 秒，`round(..., 3)` 保留到毫秒。这些时间戳就是讲义中要插入的 `<time>t</time>` 的值。
- `int(...)` 向下取整：2.5 秒视频按 1 FPS 只采 0 秒和 1 秒两帧，最后 0.5 秒没被看到。`max(1, ...)` 保证至少 1 帧。
- ⚠️ `total_tokens()` 只算帧 token，**没有计入时间标记**，也没有为 prompt 和输出留余量（skill 文件要求 "leave 20% slack"）。
- ⚠️ 每次调用 `total_tokens()` 都会重新调用 `frame_times()` 和 `fps()`，重复计算（对玩具代码无妨）。

### 3.5 `parse_tool_call`：带容错的 JSON 解析

```python
def parse_tool_call(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {"tool": "PARSE_ERROR", "raw": raw}
```

- 第一层：整串直接解析，适用于模型严格只输出 JSON 的情况。
- 第二层：`find` 找第一个 `{`，`rfind` 找最后一个 `}`，截取中间部分再解析——能处理 "Sure, clicking at {...} now." 这种前后带闲聊文字的输出，也能处理 Markdown 代码块包裹的 JSON。
- 都失败时返回一个带 `PARSE_ERROR` 标记的字典，而不是抛异常，调用方可以统一按字典处理。
- ⚠️ **返回类型不受控**：合法但不是对象的 JSON 会原样返回，`'[1,2]'` → `[1, 2]`、`'null'` → `None`，违背 `-> dict` 注解。
- ⚠️ **多个对象会失败**：`'click {"tool":"a"} then {"tool":"b"}'` 截出的是 `{"tool":"a"} then {"tool":"b"}`，不是合法 JSON → `PARSE_ERROR`。
- ⚠️ **没有 schema 校验**：不检查 `tool` 是否存在、`coords` 是否为两个数字。改进版（基于 `json.JSONDecoder.raw_decode` 逐个提取对象并校验）见测验 Q12。

### 3.6 演进摘要

```python
    print("  Qwen-VL   (2023) : 448 res, grounding, Q-Former")
    print("  Qwen2-VL  (2024) : M-RoPE, native res, MLP projector")
    print("  Qwen2.5-VL(2025) : dynamic FPS, abs-time tokens, JSON agent mode")
    print("  Qwen3-VL  (2025) : Qwen3 base, thinking mode, OCR scale")
```

- 与讲义四个小节一一对应。讲义的总结是："by 2025 the Qwen-VL architecture had stabilized. Additional generations scale compute and data, not primitives."
- 讲义中有几处需要谨慎看待的表述：Qwen2.5-VL 一节写 "At 0:04, the cat jumps" 对应 `<time>0.04</time>`，前者是第 4 秒、后者字面是 0.04 秒，两者不一致；"abs-time tokens" 的具体实现形式（插入文字时间戳还是把 M-RoPE 时间分量对齐到真实时间）应以 Qwen2.5-VL 技术报告原文为准。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 列表实现 RoPE | 每一对维度的旋转都看得见 | 极慢；生产中对整个张量做向量化的 cos/sin 乘法，并缓存频率表 |
| 每个 band 独立计算频率 | 三个轴对称、实现简单 | 与预训练 LLM 的 1D RoPE 频率表不一致；真实实现通常先算整张频率表再按段分配给 t/h/w |
| 文本 token 用 (i, 0, 0) | 直观地说明"文本只有时间轴" | 2/3 维度不编码文本顺序；Qwen2-VL 用 (i, i, i) 让纯文本退化为 1D RoPE |
| 候选 FPS 列表 + 首个可行值 | 规则清晰、可解释 | 兜底分支超预算；未计入时间标记和 prompt 余量；真实系统还会结合场景检测、关键帧 |
| 运动强度由调用方给出 | 省去光流计算 | 生产中可用帧差 / 光流估计运动强度，或让用户指定 |
| `find` / `rfind` 截取 JSON | 一行代码处理"前后带闲聊" | 无法处理多个对象、类型与 schema 不校验；生产中用 `raw_decode` 扫描 + schema 校验 + 受约束解码 |
| 失败时返回 `PARSE_ERROR` 字典 | 调用方无需 try/except | 容易被下游当作正常工具名处理；更好的做法是返回 `None` 或结构化的错误对象 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件顶部 | 让 `list[float]`、`list[list[float]]` 这类注解在旧版本 Python 上也能写 |
| `@dataclass` 默认值 | `base: float = 10000.0` | 有默认值的字段必须放在无默认值字段之后 |
| dataclass 中定义方法 | `VideoPlan.fps()`、`frame_times()`、`total_tokens()` | 数据和基于数据的计算放在一起；方法间通过 `self.fps()` 相互调用 |
| 泛型类型注解 | `-> list[float]`、`-> dict` | 说明返回类型；本文件 `mrope_angles` 的注解与实际返回（嵌套列表）不符 |
| 幂运算 `**` 与负指数 | `cfg.base ** (-2 * i / dim)` | 浮点幂运算，结果是 0–1 之间的频率 |
| `math.cos` / `math.sin` | `c, s = math.cos(angle), math.sin(angle)` | 标准库三角函数，参数为弧度 |
| 同时赋值（元组解包） | `v0, v1 = out[idx0], out[idx1]` | 右边先全部求值再赋值，常用于"先保存旧值" |
| `list(vec)` 浅拷贝 | `out = list(vec)` | 复制一份列表，修改 `out` 不影响调用方的 `vec` |
| 列表推导式 | `[round(a[0], 4) for a in angles]`、`[round(i * step, 3) for i in range(n_frames)]` | 一行生成列表 |
| `round(x, n)` | `round(i * step, 3)` | 四舍五入到 n 位小数（银行家舍入规则） |
| `max(1, ...)` 下限保护 | `max(1, int(self.duration_s * f))` | 保证至少为 1 |
| `try / except` 嵌套 | `parse_tool_call` 中两层 `try` | 捕获指定异常类型 `json.JSONDecodeError`；`pass` 表示什么都不做继续往下 |
| `str.find` / `str.rfind` | `raw.find("{")`、`raw.rfind("}")` | 返回子串第一次 / 最后一次出现的下标，找不到返回 −1 |
| 切片 | `raw[start:end + 1]` | 包含 `start`，不包含 `end + 1`，所以要 +1 才能包含右花括号 |
| `json.loads` | `json.loads(raw)` | 把 JSON 字符串解析成 Python 对象（dict / list / int / None …） |
| f-string 格式 | `{name:<30}`、`{n_frames:>4}`、`{plan.total_tokens():>6}` | 花括号里可以直接调用方法 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不执行 demo |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（输出确定）：

```text
M-RoPE position rotations for hidden=48 (16 per band)
  text token i=0                 first-pair angles (t, h, w) = [0.0, 0.0, 0.0]
  text token i=12                first-pair angles (t, h, w) = [12.0, 0.0, 0.0]   ← h、w 恒为 0
  image patch (h=5, w=7)         first-pair angles (t, h, w) = [0.0, 5.0, 7.0]    ← 图像 t=0
  video frame t=3 (h=5, w=7)     first-pair angles (t, h, w) = [3.0, 5.0, 7.0]

DYNAMIC-FPS SAMPLER (tokens_per_frame=81 after 3x pool)
budget 32768 tokens per video:
  30s tennis rally (high motion)          fps=8  frames= 240  tokens= 19440   ← fps_max≈13.5
  30s recipe demo (medium motion)         fps=4  frames= 120  tokens=  9720   ← 中等运动上限 4
  10min security loop (low motion)        fps=0.5  frames= 300  tokens= 24300 ← fps_max≈0.674
  1min UI agent replay (medium)           fps=4  frames= 240  tokens= 19440   ← fps_max≈6.7

QWEN2.5-VL TOOL-CALL PARSER
  raw    : {"tool": "mouse_click", "coords": [1024, 512], "button": "left"}
  parsed : {'tool': 'mouse_click', 'coords': [1024, 512], 'button': 'left'}   ← 第一层直接成功
  raw    : Sure, clicking at {"tool": "mouse_click", "coords": [800, 400]} now.
  parsed : {'tool': 'mouse_click', 'coords': [800, 400]}                      ← 第二层截取成功
  raw    : {"tool": "type_text", "text": "hello"
  parsed : {'tool': 'PARSE_ERROR', 'raw': '{"tool": "type_text", "text": "hello"'}  ← 缺右括号
  raw    : {"tool": "scroll", "direction": "down", "amount": 300}
  parsed : {'tool': 'scroll', 'direction': 'down', 'amount': 300}
```

逐项解读：

- **M-RoPE**：第一对的频率为 1，所以角度等于位置，直接看出各 token 的 (t, h, w)。i=0 的文本 token 与图像 patch 的 t 都是 0——说明这里没有做模态间的位置偏移。
- **采样器**：
  - 网球 8 FPS、240 帧：19440 tokens，恰好等于讲义举例的"60 秒 × 4 FPS × 81 = 19440"——同样的 token 数可以换成"更短、更密"或"更长、更稀"。
  - 菜谱只到 4 FPS，是因为中等运动的候选上限就是 4，而不是预算不够。
  - 10 分钟监控选 0.5 FPS：若按讲义练习 2 的 1 FPS，需要 48600 tokens，超出 32k。
  - 讲义说 "feel the difference when you swap fixed-FPS for dynamic-FPS on a 5-minute video"：额外测试发现，5 分钟视频在 32768 预算下 `fps_max ≈ 1.35`，高运动和中等运动都只能选 1 FPS（300 帧、24300 tokens）——长视频时预算而非运动强度才是瓶颈。
- **解析器**：四条中三条成功；第三条是被截断的输出（常见于 `max_tokens` 不够），正确的处理是重试或请求模型续写，而不是猜测补全。

---

## 7. 动手改一改

1. **讲义练习 1**：把 `demo_mrope` 改为打印 (t=3, h=5, w=7) 每个 band 的前三对角度；再实现"按 hidden=48 统一计算频率后切分"的版本，对比两组数值（参考测验 Q9）。
2. **调用 `mrope_rotate`**：随机生成 q、k，验证旋转保范数，以及"位置整体平移后 q·k 不变"的相对性质。
3. **打包序列的位置**：实现 `pack_positions`，文本三分量取相同 ID，每种模态从前一模态最大 ID + 1 开始；对"文本 + 图像 + 文本 + 视频"的序列打印全部 (t, h, w)（参考测验 Q10）。
4. **修复采样器**：兜底时抛 `ValueError`（或自动加大池化）；`total_tokens` 计入每帧的时间标记；预算只用 80%（参考测验 Q11）。
5. **讲义练习 5**：把 `parse_tool_call` 升级为 `parse_tool_calls`，能提取多个对象、只接受 dict、校验 `tool` 与 `coords`，并为截断输出返回"需要重试"的状态（参考测验 Q12）。
6. **进阶**：写一个 `tokens_for_image(H, W, min_pixels, max_pixels)`，模拟 Qwen2-VL 风格的"缩放到 28 的倍数、限定总像素数"的流程，算出 1120×672、4000×3000 等图像的视觉 token 数。

---

## 8. 常见坑

- **忘记 2×2 合并**：Qwen2-VL 每个视觉 token 对应 28×28 像素，不是 14×14，按 14 算会高估 4 倍。
- **把 M-RoPE 当成位置表**：M-RoPE 没有可学习的位置 embedding，这正是它能处理任意分辨率的原因。
- **文本位置的设计**：文本 token 若只在时间轴上编码，会削弱从 LLM 继承来的位置能力；三分量取相同 ID 才与 1D RoPE 等价。
- **模态之间不做位置偏移**：图像 patch 与文本 token 的位置重叠，模型无法区分先后。
- **兜底分支不检查约束**：采样器在超长视频上悄悄超预算。
- **只算视觉 token**：时间标记、文本 prompt 和输出也要占上下文。
- **"帧号"与"秒数"混淆**：动态 FPS 下二者不再一一对应；讲义里 "0:04" 与 `0.04` 也容易混淆。
- **JSON 解析只做"截取花括号"**：多个对象、非对象 JSON、截断输出都会出问题，务必做类型与 schema 校验。
