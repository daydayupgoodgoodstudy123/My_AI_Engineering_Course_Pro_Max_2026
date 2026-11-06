# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 08 节 LLaVA-OneVision：统一处理单图、多图与视频 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数，预算写死为 4096） ｜ **依赖**：仅标准库（`dataclasses`、`__future__`）

---

## 1. 这份代码在考察什么

LLaVA-OneVision 的关键不在网络结构，而在两件"规划"层面的事：

1. **统一的视觉 token 预算**：单图、多图、视频三种输入形状差异巨大，但每个样本送进 LLM 的视觉 token 数要大致相同。代码用三个 `plan_*` 函数，在"tile 数 / 图片数 / 帧数"和"分辨率 / 池化倍数"之间搜索一个不超预算的配置。
2. **三阶段课程**：SI（单图）→ OV（混合）→ TT（目标任务），代码打印各阶段三类数据的混合权重。

此外它还把论文报告的三项涌现能力打印出来作为提醒。

对应讲义的核心概念：token 预算、AnyRes-k、bilinear 池化（patch 网格上的 2D 下采样）、课程顺序、涌现能力。

> 一句话：**用几行整数算术把"384 分辨率 → 27×27 patch → 池化 → 乘以张数/帧数"这条预算链条算清楚**。同时要注意它的搜索策略、兜底分支和讲义承诺的若干功能（FLOPs、under-tokenized 标记）并不完善。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Budget` | `@dataclass` | 保存三个场景的 token 数，提供 `max()` / `min()` | 预算平衡（**定义了但从未使用**） |
| `anyres_tokens(tiles, per_tile)` | 函数 | `(tiles + 1) × per_tile`，+1 是缩略图 | AnyRes-k |
| `per_tile_tokens(resolution, patch, pool)` | 函数 | `(resolution // patch // pool)²` | patch 网格与池化 |
| `plan_single_image(budget)` | 函数 | 在 tiles ∈ {9,4,1} × 三种(分辨率,池化) 中找第一个不超预算的方案 | 单图 AnyRes |
| `plan_multi_image(budget)` | 函数 | 在张数 ∈ {8,6,4,2} × 三种(分辨率,池化) 中找第一个可行方案 | 多图 |
| `plan_video(budget)` | 函数 | 在帧数 ∈ {32,16,8} × 三种(分辨率,池化) 中找第一个可行方案 | 视频 |
| `print_plan(plan, budget)` | 函数 | 打印一个方案及预算利用率 | — |
| `curriculum_stages(mix)` | 函数 | 打印三阶段数据权重，TT 阶段使用传入的产品分布 | 三阶段课程 |
| `main()` | 函数 | 预算 4096 → 三个 plan → 计算 spread → 打印课程与涌现能力 | 入口 |

数据流：`main()` 设定 `budget = 4096` → `plan_single_image` / `plan_multi_image` / `plan_video`（内部调用 `per_tile_tokens`、`anyres_tokens`）→ `print_plan` ×3 → 计算三个 `total` 的极差 spread → `curriculum_stages(mix)` → 打印涌现能力。注意 `mix` **只影响 TT 阶段的打印**，不影响 token 分配。

---

## 3. 逐段精讲

### 3.1 两个算术函数：预算链条的核心

```python
def anyres_tokens(tiles: int, per_tile: int) -> int:
    return (tiles + 1) * per_tile


def per_tile_tokens(resolution: int, patch: int, pool: int) -> int:
    g = resolution // patch
    pooled = g // pool
    return pooled * pooled
```

- `per_tile_tokens(384, 14, 1)`：`384 // 14 = 27`（384/14 ≈ 27.43，SigLIP 类 encoder 的 384 输入对应 27×27 网格），27² = **729**。
- 2 倍池化：`27 // 2 = 13` → **169**；3 倍池化：`27 // 3 = 9` → **81**；336 分辨率：`336 // 14 = 24`，2 倍池化 12² = **144**。
- `anyres_tokens(9, 169) = 10 × 169 = 1690`：9 个子图加 1 张缩略图，缩略图使用与子图相同的 token 数。
- ⚠️ **取整方式影响很大**：27 是奇数，`//` 向下取整得 13×13 = 169；若按 `ceil(27/2) = 14` 得 196（讲义"问题"一节的"~196 tokens per frame"）；讲义"概念"一节的 182 是 `729 / 4` 的近似，不对应任何整数网格。实际的 bilinear 插值可以把 27×27 缩放到任意目标尺寸，取整方式由实现决定，做预算时必须写清楚。

### 3.2 三个 `plan_*` 函数：首个可行解搜索

```python
def plan_single_image(budget: int) -> dict:
    for tiles in [9, 4, 1]:
        for per_tile_size in [(384, 14, 2), (384, 14, 1), (336, 14, 2)]:
            res, patch, pool = per_tile_size
            per = per_tile_tokens(res, patch, pool)
            total = anyres_tokens(tiles, per)
            if total <= budget:
                return {
                    "scenario": "single-image",
                    "tiles": tiles,
                    "tile_res": res,
                    "pool": pool,
                    "per_tile": per,
                    "total": total,
                }
    return {"scenario": "single-image", "tiles": 1, "per_tile": 81, "total": 162}
```

- 外层循环从"最多 tile"开始，内层按 `(384, 2)` → `(384, 1)` → `(336, 2)` 的顺序尝试，**一旦 `total <= budget` 就 `return`**。
- 预算 4096 时第一个候选 `tiles=9, pool=2` 得 1690，直接返回。`plan_multi_image` 同理返回 `8 × 169 = 1352`，`plan_video` 返回 `32 × 81 = 2592`（第一个候选就是 `(384, 3)`）。
- ⚠️ **预算变大，方案不变**：因为强池化的候选排在前面，预算 3000、4096、8192 下得到的方案完全相同（已实际运行验证），多出的预算不会转化成更高的保真度。预算 4096 下单图其实可以选 `tiles=4, pool=1`，`5 × 729 = 3645`，也就是讲义写的 "AnyRes-4 at 729-per-tile = 2916 + 729"。改成"在可行解中取 total 最大"的写法见测验 Q9。
- ⚠️ **与讲义的多图方案不同**：讲义是"每张 729 个 token、不池化、6 张 = 4374"；代码选 8 张 × 169。讲义的 4374 本身也超过 4096。
- ⚠️ **兜底分支会超预算**：`plan_video(500)` 返回 `total=512`；预算 100 时三个兜底分别返回 162、162、512，全都超出。兜底字典还缺少 `tile_res` / `resolution`、`pool` 键，`per_frame=64` 也不在候选里（对应 `(336, 3)`：`24 // 3 = 8`，8² = 64）。这与 docstring "so the LLM never blows context" 矛盾。

```python
def plan_video(budget: int) -> dict:
    for n_frames in [32, 16, 8]:
        for res_pool in [(384, 3), (384, 2), (336, 2)]:
            res, pool = res_pool
            per = per_tile_tokens(res, 14, pool)
            total = n_frames * per
            ...
```

- 视频与单图的差别：没有 AnyRes 切块，`total = 帧数 × 每帧 token`；默认就从 3 倍池化开始，体现"视频要多帧、低分辨率"。
- 视频帧数优先级高于每帧质量：先尽量保 32 帧，再考虑减少池化。

### 3.3 `print_plan`：打印方案与利用率

```python
def print_plan(plan: dict, budget: int) -> None:
    pct = 100 * plan["total"] / budget
    print(f"\n{plan['scenario'].upper():<12} budget target {budget:>5}, used {plan['total']:>5}  ({pct:>5.1f}%)")
    for k, v in plan.items():
        if k in ("scenario", "total"):
            continue
        print(f"    {k:<12}: {v}")
```

- `plan.items()` 遍历字典的键值对，`continue` 跳过已在标题行打印过的两项。因为是"有什么键就打印什么"，所以兜底字典缺键时不会报错，只是信息不全。
- f-string 里 `plan['scenario']` 用单引号，因为外层已经用了双引号；`.upper()` 把场景名转成大写。
- ⚠️ 讲义 "Use It" 说代码会报告 "LLM FLOPs" 和 "which scenarios are under-tokenized"，docstring 也说 "expected FLOPs per sample"，但这里只打印利用率。skill 文件定义"低于目标 70% 为 under-tokenized"，默认运行的三个场景（41.3%、33.0%、63.3%）都应被标记。

### 3.4 `main()` 中的 spread 计算

```python
    spread = max(si["total"], mi["total"], vi["total"]) - min(si["total"], mi["total"], vi["total"])
    print(f"\nbudget spread across scenarios: {spread} tokens "
          f"({100*spread/budget:.1f}% of budget)")
    print("LLaVA-OneVision target: keep spread under 30% for predictable LLM cost.")
```

- spread（极差）= 最大场景 token 数 − 最小场景 token 数 = 2592 − 1352 = 1240，占 4096 的 30.3%。
- ⚠️ **目标未达成却没有警告**：30.3% > 30%，代码却紧接着打印"目标是 30% 以内"，没有任何判断。顶部定义的 `Budget` 类恰好提供了 `max()` / `min()` 方法，本可以在这里使用，但整个文件都没有用到它。
- 两个相邻的 f-string 在括号内自动拼接成一个字符串。

### 3.5 `curriculum_stages`：三阶段课程

```python
    stages = [
        ("Stage SI  ", 1.0, 0.0, 0.0, "single-image only, AnyRes high-res"),
        ("Stage OV  ", 0.5, 0.3, 0.2, "OneVision mix, unified budget"),
        ("Stage TT  ", mix["single"], mix["multi"], mix["video"],
         "target-task fine-tune"),
    ]
```

- SI 全部单图；OV 仍保留一半单图（防止遗忘感知能力），再加入多图和视频；TT 直接用产品分布（`main()` 传入的是 0.4 / 0.3 / 0.3）。
- 讲义强调阶段之间 "No weight reset"，代码只打印权重，不体现训练本身。
- ⚠️ 最后一行 "stages in reverse (video first) underperform by 2-4 MMMU per LLaVA-OneVision ablation"：讲义正文只说论文"explicitly"做了顺序消融，没有给出 "2-4 MMMU" 这个数字（该数字出现在代码和 skill 文件中）。引用时应注明出处不明。

### 3.6 涌现能力

- 直接 `print` 三项能力及其来源组合：多摄像头推理（多图 + 视频）、set-of-mark（空间定位 + 多图指代）、iPhone 截图 agent（UI 截图 + 用户操作视频 + 前后对比图）。这些都"不是训练任务"，而是课程组合的结果。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用整数算术估算 token 数 | 不需要真实 encoder 就能规划预算 | 取整方式要与实际实现（bilinear 插值目标尺寸）一致，否则差 10%+ |
| 首个可行解搜索 | 代码短，优先级由列表顺序表达 | 预算增大时不提升保真度；应在可行解中按利用率或场景偏好打分选最优 |
| 场景之间独立规划 | 逻辑简单 | 无法根据产品分布（`mix`）调整各场景配额；`mix` 只用于打印 |
| 兜底返回固定小方案 | 保证总有输出 | 可能超预算、缺键；应返回 `None` / 抛错，或按 skill 规则拒绝 |
| 只打印 spread 不判断 | 演示指标 | 应检查 `spread / budget <= 0.3` 并对低于 70% 的场景标记 under-tokenized |
| 课程权重写死 | 便于展示 SI → OV → TT | 生产中 OV 权重要按数据量和遗忘情况调参 |
| 固定预算（OneVision 路线） | 延迟和显存可预测 | 长视频信息密度下降；Qwen2.5-VL 采用预算随输入增长的方案（下一节） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件顶部 | 注解延迟求值；配合 `-> dict` 等返回类型注解 |
| `@dataclass` + 方法 | `class Budget: ... def max(self) -> int:` | dataclass 也可以定义普通方法；这里方法名 `max` / `min` 与内置函数同名，但作为方法不会冲突 |
| 内置 `max` / `min` 多参数 | `max(self.single_image_tokens, self.multi_image_tokens, self.video_tokens)` | 直接比较多个值取最大/最小 |
| 整除 `//` | `resolution // patch`、`g // pool` | 向下取整；`384 // 14 == 27`，`27 // 2 == 13` |
| 嵌套循环 + 提前 `return` | `for tiles in ...: for ...: if total <= budget: return {...}` | 找到第一个满足条件的组合就立即退出整个函数 |
| 元组解包 | `res, patch, pool = per_tile_size`、`for name, s, m, v, note in stages:` | 把元组拆成多个变量 |
| 字典字面量 | `{"scenario": "video", "n_frames": n_frames, ...}` | 用字典作为轻量的返回结构 |
| `dict.items()` + `continue` | `for k, v in plan.items(): if k in (...): continue` | 遍历键值对；`continue` 跳过本次循环 |
| `in` 判断成员 | `if k in ("scenario", "total")` | 判断元素是否在元组中 |
| 字符串方法 | `plan['scenario'].upper()` | 转大写 |
| f-string 格式符 | `{budget:>5}`、`{pct:>5.1f}`、`{k:<12}`、`{s:>8.2f}`、`{100*spread/budget:.1f}` | 宽度、对齐、小数位；花括号内可以写表达式 |
| 相邻字符串拼接 | `print(f"... {spread} tokens " f"({...}% of budget)")` | 括号内相邻字符串字面量自动拼接 |
| 列表中的多行元组 | `("Stage TT  ", mix["single"], ..., \n "target-task fine-tune")` | 括号内可以随意换行，不需要反斜杠 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（输出确定，无随机性）：

```text
shared per-sample visual token budget: 4096

SINGLE-IMAGE budget target  4096, used  1690  ( 41.3%)
    tiles       : 9
    tile_res    : 384
    pool        : 2
    per_tile    : 169            ← 27//2=13，13²=169；(9+1)×169=1690

MULTI-IMAGE  budget target  4096, used  1352  ( 33.0%)
    n_images    : 8
    resolution  : 384
    pool        : 2
    per_image   : 169            ← 8×169=1352；讲义方案是 6×729=4374

VIDEO        budget target  4096, used  2592  ( 63.3%)
    n_frames    : 32
    resolution  : 384
    pool        : 3
    per_frame   : 81             ← 27//3=9，9²=81；32×81=2592，与讲义一致

budget spread across scenarios: 1240 tokens (30.3% of budget)
LLaVA-OneVision target: keep spread under 30% for predictable LLM cost.   ← 30.3% 已超标，但没有警告

CURRICULUM SCHEDULE (three-stage)
stage         single   multi   video   notes
Stage SI        1.00    0.00    0.00   single-image only, AnyRes high-res
Stage OV        0.50    0.30    0.20   OneVision mix, unified budget
Stage TT        0.40    0.30    0.30   target-task fine-tune      ← 来自 main() 的 mix
...
```

逐项解读：

- **单图 1690**：与讲义的 1820 不同，差别全在每块 169 vs 182 的取整（见 3.1）。
- **多图 1352**：首个可行解搜索的结果，比讲义方案（每张 729）粗得多。8 张 × 169 能放进更多图，但每张图细节减少约 4 倍。
- **视频 2592**：与讲义完全一致。
- **利用率**：三个场景都远低于 4096，最高只有 63.3%。按 skill 文件的 ±30% 规则，三个场景都属于 under-tokenized。
- **spread 30.3%**：略超代码自己打印的 30% 目标。如果改为"取利用率最高的可行解"（单图 3645、多图 2916、视频 2704），spread 变为 941（23.0%），三个场景利用率分别为 89%、71%、66%，更接近"预算恒定"的初衷。
- **额外实验**：预算改为 2048 时视频降到 16 帧（1296）；改为 1024 时单图 4 tiles（845）、多图 6 张（1014）、视频 8 帧（648）；改为 8192 时与 4096 的结果完全相同。

---

## 7. 动手改一改

1. **最优可行解**：把三个 `plan_*` 改成"遍历所有候选、在 `total <= budget` 中取 `total` 最大者"，对比预算 4096 和 8192 下的结果（参考测验 Q9）。
2. **用上 `Budget` 类**：把三个方案的 `total` 装进 `Budget`，用它的 `max()` / `min()` 计算 spread，并在 `spread / budget > 0.3` 时打印警告；对利用率低于 70% 的场景打印 `UNDER-TOKENIZED`。
3. **修正兜底分支**：找不到可行解时返回 `None`，在 `main()` 中处理；预算低于 1024 时拒绝多图和视频（skill 拒绝规则）。
4. **加 FLOPs 估算**：给 `print_plan` 增加参数 `llm_params=7e9`，打印 `2 * llm_params * total`（默认视频方案约 3.6×10¹³ FLOPs），兑现 docstring 的承诺。
5. **讲义练习 5**：用纯 Python 实现 2D bilinear 下采样，验证 24×24 → 12×12 等于 2×2 块平均；再试 3 倍下采样，观察它退化为"取中心像素"（参考测验 Q11）。
6. **让 `mix` 影响分配**：例如按场景占比加权，求一个"期望 token 数"；或者对占比最高的场景放宽池化、对占比低的场景加强池化（讲义练习 1 的 80/10/10 场景）。

---

## 8. 常见坑

- **奇数网格的取整**：27×27 做 2 倍池化，向下取整得 169，向上取整得 196，"除以 4"得 182。预算表里必须统一口径。
- **把"每维缩小倍数"和"token 缩小倍数"混淆**：24×24 → 12×12 是每维 2 倍、token 4 倍；讲义练习 5 写成了 "4x reduction per dim"。
- **以为 bilinear 下采样总是块平均**：只有 2 倍且 `align_corners=False` 时等于 2×2 平均；3 倍时只取中心像素，会丢信息、产生混叠。
- **首个可行解 ≠ 最优解**：循环顺序决定结果，预算变大时方案可能纹丝不动。
- **兜底分支不受约束**：写兜底时也要检查预算，否则"永不超上下文"的承诺会在边界情况下失效。
- **打印目标却不检查目标**：spread 30.3% 和 "target under 30%" 并排打印，读者容易误以为达标。
- **定义了不用的类**：`Budget` 从未被实例化，属于死代码；阅读时不要以为它参与了计算。
