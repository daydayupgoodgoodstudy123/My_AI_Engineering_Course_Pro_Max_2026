# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 12 节 Emu3：通过下一 Token 预测生成图像与视频 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`），无需 GPU、无需网络

---

## 1. 这份代码在考察什么

Emu3 的论点是"更好的 tokenizer + 规模 + 单一 next-token 损失"就能做扩散级的图像生成。这份 140 行的脚本不训练任何模型，而是把这个论点里**两个可以算清楚的部分**做成玩具：

1. **成本账**：图像/视频被 tokenizer 压成多少个离散 token，按固定解码速度（30 tok/s）要生成多久——对应讲义"Compute cost"一节的"约 2 分钟/张"。
2. **Classifier-free guidance（CFG）**：条件 logits 与无条件 logits 按 `u + γ(c − u)` 混合，再加 temperature 采样——对应讲义"Classifier-free guidance and temperature"一节。

它还在结尾打印一张 Emu3 vs SDXL 的定性对比表。

> 一句话：**用算术说明"自回归生成图像为什么质量可行但很慢"，用 5 个数的小例子说明 CFG 如何把分布推尖**。同时要看清它的实验设计在哪些地方不严谨。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `random.seed(0)` | 模块级语句 | 固定随机种子，保证输出可复现 | 可复现性 |
| `TokCost` | `@dataclass` | 描述一个图像/视频配置，`tokens()` 计算 token 数 | 2D / 3D VQ 压缩 |
| `token_table` | 函数 | 打印 7 种配置的 token 数与 30 tok/s 下的延迟 | 推理成本 |
| `softmax` | 函数 | 带 temperature、减最大值的数值稳定 softmax | 采样分布 |
| `cfg_mix` | 函数 | `u + γ(c − u)` 逐元素混合 logits | CFG |
| `sample` | 函数 | 逆 CDF 法按概率抽一个下标 | 类别采样 |
| `demo_cfg` | 函数 | 固定的 5 维 logits，展示 γ = 0/1/3/5/7 的效果 | CFG 锐化 |
| `sample_tokens` | 函数 | 对每一步做 CFG + temperature + 采样 | "自回归"采样（简化） |
| `demo_sampling` | 函数 | K=16、8 步随机 logits，对比三组 γ/T | CFG 对采样结果的影响 |
| `main` | 函数 | 依次调用上述 demo 并打印 Emu3 vs SDXL 表 | — |

数据流：`random.seed(0)` → `token_table()`（纯算术）→ `demo_cfg()`（固定 logits → `cfg_mix` → `softmax`）→ `demo_sampling()`（随机 logits → `sample_tokens` → `sample`）→ 打印定性对比。

---

## 3. 逐段精讲

### 3.1 `TokCost`：图像和视频的 token 数

```python
@dataclass
class TokCost:
    label: str
    resolution: int
    reduction: int
    video_seconds: float = 0.0
    fps: float = 0.0
    time_reduction: int = 1

    def tokens(self) -> int:
        spatial_per_frame = (self.resolution // self.reduction) ** 2
        if self.video_seconds == 0:
            return spatial_per_frame
        frames = int(self.video_seconds * self.fps)
        frames_reduced = max(1, frames // self.time_reduction)
        return spatial_per_frame * frames_reduced
```

- **图像**：`(resolution / reduction)²`。512、8 → `64² = 4,096`，即讲义"A 512x512 image becomes 64x64 = 4096 tokens"。
- **视频**：再乘以压缩后的帧数。4 s × 8 FPS = 32 帧，时间压缩 4 → 8 个时间片；空间 `256 / 4 = 64` → `64² × 8 = 32,768`，与讲义的算式 `(256/4) * (256/4) * (32/4)` 完全一致。
- 用 `video_seconds == 0` 区分图像和视频：图像就是"只有一帧、不做时间压缩"的特例。这正是 3D VQ 的思想——图像和视频共用一套"空间 × 时间"的计数公式。
- `max(1, ...)`：不足一个时间片的极短视频也至少算 1 片。
- ⚠️ `//` 是**向下取整**：分辨率不能被 `reduction` 整除时（如 500 / 8 = 62.5）会静默截断成 62，真实 tokenizer 通常要求先 resize/pad 到整数倍。
- ⚠️ 只支持正方形图像；长宽不同需要拆成 `h // r * w // r`。
- ⚠️ 讲义（以及这里的视频配置）用的是 4×4×4 时空压缩；Emu3 论文描述的是时间 4×、空间 8×8，按论文口径同一片段只有 8,192 个 token。代码忠实于讲义，但讲义口径值得核对。

### 3.2 `token_table`：延迟就是 token 数除以速度

```python
    print(f"{'config':<32}{'tokens':>12}{'seconds @30tps':>18}")
    for c in configs:
        t = c.tokens()
        latency = t / 30.0
        print(f"  {c.label:<30}{t:>12}{latency:>16.1f}s")
```

- 自回归解码一次只出一个 token，延迟 ≈ `token 数 / 每秒 token 数`。512×512 → 136.5 s ≈ 2.3 分钟，对应讲义"~2 minutes per 512x512 image"。
- 分辨率翻倍，token 数 ×4，延迟 ×4（1024 → 546 s，2048 → 2,184 s）。
- ⚠️ **简化 1**：没算 CFG。讲义说 Emu3 推理要"generate twice"，每个 token 两次前向；串行时延迟要 ×2。
- ⚠️ **简化 2**：把 30 tok/s 当常数。序列越长，每步注意力要看的 KV cache 越大，后期 token 会越来越慢；整段的注意力计算量约与 `L²` 成正比（2048 相对 512 约 256 倍）。
- 表头 `'config':<32` 与数据行 `"  " + label:<30` 合起来正好 32 列，是对齐的小技巧。

### 3.3 `softmax`：带 temperature 的数值稳定版本

```python
def softmax(xs: list[float], temperature: float = 1.0) -> list[float]:
    m = max(xs)
    exps = [math.exp((x - m) / temperature) for x in xs]
    z = sum(exps)
    return [e / z for e in exps]
```

- 先减最大值 `m` 再取 `exp`，最大项变成 `exp(0) = 1`，不会溢出；`(x − m) / T` 与 `x / T − m / T` 相差一个常数，softmax 结果不变。
- `temperature < 1` 放大差值 → 分布更尖；`> 1` → 更平。讲义推荐：感知 1.0，图像生成 0.8。
- ⚠️ `temperature = 0` 会 `ZeroDivisionError`；贪心解码需要单独分支（直接取 argmax）。

### 3.4 `cfg_mix`：CFG 的全部数学就这一行

```python
def cfg_mix(cond_logits: list[float], uncond_logits: list[float],
            gamma: float) -> list[float]:
    """Classifier-free guidance: mixed = uncond + gamma * (cond - uncond)."""
    return [u + gamma * (c - u) for c, u in zip(cond_logits, uncond_logits)]
```

- `c` 是带完整 caption 前向得到的 logits，`u` 是带空 caption 的 logits。`c − u` 表示"prompt 让每个 token 的分数提高了多少"。
- γ = 0 → `u`（无条件）；γ = 1 → `c`（普通条件生成）；γ > 1 → 沿 `c − u` 方向外推。
- 等价写法 `γc + (1 − γ)u`：γ > 1 时 `u` 的系数为负，相当于"减去无条件分布"，这也是"负向 prompt"技巧的来源（把空 caption 换成负向描述）。
- γ → ∞ 时 softmax 收敛到 `argmax(c − u)`，**不一定是**条件分布的众数 `argmax(c)`。反例 `c=[3.0, 2.8]`、`u=[2.5, 0.0]`：γ=1 概率 `[0.55, 0.45]`，γ=3 变成 `[0.012, 0.988]`，排序翻转（见测验 Q9）。

### 3.5 `sample`：逆 CDF 采样

```python
def sample(probs: list[float]) -> int:
    r = random.random()
    acc = 0
    for i, p in enumerate(probs):
        acc += p
        if r <= acc:
            return i
    return len(probs) - 1
```

- 在 `[0, 1)` 上抽一个均匀随机数 `r`，沿累计概率走，第一个使 `acc ≥ r` 的下标被选中——每个下标被选中的概率恰好是 `p_i`。
- 最后的 `return len(probs) - 1` 是**浮点兜底**：概率和可能是 0.9999999，`r` 恰好比它大时循环会走完。
- 等价的标准库写法是 `random.choices(range(len(probs)), weights=probs)[0]`。

### 3.6 `demo_cfg`：固定 logits 看 γ 的效果

```python
    cond = [2.0, 4.0, 1.0, 3.5, 0.5]
    uncond = [1.0, 2.0, 1.5, 1.8, 1.2]
    for gamma in [0.0, 1.0, 3.0, 5.0, 7.0]:
        mixed = cfg_mix(cond, uncond, gamma)
        probs = softmax(mixed)
```

- `c − u = [1.0, 2.0, −0.5, 1.7, −0.7]`。γ 每加 1，token 1 的 logit 就加 2.0、token 3 加 1.7，二者差距每次扩大 0.3，所以 token 1 的概率从 0.549（γ=1）一路涨到 0.909（γ=7）。
- token 2 和 token 4 的 `c − u` 为负，γ 越大越被压低，γ ≥ 3 时概率显示为 0.0。
- 这里 `softmax(mixed)` 用的是默认 T = 1；与 `sample_tokens` 的 T = 0.8 不同，读结果时别混淆。
- ⚠️ 打印的 "Emu3 recommends gamma = 3.0 for image gen, 7.0 for strong adherence" 是代码作者的说法，讲义只说"typical 3.0-7.0"，没有给出这样的出处。

### 3.7 `sample_tokens` 与 `demo_sampling`：玩具"自回归"采样

```python
def sample_tokens(cond, uncond, gamma=3.0, temp=0.8):
    out = []
    for c, u in zip(cond, uncond):
        mixed = cfg_mix(c, u, gamma)
        probs = softmax(mixed, temperature=temp)
        out.append(sample(probs))
    return out
```

```python
    cond = [[random.gauss(0, 2) for _ in range(K)] for _ in range(steps)]
    uncond = [[random.gauss(0, 1) for _ in range(K)] for _ in range(steps)]
    tokens_no_cfg = sample_tokens(cond, uncond, gamma=1.0, temp=1.0)
    tokens_cfg3 = sample_tokens(cond, uncond, gamma=3.0, temp=0.8)
    tokens_cfg7 = sample_tokens(cond, uncond, gamma=7.0, temp=0.8)
```

- `cond` 是 8 × 16 的嵌套列表：8 步，每步 16 个 codebook 条目的 logits；条件 logits 标准差 2、无条件标准差 1，模拟"有 prompt 时更有主见"。
- 默认参数 `gamma=3.0, temp=0.8` 与讲义的推荐值一致。
- ⚠️ **不是真正的自回归**：每步 logits 事先生成且互相独立，不依赖已采到的 token。真实 Emu3 每采一个 token 都要追加到两条序列（有/无 caption）上，再前向得到下一步的 `c`、`u`。
- ⚠️ **混杂变量**："no CFG" 组 γ=1、T=1，CFG 组 T=0.8——γ 和 T 同时变了；而且三次调用依次消耗全局随机流，每组的 `r` 都不同。应固定 T、用同一个种子做对比（测验 Q10 给出了改法）。

### 3.8 `main` 与结尾对比表

- 依次调用三个 demo，最后打印 Emu3 vs SDXL 的定性结论：训练成本可比、推理 Emu3 慢、质量持平或略好、Emu3 还能做理解和视频。
- "~300M image-steps" 没有在讲义中出现、代码也没解释，只能当作一个量级示意。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯标准库、无模型 | 聚焦"token 数"和"CFG 数学"两个可算清楚的点 | 看不到真实 tokenizer 与 Transformer；真实系统用 PyTorch + VQ 解码器 |
| `TokCost` 一个公式覆盖图像与视频 | 体现 3D VQ"图像是单帧视频"的统一视角 | 只支持正方形、整除；生产 tokenizer 需处理任意长宽比和 padding |
| 延迟 = token / 30 | 一眼看出量级（分钟级） | 忽略 CFG 翻倍、KV cache 增长、批处理；真实估算要 profile |
| CFG 在 logits 上线性混合 | 与 Emu3 / 扩散的做法一致，一行代码 | 每 token 两次前向、两份 KV cache；生产中把两路拼成 batch=2 |
| 随机 logits 模拟"采样" | 不需要模型就能演示 γ 的作用 | 不是自回归；对比实验混杂了 γ、T 和随机数 |
| 全局 `random.seed(0)` | 输出可复现 | 各 demo 共享一个随机流，改动前面的代码会影响后面的结果；更好的做法是每个 demo 用独立的 `random.Random(seed)` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值；在旧版本 Python 上也能写 `list[float]` |
| `@dataclass` | `class TokCost:` | 自动生成 `__init__`、`__repr__` 等；字段按顺序成为构造参数 |
| 字段默认值 | `video_seconds: float = 0.0` | 有默认值的字段必须排在无默认值字段之后 |
| 位置参数构造 dataclass | `TokCost("video 4s @8fps 256x256", 256, 4, 4.0, 8, 4)` | 按字段声明顺序传参；可读性差时建议改用关键字参数 |
| 类型注解 | `def softmax(xs: list[float], temperature: float = 1.0) -> list[float]` | 说明参数与返回值类型，不做运行时检查 |
| `//` 与 `**` | `(self.resolution // self.reduction) ** 2` | 整除（向下取整）与乘方 |
| 列表推导式 | `[math.exp((x - m) / temperature) for x in xs]` | 一行构造新列表 |
| 嵌套推导式 | `[[random.gauss(0, 2) for _ in range(K)] for _ in range(steps)]` | 生成 `steps × K` 的二维列表；`_` 表示不使用的循环变量 |
| `zip` | `for c, u in zip(cond_logits, uncond_logits)` | 并行遍历两个序列，长度不等时以短的为准 |
| `enumerate` | `for i, p in enumerate(probs)` | 同时拿到下标和值 |
| `list.index(max(...))` | `probs.index(max(probs))` | 找最大值的下标（argmax）；有并列时返回第一个 |
| `round` 嵌在推导式中 | `[round(x,2) for x in mixed]` | 打印前保留小数位 |
| f-string 对齐与格式 | `{c.label:<30}`、`{t:>12}`、`{latency:>16.1f}`、`{gamma:>4.1f}` | 左对齐 / 右对齐 / 宽度 + 小数位 |
| f-string 中嵌套引号 | `f"{'config':<32}"` | 花括号里可以放字符串字面量再格式化 |
| 字符串乘法 | `"-" * 60`、`"=" * 60` | 重复字符串，画分隔线 |
| 相邻字符串自动拼接 | `"higher gamma ...;" " same pattern at scale."` | 两个字面量相邻会在编译期合并 |
| `random.random` / `random.gauss` | `r = random.random()` | `[0,1)` 均匀分布 / 正态分布 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，`python3 main.py`，瞬间完成）：

```text
EMU3 TOKEN COUNTS (at recommended tokenizer reductions)
config                                tokens    seconds @30tps
  image 256x256                         1024            34.1s
  image 512x512                         4096           136.5s   ← 讲义 "~2 minutes"
  image 1024x1024                      16384           546.1s   ← 练习 1：×4
  image 2048x2048                      65536          2184.5s   ← 再 ×4，约 36 分钟
  video 4s @8fps 256x256               32768          1092.3s   ← 讲义的 32,768
  video 10s @8fps 256x256              81920          2730.7s   ← 时长 ×2.5，token ×2.5
  video 4s @8fps 512x512              131072          4369.1s   ← 分辨率 ×2，token ×4

CLASSIFIER-FREE GUIDANCE — effect on logit shape
  gamma= 0.0  logits=[1.0, 2.0, 1.5, 1.8, 1.2]       ← 等于 uncond
            probs =[0.113, 0.308, 0.187, 0.253, 0.139]  top=1
  gamma= 1.0  logits=[2.0, 4.0, 1.0, 3.5, 0.5]       ← 等于 cond
            probs =[0.074, 0.549, 0.027, 0.333, 0.017]  top=1
  gamma= 3.0  logits=[4.0, 8.0, 0.0, 6.9, -0.9]
            probs =[0.014, 0.74, 0.0, 0.246, 0.0]  top=1
  gamma= 5.0  logits=[6.0, 12.0, -1.0, 10.3, -2.3]
            probs =[0.002, 0.844, 0.0, 0.154, 0.0]  top=1
  gamma= 7.0  logits=[8.0, 16.0, -2.0, 13.7, -3.7]
            probs =[0.0, 0.909, 0.0, 0.091, 0.0]  top=1

AUTOREGRESSIVE IMAGE-TOKEN SAMPLING (toy, K=16 codebook)
  no CFG      : [13, 12, 13, 1, 14, 14, 7, 11]
  CFG gamma=3 : [13, 0, 1, 1, 14, 14, 7, 11]
  CFG gamma=7 : [13, 0, 1, 1, 14, 14, 7, 11]
```

逐项解读：

- **token 表**：图像 token 数随边长平方增长，视频再乘时间片数。最后一行 4 秒 512×512 视频已经 13 万 token、按 30 tok/s 要 73 分钟——这就是 outputs 技能文件说"别拿 Emu3 做 4K 图像"的原因。
- **γ = 0 / 1 两行**：logits 分别精确等于 `uncond` 和 `cond`，验证了公式的两个端点。
- **γ 增大**：top 一直是 token 1，但概率从 0.549 → 0.74 → 0.844 → 0.909，分布越来越尖；负向 token（2、4）被压到 0。注意此处 T = 1。
- **采样序列**：经逐步检查，γ=1、T=1 时第 2、3 步的最大概率只有 0.486 和 0.339，所以采到了非众数 12、13；γ=3、T=0.8 时 8 步中 6 步的最大概率 ≥ 0.83，结果正好等于每步 `argmax(c)` 也等于 `argmax(c − u)`：`[13, 0, 1, 1, 14, 14, 7, 11]`。γ=3 与 γ=7 完全相同，并不是"γ 越大越好"的证据，只是分布都已经很尖。
- **结论的边界**：这组对比同时变了 γ 和 T、且随机数不同，只能作为直观演示，不能作为"CFG 让结果更准"的定量证据。

---

## 7. 动手改一改

1. **（练习 1）** 在 `configs` 中加入 768×768、1536×1536，以及"按 Emu3 论文口径"的视频配置（空间 8、时间 4），对比 token 数。
2. **加入 CFG 成本**：给 `TokCost` 增加 `cfg_passes: int = 2`，延迟改为 `t * cfg_passes / 30`，再加一列"batch=2 时的估计延迟"，说明两者差异来自 decode 的显存带宽瓶颈。
3. **（练习 3）** 在 `demo_cfg` 中同时打印 T = 0.8 的概率，观察 γ 与 T 叠加的效果；再用 `c=[3.0, 2.8]`、`u=[2.5, 0.0]` 复现"排序翻转"，并修正结尾的注释。
4. **修正对比实验**：让 `sample` 接收一个 `rng` 参数，三组都用 `random.Random(123)`，固定 T = 0.8，只改 γ（参考测验 Q10）。
5. **做成真正的自回归**：写一个 `toy_model(seq) -> logits` 的小函数（例如让 logits 依赖上一个 token 的二元转移表），条件分支额外加上一个"prompt 偏置"向量，再用 CFG 逐步采样，观察 γ 如何改变整条序列。
6. **进阶（练习 4）**：写一个 `train_flops(N, D)` 与 `gpu_hours(flops, peak, mfu)`，计算 7B × 300B token，与讲义中 "2k-4k GPU-years" 对比（答案约 3 GPU-years，见测验 Q12）。

---

## 8. 常见坑

- **把 codebook 大小当成 token 数**：32,768 是每个 token 的取值范围，4,096 才是一张 512×512 图的 token 数。
- **以为 γ = 1 是"开了 CFG"**：γ = 1 就是普通条件生成，引导效果从 γ > 1 才开始。
- **以为大 γ 收敛到条件众数**：实际收敛到 `argmax(c − u)`，可能翻转排序。
- **忽略 CFG 的成本**：每个 token 两次前向、两份 KV cache；延迟表必须把它算进去。
- **同时改两个超参再下结论**：γ 和 T 都会让分布变尖，对比实验要控制变量、共用随机数。
- **temperature 设为 0**：`softmax` 会除以 0 报错，贪心应单独走 argmax。
- **整除截断**：`resolution // reduction` 不整除时会悄悄少算 token。
- **相信中文讲义的机器翻译**：多处语义反转（如"在图像生成上比 SDXL 差"），以英文为准。
