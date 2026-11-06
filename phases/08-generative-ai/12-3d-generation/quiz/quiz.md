# 测验 · 3D 生成（3D Generation）

> **阶段 08 · 生成式 AI · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 3D 为什么难 | 表示多样（网格、点云、体素、SDF、NeRF、3D 高斯）、数据稀缺（Objaverse-XL 约 1000 万个物体，质量参差）、内存大、通常只有少量 2D 视图作监督 |
| 2 | 2026 主流两段式 | 先用扩散模型生成**多视角 2D 图像**，再把 **3D 表示**（通常是高斯泼溅）拟合到这些图像上 |
| 3 | 3D Gaussian Splatting | 场景 = 约 100 万个 3D 高斯，每个 59 个参数（位置 3 + 四元数 4 + 缩放 3 + 不透明度 1 + 3 阶球谐颜色 48）；投影 + 按深度排序做 alpha 合成；可微、实时 |
| 4 | 致密化与剪枝 | 3DGS 训练时在梯度大的区域分裂/克隆高斯、删除无用高斯；不加约束会膨胀到上千万个并过拟合 |
| 5 | 多视角扩散 | 微调图像扩散模型，同时生成同一物体的多个一致视角（Zero123、MVDream、SV3D、CAT3D），通常 4–16 个视角；视角之间要共享注意力 |
| 6 | 前馈式重建 | LRM（输出 triplane）、InstantMesh（输出网格）、TripoSR、LGM 等一次前向就从一张或几张图得到 3D，秒级完成 |
| 7 | SDS / DreamFusion | 把 2D 扩散模型的 score 当作伪梯度，逐个资产优化一个 3D 模型；质量可以，但每个资产约 1 小时 |
| 8 | NeRF | 小 MLP 输入 `(x, y, z, 视线方向)`，输出 `(颜色, 密度)`，沿光线积分渲染；质量好但渲染比网格慢 100–1000 倍 |
| 9 | 生产部署 | 3D 还没有统一底座：请求时跑多视角扩散，异步重建为 3DGS 供实时浏览；进游戏引擎要转网格并带 PBR 材质 |

### 核心技能（能动手做到）

- [ ] 能逐项算出 3DGS 每个高斯的 59 个参数，并估算 100 万个高斯的存储量
- [ ] 能写出 alpha 合成公式，说明它与本节玩具代码"直接相加"的区别
- [ ] 运行 `code/main.py`，能解读 ASCII 图和 MSE，并识别出输出中由负像素值导致的伪影
- [ ] 能指出 `finite_diff_step` 中"基线损失过期"的问题，复现它在 64 个高斯时的数值溢出，并给出修正
- [ ] 能为颜色参数写出解析梯度，并用数值梯度验证
- [ ] 能根据输入（文本 / 单图 / 多图 / 实拍）和输出用途（实时浏览 / 游戏引擎 / VR）设计 3D 生成管线

---

## 二、基础自测（选择题）

**Q1.** 按讲义，2026 年主流的生成式 3D 管线是怎样拆分问题的？

- A. 直接用 3D 卷积网络在体素上做扩散
- B. 先用扩散模型生成多视角 2D 图像，再拟合 3D 表示（通常是高斯泼溅）
- C. 先生成点云，再用 GAN 上色
- D. 先训练 NeRF，再用 NeRF 生成文本描述

**Q2.** 3DGS 中每个高斯有 59 个参数。下面哪种拆分是对的？

- A. 位置 3 + 协方差矩阵 9 + 不透明度 1 + RGB 3 + 法线 43
- B. 位置 3 + 旋转四元数 4 + 缩放 3 + 不透明度 1 + 3 阶球谐颜色 48
- C. 位置 3 + 缩放 3 + 不透明度 1 + 球谐颜色 52
- D. 位置 3 + 旋转 3 + 缩放 3 + 不透明度 1 + 纹理 49

**Q3.** 真实 3DGS 渲染一个像素时，对覆盖该像素的多个高斯的处理方式是：

- A. 把所有高斯的颜色直接相加
- B. 沿光线采样数百个点，逐点用 MLP 查询颜色和密度
- C. 按深度排序，用 alpha 合成从前往后累积，前面的高斯会遮挡后面的
- D. 只取离相机最近的那一个高斯

**Q4.** 独立生成 4 个视角的图片再做 3D 拟合，结果很模糊。讲义给出的根本解决方法是：

- A. 增加高斯数量
- B. 使用视角之间共享注意力的多视角扩散模型，保证各视角对物体结构的描述一致
- C. 换成 NeRF
- D. 提高每张图的分辨率

**Q5.** 关于 SDS（Score Distillation Sampling），下列说法正确的是：

- A. 它训练一个可以直接前馈输出 3D 的大模型
- B. 它把 2D 扩散模型的 score 当作伪梯度，对每个资产单独优化一个 3D 表示，因此每个资产需要较长时间
- C. 它不需要预训练的 2D 扩散模型
- D. 它是一种网格重拓扑算法

**Q6.** 3DGS 训练中不加控制，高斯数量涨到上千万并过拟合。讲义指出的必要手段是：

- A. 把学习率调大
- B. 原论文的致密化（densification）+ 剪枝（pruning）启发式规则
- C. 改用体素表示
- D. 去掉不透明度参数

**Q7.** 客户要把生成的 3D 资产直接放进 Unity / Unreal。下列做法最合适的是：

- A. 直接导出 3DGS 文件交付
- B. 交付 NeRF 权重
- C. 用能输出 PBR 网格的模型（如 Meshy 4、Rodin Gen-1.5），或者把 3DGS/隐式场转成网格并做重拓扑、补材质通道
- D. 交付多视角图片，让美术自己建模

**Q8.** 关于 NeRF 与 3DGS，下列说法**错误**的是：

- A. NeRF 用 MLP 把 3D 坐标和视线方向映射为颜色和密度
- B. NeRF 渲染时需要沿光线积分，比基于网格的方法慢很多
- C. 3DGS 的渲染是可微的，可以用梯度下降拟合真实照片
- D. 3DGS 因为不可微，只能用遗传算法优化

---

## 三、动手 / 代码题

**Q9.**（找 bug）阅读 `finite_diff_step`：

```python
def finite_diff_step(gaussians, target, lr, eps=0.1):
    base = render(gaussians)
    base_loss = mse(base, target)
    for g in gaussians:
        for key in ("pos", "sigma", "color"):
            if isinstance(g[key], list):
                for i in range(len(g[key])):
                    g[key][i] += eps
                    up = mse(render(gaussians), target)
                    g[key][i] -= eps
                    grad = (up - base_loss) / eps
                    g[key][i] -= lr * grad
            else:
                # ... 标量参数同理
    return base_loss
```

(a) `base_loss` 在整个函数中只算了一次，而每个参数的梯度算完后**立即**更新了参数。这会带来什么问题？
(b) 讲义练习 1 让你用 64 个高斯运行。按 `main` 的写法（`init_gaussians(64, random.Random(7 + 64))`，`lr=0.5, eps=0.2`），预测会发生什么。
(c) 给出修正版本。

**Q10.**（解读输出）实际运行时，"fit 8 Gaussians" 的 ASCII 图右上角出现了 `@#@`、`###` 这类最亮的字符，而目标图像在那里几乎是 0。最终 8 个高斯的颜色是 `[-0.37, 0.05, 0.29, -0.0, -0.18, 0.41, 0.56, 0.25]`，渲染结果的最小像素值约为 −0.246。结合下面的代码解释原因，并给出修复：

```python
def ascii_img(img, chars=" .:;+*#@"):
    peak = max(max(row) for row in img) or 1.0
    lines = []
    for row in img:
        line = "".join(chars[min(len(chars) - 1, int(v / peak * (len(chars) - 1)))]
                       for v in row)
        lines.append(line)
    return "\n".join(lines)
```

**Q11.** 有限差分要对每个参数各渲染一次，开销是 `O(参数数 × 渲染开销)`。请为**颜色参数**写出解析梯度函数 `color_grads(gaussians, target)`（损失为 `mse`），并用中心差分验证。为什么真实的 3DGS 一定要用解析梯度（自动微分 / 手写 CUDA 反向）？

---

## 四、面试高频题

**Q12.**（基础必考）比较 3D 表示：网格、点云、体素、SDF、NeRF、3D 高斯泼溅。生成式 3D 为什么越来越多地选择 3DGS？

**Q13.**（原理深挖）讲讲 3D Gaussian Splatting 的渲染与训练：投影、排序、alpha 合成、球谐颜色、致密化与剪枝。它为什么比 NeRF 快那么多？

**Q14.**（原理深挖）对比生成式 3D 的三条路线：SDS 逐资产优化（DreamFusion）、多视角扩散 + 重建（MVDream / CAT3D + 3DGS）、前馈式重建（LRM / TripoSR / InstantMesh）。各自的速度、质量和失败模式是什么？

**Q15.**（场景设计）电商平台想让商家上传一张商品照片，就自动生成可 360° 旋转查看的 3D 模型，并且后续还要能导入游戏引擎做营销小游戏。请设计端到端方案，说明在线与离线的部分如何划分。

**Q16.**（追问型）单张图片生成 3D 时，背面是怎么来的？如何评估和缓解"背面幻觉"？

**Q17.**（工程实践）讲义说"3D 还没有统一的底座"。从服务化角度，NeRF/triplane、多视角扩散 + LRM、SDS 三类工作负载分别应该怎么部署？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："The 2026 stack separates the two problems. First, generate *2D multi-view images* with a diffusion model. Second, fit a *3D representation* (usually Gaussian splatting) to those images."这样可以借用在海量 2D 图像上训练的扩散模型的知识，弥补 3D 数据的稀缺。

### Q2 — 答案：B

`3 + 4 + 3 + 1 + 48 = 59`。球谐颜色：3 阶球谐每个颜色通道有 `(3+1)² = 16` 个系数，3 个通道共 48 个（只用 0 阶时是 3 个，即普通 RGB）。协方差是对称矩阵，只有 6 个自由度；实践中用"四元数 + 缩放"参数化，保证协方差始终半正定，便于优化。

### Q3 — 答案：C

真实 3DGS 把 3D 高斯投影成屏幕上的 2D 高斯，按深度排序后做 alpha 合成：`C = Σᵢ cᵢ·αᵢ·Πⱼ<ᵢ(1 − αⱼ)`。A 是本节玩具代码的简化（讲义："Our 2D toy just sums"）；B 是 NeRF 的体渲染方式。

### Q4 — 答案：B

讲义 Pitfalls："View inconsistency. If you generate 4 views independently and they disagree about object structure, the 3D fit is blurry. Fix: multi-view diffusion with shared attention."各视角互相矛盾时，3D 拟合只能取"平均"，所以会模糊；增加高斯数量（A）解决不了数据本身的矛盾。

### Q5 — 答案：B

SDS（DreamFusion 提出）：随机选一个相机渲染当前的 3D 表示，加噪后让冻结的 2D 扩散模型预测噪声，把"预测噪声与所加噪声之差"作为图像空间的梯度，反传到 3D 参数上。每个资产都要单独迭代优化，讲义表格中 DreamFusion 约 1 小时一个资产。Production note 也强调 SDS 是"逐资产优化而不是推理"，应该做成异步任务。

### Q6 — 答案：B

讲义："Densification + pruning heuristics (from 3D-GS original paper) are essential."致密化在梯度大（欠拟合）的区域分裂或克隆高斯；剪枝删除不透明度过低或尺寸过大的高斯，控制数量、防止过拟合。

### Q7 — 答案：C

讲义 Use It："Meshy 4 or Rodin Gen-1.5 output PBR meshes that go straight into Unity / Unreal."配套 skill 文件规定：不经过网格转换，就不要把 3DGS 直接交付给游戏引擎（大多数引擎不原生支持渲染高斯）；隐式场转出的网格常有孔洞或自相交，要先重拓扑（Pitfalls 中提到 Blender 的 voxel remesh）。

### Q8 — 答案：D

3DGS 的核心卖点之一就是渲染**可微**，可以用梯度下降拟合照片（讲义："Differentiable. Fit by gradient descent against ground-truth photos"），本节玩具代码也在演示这一点。A、B、C 都正确。

### Q9 — 参考答案

(a) 每个参数的梯度估计是 `(L(θ_当前 + eps·eᵢ) − base_loss) / eps`。但 `θ_当前` 已经包含了**本步前面所有参数的更新**，而 `base_loss` 还是更新前的损失。于是这个"梯度"里混进了"前面那些更新造成的损失变化 / eps"，不再是第 i 个参数的偏导数。前面的更新若大幅降低了损失，后面每个参数都会得到一个巨大的负"梯度"，被往同一个方向猛推。参数越多，累积的偏差越大。另外 `eps = 0.2` 的前向差分本身有 `O(eps)` 的截断误差，也会让梯度不准。

(b) **数值溢出崩溃**。我们在临时副本中实测：64 个高斯的初始损失高达约 15.36（大量高斯重叠，像素值远大于目标）。第 0 步内，前面几个参数的更新让损失急剧下降，后面参数的"梯度"变成巨大的负数，某个 `sigma` 被推到约 `2.4 × 10²³⁸`，接着在 `g["sigma"] ** 2` 处抛出 `OverflowError: (34, 'Numerical result out of range')`。16 个高斯时还能跑完（最终 MSE 约 0.028）。

(c) 修正：所有偏导数都基于**同一个**基线计算，算完再统一更新：

```python
def fixed_step(gaussians, target, lr, eps=0.2):
    base_loss = mse(render(gaussians), target)
    grads = []
    for g in gaussians:
        for key in ("pos", "sigma", "color"):
            if isinstance(g[key], list):
                for i in range(len(g[key])):
                    g[key][i] += eps
                    grads.append((g, key, i, (mse(render(gaussians), target) - base_loss) / eps))
                    g[key][i] -= eps
            else:
                g[key] += eps
                grads.append((g, key, None, (mse(render(gaussians), target) - base_loss) / eps))
                g[key] -= eps
    for g, key, i, gr in grads:          # 统一更新
        if i is None:
            g[key] -= lr * gr
        else:
            g[key][i] -= lr * gr
    return base_loss
```

实测（30 步，`lr=0.5, eps=0.2`）：n = 2 / 4 / 8 / 16 的最终 MSE 为 0.0601 / 0.0565 / 0.0356 / 0.0099；**n = 64 不再溢出**，最终 MSE 约 0.0121。若进一步改用中心差分（`eps=1e-3`）并跑 300 步，n = 8 能降到约 0.005。还可以把 `sigma` 限制为正数（例如优化 `log σ`），防止它穿过 0 导致除零。

### Q10 — 参考答案

**原因**：颜色参数没有约束，优化后出现了负颜色（−0.37、−0.18），右上角的像素值是负数。`int(v / peak * 7)` 对负数得到负整数，`min(7, 负数)` 只限制了上界，于是 `chars[-1] = '@'`、`chars[-2] = '#'`、`chars[-3] = '*'`……Python 的**负下标从末尾取值**，负像素反而被画成了最亮的字符。右上角的 `@#@` 并不是亮斑，而是"负亮度"的显示错误。

**修复**：同时夹紧下界，

```python
idx = int(v / peak * (len(chars) - 1))
idx = max(0, min(len(chars) - 1, idx))
line_chars.append(chars[idx])
```

更根本的做法是约束颜色非负（例如用 `softplus` 或 `exp` 参数化），真实 3DGS 的不透明度也会经过 sigmoid 限制在 (0, 1) 之内。

**启示**：可视化代码的 bug 会直接误导对模型的判断。这里 8 个高斯的 MSE（0.0365）虽然比 2、4 个时低，但图像上有一片"负亮度"区域，说明模型在用负颜色"挖掉"多余的亮度——这在真实 alpha 合成中是不允许的。

### Q11 — 参考答案

`pred(x,y) = Σₖ cₖ·Bₖ(x,y)`，其中基函数 `Bₖ = exp(−d²/(2σₖ²))`。`MSE = (1/N)·Σ(pred − target)²`，所以

```text
∂MSE/∂cₖ = (2/N) · Σ_{x,y} (pred − target) · Bₖ(x,y)
```

```python
import math

def color_grads(gaussians, target):
    pred = render(gaussians)
    N = SIZE * SIZE
    grads = []
    for g in gaussians:
        s = 0.0
        for y in range(SIZE):
            for x in range(SIZE):
                dx, dy = x - g["pos"][0], y - g["pos"][1]
                basis = math.exp(-(dx * dx + dy * dy) / (2 * g["sigma"] ** 2))
                s += 2 * (pred[y][x] - target[y][x]) * basis
        grads.append(s / N)
    return grads
```

用 3 个随机高斯验证（中心差分，`eps = 1e-5`），两者输出一致：`[0.027315, 0.081659, 0.100985]`。

**为什么必须用解析梯度**：有限差分每个参数都要额外渲染一次。100 万个高斯 × 59 个参数，就要做约 6000 万次渲染才能得到一步的梯度，根本不可行；而反向传播只需要"一次前向 + 一次反向"，开销与前向同阶，与参数数量无关。真实 3DGS 用手写 CUDA 的可微光栅化器，同时算出所有参数的梯度。此外解析梯度没有截断误差，数值也更稳定（不会出现 Q9 那样的问题）。

### Q12 — 参考回答要点

| 表示 | 特点 | 生成式场景中的问题 |
|------|------|-----------------|
| 网格 | 工业标准，引擎原生支持，可加 PBR 材质 | 拓扑离散、难以直接用梯度优化 |
| 点云 | 简单、易获取 | 没有表面、渲染有空洞 |
| 体素 | 规则网格，易用 3D 卷积 | 内存 `O(n³)`：512³ 约 1.3 亿个体素 |
| SDF | 能提取光滑表面 | 提取网格常有孔洞或自相交 |
| NeRF | 质量高、可微 | 渲染慢 100–1000 倍，要沿光线逐点查询 MLP |
| 3DGS | 显式、可微、实时（讲义：4090 上 1080p 约 100 fps），5–30 分钟拟合一个场景 | 高斯数量要控制；引擎不原生支持，交付前常需转网格 |

- **为什么选 3DGS**：既能用梯度下降从多视角图像高效拟合，又能实时浏览；显式表示方便编辑和前馈预测（LGM 等直接输出高斯）。
- **加分点**：最终交付形式取决于下游——游戏引擎要网格 + PBR，Web 实时浏览可以直接用 3DGS。

### Q13 — 参考回答要点

- **表示**：每个高斯有中心位置、协方差（四元数 + 缩放）、不透明度、球谐颜色系数（随视角变化的颜色，3 阶共 48 个系数）。
- **渲染**：把 3D 高斯投影到屏幕上成为 2D 椭圆高斯 → 分块（tile）并按深度排序 → 对每个像素从前往后做 alpha 合成 `C = Σ cᵢαᵢΠⱼ<ᵢ(1−αⱼ)`。全过程可微。
- **训练**：用多视角照片作监督，梯度下降优化所有参数（原论文的损失是 L1 + D-SSIM）；周期性致密化（欠拟合区域分裂/克隆）和剪枝（删除近乎透明的高斯）。
- **为什么比 NeRF 快**：NeRF 每个像素要沿光线采样几十到上百个点，每个点跑一次 MLP；3DGS 是显式的"光栅化"——每个高斯投影一次，按 tile 并行合成，没有逐点神经网络查询，非常适合 GPU。
- **常见误区**：以为高斯是"直接相加"（本节玩具代码的简化）；真实系统中前面的高斯会遮挡后面的。

### Q14 — 参考回答要点

| 路线 | 代表 | 速度（讲义表格） | 优点 | 典型失败模式 |
|------|------|----------------|------|-------------|
| SDS 逐资产优化 | DreamFusion、Magic3D、ProlificDreamer | 30 分钟到 1 小时/资产 | 只需要 2D 扩散模型 | 慢；颜色过饱和；"多面"（Janus）问题——各视角都想长出正面 |
| 多视角扩散 + 重建 | MVDream、SV3D、CAT3D + 3DGS/NeRF | 约 1–2 分钟 | 讲义："still the best-performing recipe for general objects" | 视角不一致时结果模糊；视角数有限 |
| 前馈重建 | LRM（triplane，约 5 秒）、InstantMesh（约 10 秒）、TripoSR（约 1 秒） | 秒级 | 快，适合在线 | 细节和背面质量受训练数据限制 |
| 直接文生网格 + PBR | Meshy 4、Rodin Gen-1.5、Hunyuan3D 2.0 | 30–60 秒 | 直接产出引擎可用的资产 | 复杂可动角色难（skill 建议改用支持绑定的管线） |

- **加分点**：把多视角扩散理解为"把 3D 问题转成 2D 问题"，利用 2D 数据的规模优势；前馈重建是"学一个重建器"，把逐资产优化摊销到训练中。

### Q15 — 参考回答要点

- **在线（秒级，用户等待）**：
  1. 抠图、居中、估计相机视角；
  2. 多视角扩散（如 SV3D）生成 4–16 个环绕视角，或者用前馈模型（TripoSR / InstantMesh / Hunyuan3D 2.0）直接出初版网格，先给用户一个可预览的结果。
- **离线（分钟级，异步任务）**：用多视角图像拟合 3DGS，供网页 360° 实时浏览（讲义 Production note："run a multi-view diffusion model on request, reconstruct to 3DGS asynchronously, serve the 3DGS for real-time viewing"）。
- **游戏引擎版本**：从 3DGS / 隐式场提取网格 → 重拓扑（如 voxel remesh）→ 自动 UV → 烘焙 PBR 贴图（albedo、roughness、metallic、normal），导出 glb / USDZ；或者直接调用能输出 PBR 网格的模型。
- **评估**：留出视角上的 SSIM、CLIP score、网格水密性、面数、贴图分辨率（skill 文件中的评估项）。
- **风险**：背面幻觉（见 Q16）、商品细节（logo、文字）失真、训练数据许可（Objaverse 的许可混杂，商用前要核实）。

### Q16 — 参考回答要点

- **来源**：单张图片看不到背面，模型只能根据训练数据中的先验"脑补"（讲义："Single-image → 3D has to invent the unseen side. Quality varies wildly"）。多视角扩散模型会根据同类物体的统计规律生成合理但未必真实的背面。
- **评估**：如果有真实的多视角照片，在留出视角上算 SSIM/LPIPS；没有的话做人工评审、检查对称性，用 CLIP 衡量背面与描述是否一致。
- **缓解**：让用户多拍几张（"few images"路线，如 CAT3D 支持 1–64 张输入）；对对称物体利用对称先验；用更强的多视角扩散模型；在 UI 上标注"背面为 AI 推测"；电商场景下关键角度要求实拍。
- **常见误区**：以为提高分辨率或增加高斯数量就能解决——信息缺失不是容量问题。

### Q17 — 参考回答要点

讲义 Production note 的决策树：
- **NeRF / triplane**：推理是光线步进 + 每个采样点一次 MLP 前向，512² 的渲染需要数百万次 MLP 前向。要激进地批处理光线采样点，SDPA / xformers 等高效注意力实现也适用。
- **多视角扩散 + LRM**：两段式。第一段（多视角 DiT）就是一个和第 07 节一样的扩散服务；第二段（LRM transformer）是一次前向。延迟画像是"扩散 + 一次前向"，两段分别选择合适的服务形态。
- **SDS / DreamFusion**：逐资产优化，不是推理——要做成后台任务队列（"Build jobs, not request handlers"），而不是同步请求处理器。
- **总结**：在线 GPU 推理服务负责快的部分，离线优化器负责慢的部分，3DGS 结果做成静态资产供 CDN 分发、在客户端实时渲染。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 13 3D 视觉与 NeRF](../../../04-computer-vision/13-3d-vision-nerf/docs/zh.md)：NeRF 的体渲染原理。
- [阶段 04 · 22 3D Gaussian Splatting](../../../04-computer-vision/22-3d-gaussian-splatting/docs/zh.md)：3DGS 的重建细节（投影、排序、致密化）。
- [阶段 08 · 07 潜空间扩散与 Stable Diffusion](../../07-latent-diffusion-stable-diffusion/docs/zh.md)：多视角扩散模型是从图像扩散模型微调来的。
- [阶段 01 · 05 链式法则与自动微分](../../../01-math-foundations/05-chain-rule-and-autodiff/docs/zh.md)：理解为什么要用解析梯度而不是有限差分。

### 相关小节
- [阶段 08 · 10 视频生成](../../10-video-generation/docs/zh.md)：SV3D 基于视频扩散生成环绕视角；视频的时空一致性与多视角一致性本质相通。
- [阶段 04 · 26 单目深度估计](../../../04-computer-vision/26-monocular-depth/docs/zh.md)：从单张图推断几何的另一条路线。
- [阶段 04 · 28 世界模型与视频扩散](../../../04-computer-vision/28-world-models-video-diffusion/docs/zh.md)：3D 一致的场景生成。
- [阶段 08 · 14 评估：FID、CLIP 分数、人类偏好](../../14-evaluation-fid-clip-score/docs/zh.md)：CLIP score 等指标同样用于 3D 资产评估。
- [阶段 01 · 13 数值稳定性](../../../01-math-foundations/13-numerical-stability/docs/zh.md)：Q9 中的溢出问题。

### 延伸关键词
`3D Gaussian Splatting` · `alpha compositing` · `spherical harmonics` · `densification / pruning` · `NeRF volume rendering` · `triplane` · `SDS / Janus problem` · `Zero123 / MVDream / SV3D / CAT3D` · `LRM / LGM / TripoSR / InstantMesh` · `PBR material` · `remesh / UV unwrap`
