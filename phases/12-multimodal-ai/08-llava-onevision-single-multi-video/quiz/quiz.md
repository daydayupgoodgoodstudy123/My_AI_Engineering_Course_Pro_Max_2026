# 测验 · LLaVA-OneVision：统一处理单图、多图与视频（LLaVA-OneVision: Single-Image, Multi-Image, Video in One Model）

> **阶段 12 · 多模态 AI · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 注：中文讲义为机器翻译，错误较多（例如把"约 3000–4000 tokens"译成了"约3,000-4000美元"），数字与术语请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三条旧路线 | OneVision 之前：单图（LLaVA-1.5）、多图（Mantis、VILA）、视频（Video-LLaVA、Video-LLaMA）各自为政，"each won its benchmark and failed at the others" |
| 2 | 三种场景的不同压力 | 单图要高分辨率抓 OCR 和细节；多图要几张中等分辨率的图同时放进上下文；视频要很多低分辨率帧捕捉时间动态 |
| 3 | 统一视觉 token 预算 | 每个样本约 3000–4000 个视觉 token，三种场景用不同的"分辨率 × 切块 × 池化 × 张数/帧数"凑到相近的总数，LLM 永远不会被撑爆上下文 |
| 4 | token 算术 | 384 / 14 → 27×27 = 729 个 patch；2×2 池化 → 13×13 = 169（向下取整）；3×3 池化 → 9×9 = 81；32 帧 × 81 = 2592 |
| 5 | AnyRes-k | k 个固定分辨率子图 + 1 张缩略图，总 token = `(k + 1) × 每块 token`；常见 k ∈ {4, 9} |
| 6 | 三阶段课程 | Stage SI（单图 SFT）→ Stage OV（单图 + 多图 + 视频混合）→ Stage TT（目标任务迁移）；阶段之间不重置权重 |
| 7 | 顺序很重要 | 讲义："Training video-first or multi-image-first produces worse image performance than single-image-first, even with the same data." |
| 8 | 课程为什么有效 | 单图阶段打感知基础；多图/视频带来的"哪张是哪张、谁先发生"等结构难题需要先有扎实的感知；一起从头训会感知欠拟合、结构过拟合 |
| 9 | 三项涌现能力 | 多摄像头推理、set-of-mark prompting（编号标记提示）、iPhone 截图 agent——都不是直接训练的任务 |
| 10 | 双线性池化与对比 | 在 2D patch 网格上做 bilinear 插值以保留局部性；OneVision 固定预算、调整池化，Qwen2.5-VL 让预算随输入增长（M-RoPE + 动态 FPS） |

### 核心技能（能动手做到）

- [ ] 给定分辨率、patch 大小和池化倍数，手算每块 / 每帧的视觉 token 数，并说清向下取整与向上取整的区别
- [ ] 为单图、多图、视频三种场景分别设计配置，让它们都落在同一个 token 预算附近
- [ ] 读懂本节 `plan_*` 函数的"首个可行解"搜索，指出它为何在 4096 和 8192 预算下给出完全相同的方案
- [ ] 用纯 Python 实现 2D 双线性下采样，并验证 2 倍下采样等于 2×2 块平均（讲义练习 5）
- [ ] 按产品的场景分布（如 80/10/10）设计 token 预算和三阶段课程的数据权重
- [ ] 解释 OneVision 的"固定预算"与 Qwen2.5-VL 的"随输入增长"两种策略的取舍

---

## 二、基础自测（选择题）

**Q1.** 一个 384×384 的 tile，patch 大小 14，按本节代码 `per_tile_tokens(384, 14, 2)` 做 2×2 池化后，每个 tile 有多少视觉 token？

- A. 182
- B. 196
- C. 169
- D. 729

**Q2.** LLaVA-OneVision 的训练课程顺序是：

- A. 单图 SFT（SI）→ 单图 + 多图 + 视频混合（OV）→ 目标任务迁移（TT）
- B. 视频 → 多图 → 单图，由难到易
- C. 三种场景从第一步起均匀混合训练
- D. 多图 → 单图 → 视频

**Q3.** 视频场景：32 帧、每帧 384 分辨率（patch 14）、3×3 双线性池化，按代码公式，每个样本的视觉 token 总数是：

- A. 6272
- B. 23328
- C. 1820
- D. 2592

**Q4.** 下列哪一项**不是** LLaVA-OneVision 论文报告的三项涌现能力之一？

- A. 多摄像头（multi-camera）驾驶场景推理
- B. 根据文字描述生成视频
- C. set-of-mark prompting：对图中编号标记的物体进行推理
- D. 根据 iPhone 截图规划下一次点击

**Q5.** LLaVA-OneVision 与 Qwen2.5-VL 处理视觉 token 预算的方式区别在于：

- A. OneVision 固定每个样本的预算、通过调整池化来适配不同场景；Qwen2.5-VL 用 M-RoPE 和动态 FPS，预算随输入长度增长
- B. OneVision 的预算随视频长度线性增长；Qwen2.5-VL 固定每个样本 3000 个 token
- C. 两者都不池化，直接把全部 patch 送入 LLM
- D. Qwen2.5-VL 只支持单图

**Q6.** 按代码 `anyres_tokens(tiles, per_tile)` 的定义，AnyRes-9、每块 169 个 token 时，单图总共有多少视觉 token？

- A. 1521
- B. 1820
- C. 7290
- D. 1690

**Q7.** 讲义认为"所有场景从一开始一起从头训练"效果较差，原因是：

- A. 多图和视频数据太少，无法凑满 batch
- B. 每个 batch 中单图数据有限，模型感知能力欠拟合，却在大量多图/视频数据上过拟合"结构"，结果是会跟随跨图推理模式但视觉上很浅
- C. 混合训练会导致 LLM 上下文溢出
- D. 视频帧必须用不同的 encoder

**Q8.** 把 24×24 的 patch 网格用 bilinear 插值（`align_corners=False`）下采样到 12×12，下列说法正确的是：

- A. 每个维度缩小 4 倍，token 数缩小 16 倍
- B. 结果等于每个 2×2 块的中心像素，不做任何平均
- C. 每个维度缩小 2 倍、token 数从 576 降到 144；结果恰好等于每个 2×2 块的平均值
- D. 池化在 token 序列（1D）上进行，会打乱空间局部性

---

## 三、动手 / 代码题

**Q9.** 阅读 `plan_single_image`：

```python
def plan_single_image(budget: int) -> dict:
    for tiles in [9, 4, 1]:
        for per_tile_size in [(384, 14, 2), (384, 14, 1), (336, 14, 2)]:
            res, patch, pool = per_tile_size
            per = per_tile_tokens(res, patch, pool)
            total = anyres_tokens(tiles, per)
            if total <= budget:
                return {...}
```

`plan_multi_image`、`plan_video` 的结构相同。

1. 分别用预算 3000、4096、8192 调用三个 `plan_*` 函数，结果有什么变化？为什么？
2. 默认预算 4096 下，单图只用了 41.3%，多图 33.0%。`outputs/skill-onevision-budget-planner.md` 要求"flag any scenario that falls below 70% of target (under-tokenized)"——按这个规则，哪些场景应被标记？代码标记了吗？
3. `main()` 打印 "budget spread across scenarios: 1240 tokens (30.3% of budget)"，紧接着打印 "LLaVA-OneVision target: keep spread under 30%"。这里有什么问题？
4. 把"首个可行解"改成"最大利用率的可行解"，写出改动思路，并说明预算 4096 下单图会选出什么配置。

**Q10.** 观察兜底返回值：

```python
    return {"scenario": "single-image", "tiles": 1, "per_tile": 81, "total": 162}
    ...
    return {"scenario": "video", "n_frames": 8, "per_frame": 64, "total": 512}
```

1. `plan_video(500)` 返回什么？`plan_single_image(100)` 呢？这违反了模块 docstring 中的哪条承诺？
2. 兜底字典和正常返回的字典在键上有什么不一致？`print_plan` 会因此出错吗？
3. 给出一个更安全的处理方式，并结合 skill 文件的拒绝规则（"If the per-sample token budget is below 1024, refuse for multi-image or video"）说明。

**Q11.**（讲义练习 5）用纯 Python（不用 NumPy）实现 `bilinear_downsample(grid, out_h, out_w)`，采用 `align_corners=False` 的坐标映射。然后：

1. 验证 24×24 → 12×12 的结果等于每个 2×2 块的平均；
2. 再试 24×24 → 8×8（3 倍），结果还等于 3×3 块平均吗？这对"3×3 双线性池化"意味着什么？

**Q12.** 同一个"384 分辨率、2×2 池化"的 tile，出现了三个数字：讲义"概念"一节写 **182** 个 token（AnyRes-9 合计 1820），代码算出 **169**（合计 1690），讲义"问题"一节写视频每帧约 **196**。

1. 解释这三个数字分别是怎么来的。
2. 讲义写"Multi-image: ... 729 tokens with no pooling. Budget 6 images → 4374 tokens"，而代码在 4096 预算下选择了 8 张 × 169。两者差在哪里？讲义的方案放得进 4096 预算吗？
3. 模块 docstring 说会打印 "expected FLOPs per sample"，但代码没有。用"前向 FLOPs ≈ 2 × 参数量 × token 数"估算：7B LLM 处理默认视频方案的视觉 token 需要多少 FLOPs？

---

## 四、面试高频题

**Q13.**（基础必考）LLaVA-OneVision 的核心思想是什么？它如何在单图、多图、视频三种场景之间分配视觉 token？

**Q14.**（原理深挖）为什么课程必须"单图先行"？如果把顺序改成"先多图、再单图、再视频"（讲义练习 3），你预测哪些 benchmark 会退化？

**Q15.**（工程实践）（讲义练习 1）你的产品流量是 80% 单图、10% 多图（2–4 张）、10% 视频（8–16 帧）。请设计 token 预算和课程数据权重，并说明省下来的预算放在哪里。

**Q16.**（追问型）（讲义练习 4）如果视频 benchmark 是在每个样本只有 8 帧的数据上训练的，推理时给 30 秒视频还能泛化吗？先坏掉的是 token 预算还是时间推理？

**Q17.**（场景设计）你要上线一个同时处理截图问答和 5 秒到 10 分钟不等视频的服务。你会选 OneVision 式的"固定预算"还是 Qwen2.5-VL 式的"随输入增长"？从训练、推理成本、延迟可预测性和效果几个角度分析。

---

## 五、参考答案与解析

### Q1 — 答案：C

`384 // 14 = 27`（384 / 14 ≈ 27.43，代码用整除），网格 27×27 = 729；`27 // 2 = 13`，13×13 = **169**。A（182）是讲义"概念"一节写的数字，等于 729 / 4 ≈ 182.25 的近似，不是任何真实网格的平方；B（196）是向上取整 14×14 的结果；D 是未池化的 729。详见 Q12。

### Q2 — 答案：A

讲义的三阶段：Stage SI（单图 SFT，AnyRes 高分辨率）→ Stage OV（单图 + 多图 + 视频混合，统一预算，"No weight reset — continues from stage SI"）→ Stage TT（按目标产品的任务组合继续训练）。B、D 违背"单图先行"；C 正是讲义说的会"感知欠拟合"的做法。

### Q3 — 答案：D

`27 // 3 = 9`，每帧 9×9 = 81，32 帧 × 81 = **2592**，与讲义和代码输出一致。A（6272）是按讲义"问题"一节每帧 196 计算的 32 帧；B 是不池化（729 × 32）；C（1820）是讲义中 AnyRes-9 单图的数字。

### Q4 — 答案：B

讲义列出的三项涌现能力是 multi-camera reasoning、set-of-mark prompting、iPhone-screenshot agent。LLaVA-OneVision 是理解模型，只输出文本，没有视频生成能力；"由文生成图像/视频"属于本阶段后面 Emu3 等统一生成模型的内容。

### Q5 — 答案：A

讲义："Its budget scales with input — a 1-minute video uses more tokens than a 5-second video. LLaVA-OneVision fixes the budget and scales the pooling. Both work; they trade configurability for predictability." B 把两者说反了；C 错，两者都会压缩 token（OneVision 用 bilinear 池化，Qwen 系列用相邻 patch 合并）；D 错，Qwen2.5-VL 支持图像和视频。

### Q6 — 答案：D

`anyres_tokens(9, 169) = (9 + 1) × 169 = 1690`，多出来的 1 是缩略图（thumbnail）。A（1521 = 9 × 169）漏了缩略图；B 是讲义用 182 算出的 1820；C 是不池化的 `10 × 729`。代码输出 `SINGLE-IMAGE ... used 1690`。

### Q7 — 答案：B

讲义："If you train all scenarios from scratch together, the model underfits perception (limited single-image data per batch) and overfits structure (lots of multi-image / video data). Result: a model that follows cross-image reasoning patterns but is visually shallow." A、D 无依据；C 错，统一预算本身就是为了不溢出上下文。

### Q8 — 答案：C

`align_corners=False` 时，输出像素 i 对应输入坐标 `(i + 0.5) × 2 − 0.5 = 2i + 0.5`，正好落在第 2i 与 2i+1 个像素的正中间，双线性插值的两个权重都是 0.5，二维上就是 2×2 块的平均（已用 PyTorch `F.interpolate` 与 `F.avg_pool2d` 对比验证完全一致）。A：讲义练习 5 写 "a 4x reduction per dim"，实际是每维 2 倍、总数 4 倍（576 → 144）；B 是 3 倍下采样时的情况（见 Q11）；D 与讲义相反："Pooling is done in patch-grid space, not token space, to preserve locality."

### Q9 — 参考答案

1. 实际运行：预算 3000、4096、8192 下三个场景的方案**完全相同**——单图 9 tiles × 169 = 1690、多图 8 × 169 = 1352、视频 32 × 81 = 2592。原因：搜索按"tile/张/帧数从多到少、池化从强到弱"的顺序，返回**第一个**不超预算的方案。由于 `(384, 14, 2)`（池化最强）排在 `(384, 14, 1)` 之前，只要最多 tile 数的强池化方案放得下就立刻返回，预算再大也不会去试"少池化、更高保真"的方案。预算变小时才会改变：例如 2048 时视频降为 16 帧（1296），1024 时单图降为 4 tiles（845）、多图 6 张（1014）、视频 8 帧（648）。
2. 三个场景都低于 70%：单图 41.3%、多图 33.0%、视频 63.3%，按 skill 规则全部应标记为 under-tokenized。代码只打印百分比，没有任何标记逻辑。讲义 "Use It" 也说代码会报告 "which scenarios are under-tokenized"，实际并未实现。
3. spread = 2592 − 1352 = 1240，占预算 30.3%，**已经超过**下一行打印的 30% 目标，但代码既不判断也不警告，读者容易误以为方案达标。
4. 改为遍历全部候选、在 `total <= budget` 的方案中选 `total` 最大者（同分时可优先 tile 多 / 池化少）。预算 4096 下，单图候选里 `tiles=4, pool=1` 得 `5 × 729 = 3645`（利用率 89%），优于 `tiles=9, pool=2` 的 1690——这正是讲义提到的 "AnyRes-4 at 729-per-tile = 2916 + 729"。示意：

```python
def plan_single_image(budget: int) -> dict | None:
    best = None
    for tiles in [9, 4, 1]:
        for res, patch, pool in [(384, 14, 2), (384, 14, 1), (336, 14, 2)]:
            per = per_tile_tokens(res, patch, pool)
            total = anyres_tokens(tiles, per)
            if total <= budget and (best is None or total > best["total"]):
                best = {"scenario": "single-image", "tiles": tiles, "tile_res": res,
                        "pool": pool, "per_tile": per, "total": total}
    return best
```

   同理，多图在 4096 下最佳为 `4 × 729 = 2916` 或 `8 × 169 = 1352` 中的前者（6 × 729 = 4374 超预算）；视频为 `16 × 169 = 2704`（比 32 × 81 = 2592 略高，用更少的帧换更高的每帧保真度）。是否接受这种取舍应由场景偏好决定，而不是由循环顺序决定。

### Q10 — 参考答案

1. 实际运行：`plan_video(500)` 返回 `{'n_frames': 8, 'per_frame': 64, 'total': 512}`，512 > 500；`plan_single_image(100)` 返回 `total=162`，`plan_multi_image(100)` 返回 162、`plan_video(100)` 返回 512，全部超出预算。这违反了 docstring 的 "Keeps the budget roughly constant across scenarios so the LLM never blows context"——兜底分支恰恰可能撑爆上下文。
2. 兜底字典缺少 `tile_res` / `resolution` 和 `pool` 键；`per_frame=64` 也不在候选列表里（它对应 336 分辨率、3 倍池化：`24 // 3 = 8`，8×8 = 64，但候选只有 `(336, 2)`）。`print_plan` 只遍历已有的键、跳过 `scenario` 和 `total`，所以不会报错，但打印出来的配置信息不完整，无法复现。
3. 更安全的做法：找不到可行解时返回 `None` 或抛出 `ValueError`，由调用方决定是否拒绝服务或降级；同时在入口处检查 `budget < 1024` 时直接拒绝多图和视频（skill 的拒绝规则），并在返回前 `assert plan["total"] <= budget`。

### Q11 — 参考答案

```python
def bilinear_downsample(grid, out_h, out_w):
    in_h, in_w = len(grid), len(grid[0])
    sy, sx = in_h / out_h, in_w / out_w
    out = []
    for i in range(out_h):
        y = min(max((i + 0.5) * sy - 0.5, 0), in_h - 1)   # align_corners=False
        y0 = int(y); y1 = min(y0 + 1, in_h - 1); wy = y - y0
        row = []
        for j in range(out_w):
            x = min(max((j + 0.5) * sx - 0.5, 0), in_w - 1)
            x0 = int(x); x1 = min(x0 + 1, in_w - 1); wx = x - x0
            top = grid[y0][x0] * (1 - wx) + grid[y0][x1] * wx
            bot = grid[y1][x0] * (1 - wx) + grid[y1][x1] * wx
            row.append(top * (1 - wy) + bot * wy)
        out.append(row)
    return out

import random
g = [[random.random() for _ in range(24)] for _ in range(24)]
d2 = bilinear_downsample(g, 12, 12)
mean2 = [[sum(g[2*i+a][2*j+b] for a in range(2) for b in range(2)) / 4
          for j in range(12)] for i in range(12)]
print(max(abs(d2[i][j] - mean2[i][j]) for i in range(12) for j in range(12)))   # ~1e-16
```

1. 2 倍时采样坐标为 `2i + 0.5`，两个方向的权重都是 0.5，结果与 2×2 块平均的最大误差约 1e-16（浮点误差），即**完全相等**。
2. 3 倍时采样坐标为 `(i + 0.5) × 3 − 0.5 = 3i + 1`，恰好落在 3×3 块的**中心像素**上，权重为 (1, 0)，结果等于直接取中心像素，而不是 3×3 平均（与 PyTorch `F.interpolate(..., mode="bilinear")` 的结果一致，已验证）。这意味着不开抗锯齿的"3×3 双线性池化"实际上丢弃了每块 9 个 patch 中的 8 个，只是**下采样**而不是**平均池化**，可能出现混叠（aliasing）。如果想保留整块信息，应改用 `avg_pool2d` 或打开抗锯齿选项。这也是讲义练习 5 只问 2 倍情形的原因——"bilinear = 块平均"只在 2 倍时成立。

### Q12 — 参考答案

1. 三个数字：
   - **169**：代码 `per_tile_tokens` 用整除，`27 // 2 = 13`，13² = 169。
   - **196**：对奇数边长向上取整，`ceil(27 / 2) = 14`，14² = 196。用 bilinear 插值把 27×27 缩放到 `ceil(h/2) × ceil(w/2)` 时就会得到这个数（我们用 `F.interpolate(size=(14, 14))` 验证了输出形状），讲义"问题"一节的"~196 tokens per frame"与此吻合。
   - **182**：`729 / 4 = 182.25` 的近似，只是"token 数除以 4"，不对应任何整数网格（13² = 169，14² = 196）。讲义"概念"一节的 `9 × 182 + 182 = 1820` 是近似算术。
   - 结论：奇数边长的网格做 2 倍池化时，必须明确取整方式，否则预算会差 10%–15%。
2. 讲义的多图方案是"每张 729 个 token、不池化、6 张 = 4374"，而 4374 > 4096，**放不进**代码使用的 4096 预算（不过讲义说的预算是"approximately 3000-4000"，同样放不下）。代码在 `n_images=8` 时先试 `(384, 2)`，得到 8 × 169 = 1352，立即返回，于是选择了"更多张、每张更粗"的方案。另外讲义"问题"一节写多图每张约 576 个 token（336 分辨率时 24×24），"概念"一节又写 729（384 分辨率），讲义内部也不一致。
3. 视频方案 2592 个视觉 token，7B LLM 前向约 `2 × 7×10⁹ × 2592 ≈ 3.6 × 10¹³` FLOPs（36 TFLOPs），只算视觉 token、不含文本 token 和注意力的二次项。可以在 `print_plan` 中加一行 `flops = 2 * llm_params * plan["total"]` 实现 docstring 的承诺。

### Q13 — 参考回答要点

- **核心思想**：一个模型、一套课程，覆盖单图、多图、视频三种场景；关键是一个在各场景间**大致恒定**的视觉 token 预算（约 3000–4000/样本），加上"单图 → OneVision 混合 → 任务迁移"的显式课程。
- **分配方式**（讲义数字）：
  - 单图：AnyRes-9（3×3 tiles + 缩略图），每块 384 分辨率 729 个 patch，2×2 池化后约 182（讲义近似值），合计约 1820；或 AnyRes-4 不池化 `4 × 729 + 729 = 3645`；
  - 多图：每张 384、不切块，729 个 token，6 张约 4374；
  - 视频：32 帧，每帧 3×3 池化后 81 个，合计 2592。
- **效果**：LLM 消耗的预算相近，"The encoder produces different geometry per scenario, but the LLM consumes the same budget"；单一模型可以在三类 benchmark 上同时取得好成绩，并出现跨场景迁移。
- 加分点：说出三项涌现能力；指出这个预算是训练 batch 形状可控、推理成本可预测的关键。

### Q14 — 参考回答要点

- **单图先行的原因**：单图高分辨率数据最适合教会模型"看清楚"（感知、OCR、细粒度理解）；多图和视频的难点是结构（"哪张是哪张、哪件事先发生"），需要以扎实的感知为前提。先学结构、后学感知，模型会学到"跨图推理的套路"但看不清细节。
- **对练习 3 的预测**（推理，不是论文数据）：
  - 单图细粒度 benchmark（OCR、DocVQA、ChartQA 等）最先退化，因为感知基础打得晚，且被后续阶段的低分辨率视频数据稀释；
  - 多图 benchmark 可能短期内不差（先学过），但后续单图、视频阶段可能导致部分遗忘；
  - 视频 benchmark 受影响较小，但依赖细节识别的视频问答会变差。
- 讲义："Training video-first or multi-image-first produces worse image performance than single-image-first, even with the same data. The paper ablates this explicitly."（代码中 "2-4 MMMU" 的数字来自代码和 skill 文件，讲义正文没有给出具体数值。）
- 加分点：从灾难性遗忘角度补充——后面阶段的数据分布离单图越远，越需要在后续阶段保留一定比例的单图数据（OV 阶段的 0.5 单图权重正是这个作用）。

### Q15 — 参考回答要点

- **预算**：以 4096 为上限。单图占 80%，应把预算优先给单图：AnyRes-4 不池化 `5 × 729 = 3645`（OCR、细节最好），或 AnyRes-9 + 2×2 池化（1690，覆盖更大的原图面积）——按产品图片的长宽比与文字密度选。
- **多图（2–4 张）**：每张 729 个 token 不池化，最多 `4 × 729 = 2916`，放得下；不需要为 8 张图做强池化。
- **视频（8–16 帧）**：每帧 2×2 池化约 169（或 196），16 帧约 2700–3100；或 3×3 池化 81 个/帧，16 帧仅 1296。视频占比低，可以用较强池化节省成本。
- **省下的预算放在哪里**：不做重度多图 / 长视频，就把预算还给单图的高分辨率（少池化、多 tile），以及文本上下文（更长的指令、多轮对话）。
- **课程权重**：SI 阶段全单图；OV 阶段约 0.6 / 0.2 / 0.2（仍偏单图，避免遗忘）；TT 阶段按产品分布 0.8 / 0.1 / 0.1。
- 常见误区：skill 文件的 hard reject："Allocating all budget to video when the product is 80% single-image."

### Q16 — 参考回答要点

- **token 预算未必先坏**：30 秒视频若按 1 fps 采 30 帧、每帧 81 个 token，共 2430 个，仍在 3000–4000 预算内；按 2 fps 取 60 帧则约 4860，开始超出，需要降采样帧数或加大池化。
- **时间推理更可能先坏**：训练只见过 8 帧，帧间间隔、事件跨度、帧的顺序编号都局限在小范围内；推理时帧数和时间跨度变大，属于分布外（类似长度外推），模型可能能"看到"每一帧，却无法正确排序事件或计算时长。
- **常见做法**：推理时仍均匀采 8–32 帧（与训练一致）；训练时加入更多帧数的数据；使用显式时间编码（如 Qwen2.5-VL 的绝对时间对齐 M-RoPE，下一节内容）。
- 加分点：区分"信息不足"（帧太少漏掉事件）和"推理失败"（帧够但理不清时序），并为两者设计不同的评测。

### Q17 — 参考回答要点

- **固定预算（OneVision）**：
  - 优点：每个请求的视觉 token 上限已知，延迟和显存可预测，batch 形状稳定，便于容量规划；
  - 缺点：10 分钟视频被压到与 5 秒视频同样的 token 数，每秒信息量下降很多；截图类任务若池化过强会损失 OCR 能力。
- **随输入增长（Qwen2.5-VL）**：
  - 优点：长视频保留更多信息，短视频不浪费；时间编码可与真实时间对齐；
  - 缺点：成本和延迟随输入线性增长，需要设置上限、排队和计费策略，尾延迟难控制。
- **折中方案**：设置"随输入增长 + 硬上限"（如最多 N 帧 / M 个 token），超出时降低 fps 或加强池化；截图请求走高分辨率、少池化的路径，视频走低 fps + 强池化的路径；对超长视频先做场景检测或检索，只送入相关片段（第 18 节长视频内容）。
- 加分点：说明这是"可配置性 vs 可预测性"的权衡（讲义原话 "they trade configurability for predictability"），并给出用 SLO（如 P95 延迟）来决定上限的方法。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：LLaVA 架构与两阶段训练，是本节的出发点。
- [阶段 12 · 06 任意分辨率视觉：Patch-n'-Pack 与 NaFlex](../../06-any-resolution-patch-n-pack/docs/zh.md)：AnyRes 切块与缩略图的来源。
- [阶段 12 · 07 开放 Weight VLM 的构建方案：真正重要的因素](../../07-open-weight-vlm-recipes/docs/zh.md)：视觉 token 数是影响最大的设计轴，本节的预算设计正是围绕它展开。
- [阶段 04 · 12 视频理解——时间建模](../../../04-computer-vision/12-video-understanding/docs/zh.md)：帧采样与时间建模基础。

### 本节被哪些后续内容用到
- [阶段 12 · 09 Qwen-VL 系列与动态帧率视频](../../09-qwen-vl-family-dynamic-fps/docs/zh.md)：与本节"固定预算"相对的"动态预算"路线。
- [阶段 12 · 17 视频语言模型：时间 Tokens 与 Grounding](../../17-video-language-temporal-grounding/docs/zh.md)：视频中的时间定位。
- [阶段 12 · 18 百万 Token 上下文中的长视频理解](../../18-long-video-million-token/docs/zh.md)：当视频长到固定预算放不下时怎么办。
- [阶段 12 · 25 多模态 Agents 与计算机操作（综合项目）](../../25-multimodal-agents-computer-use/docs/zh.md)：iPhone 截图 agent 这类涌现能力的工程化。
- [阶段 19 · 12 综合项目 12：视频理解流程——场景、问答与搜索](../../../19-capstone-projects/12-video-understanding-pipeline/docs/zh.md)：在完整流程中实践帧采样与 token 预算。

### 延伸关键词
`LLaVA-OneVision` · `LLaVA-OneVision-1.5` · `AnyRes-k` · `bilinear pooling` · `visual token budget` · `curriculum learning` · `catastrophic forgetting` · `set-of-mark prompting` · `task transfer` · `Video-LLaVA` · `VILA` · `M-RoPE` · `dynamic FPS`
