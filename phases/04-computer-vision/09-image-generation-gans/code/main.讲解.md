# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 09 节 图像生成 — GANs ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数；有 GPU 自动用 `cuda`） ｜ **依赖**：`numpy`、`torch`（`torch.nn`、`torch.nn.functional`、`torch.utils.data`、`torch.nn.utils.spectral_norm`）；无需联网

---

## 1. 这份代码在考察什么

一个可以在 CPU 上几分钟内跑完的最小 DCGAN：在 400 张"黑底彩色圆"的合成图上训练 5 个 epoch。

1. **DCGAN 的两个网络**：生成器用转置卷积把 64 维噪声"放大"成 32×32 图像；判别器用带步长卷积把图像"压缩"成一个 logit。
2. **对抗训练的标准步**：先更新 D（真图标 1、假图标 0，假图 `detach`），再更新 G（非饱和损失：让 D 把假图判成 1）。
3. **谱归一化**：用一个开关 `use_sn` 在"BN 判别器"和"SN 判别器"之间切换。
4. **采样的正确姿势**：`eval()` → 生成 → `train()`，以及 tanh 输出到 [0,1] 的映射。
5. **读损失曲线**：GAN 的损失不会单调下降，要会看"健康"的数值范围。

> 一句话：**GAN = 一个画家 + 一个鉴定师轮流进步**；这份代码把这场博弈落到最少的几十行 PyTorch 上。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Generator` | `nn.Module` | `z (B,64)` → `(B,3,32,32)`，4 个转置卷积 + BN + ReLU，输出 tanh | 生成器 / DCGAN 规则 |
| `Discriminator` | `nn.Module` | `(B,3,32,32)` → `(B,)` logit；`use_sn` 决定用谱归一化还是 BN | 判别器 / 谱归一化 |
| `train_step` | 函数 | 一次 D 更新 + 一次 G 更新，返回两个损失 | 交替训练、非饱和损失 |
| `synthetic_circles` | 函数 | 生成 `[-1,1]` 范围的"黑底随机彩色圆"数据 | 合成数据 |
| `sample` | 函数（`@torch.no_grad()`） | 生成 n 张图并映射到 [0,1] | 采样 |
| `main()` | 演示入口 | 构建 G、SN 判别器、两个 Adam，训练 5 个 epoch，最后采样 | 训练循环 |

数据流：`synthetic_circles → TensorDataset → DataLoader → (batch,)`；每个 batch 采一次噪声 `z`，`train_step(G, D, batch, z, ...)` 依次更新 D 和 G；训练结束后 `sample(G)`。

---

## 3. 逐段精讲

### 3.1 `Generator`：从 1×1 噪声"长"出 32×32 图像

```python
class Generator(nn.Module):
    def __init__(self, z_dim=64, img_channels=3, feat=32):
        super().__init__()
        self.net = nn.Sequential(
            nn.ConvTranspose2d(z_dim, feat * 4, 4, 1, 0, bias=False),
            nn.BatchNorm2d(feat * 4),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(feat * 4, feat * 2, 4, 2, 1, bias=False),
            nn.BatchNorm2d(feat * 2),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(feat * 2, feat, 4, 2, 1, bias=False),
            nn.BatchNorm2d(feat),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(feat, img_channels, 4, 2, 1, bias=False),
            nn.Tanh(),
        )

    def forward(self, z):
        return self.net(z.view(z.size(0), -1, 1, 1))
```

- `z.view(z.size(0), -1, 1, 1)`：把 `(B, 64)` 的噪声变成 `(B, 64, 1, 1)`——一张 1×1、64 通道的"图"，这样就能全程用卷积，符合 DCGAN"去掉全连接层"的规则。`-1` 让 PyTorch 自动推断这一维是 64。
- 转置卷积尺寸公式 `H_out = (H_in − 1)·s − 2p + k`：
  - 第 1 层 `(k=4, s=1, p=0)`：`1 → 4`，本质上是一个把噪声投影成 4×4 特征图的全连接层；
  - 后 3 层 `(k=4, s=2, p=1)`：`4 → 8 → 16 → 32`，每层翻倍。
  - 通道 `128 → 64 → 32 → 3`，空间变大、通道变小，与判别器镜像对称。
- `kernel=4, stride=2`：kernel 能被 stride 整除，每个输出像素收到的输入贡献次数均匀，避免了第 07 节讲过的棋盘格伪影。
- **DCGAN 规则对照**：中间层 BN + ReLU；输出层不加 BN、用 `Tanh` 把像素压到 `[-1, 1]`（所以训练数据也必须是 `[-1, 1]`）。
- `bias=False`：后面紧跟 BN 时偏置会被 BN 的去均值抵消；最后一层后面没有 BN，这里也去掉了 bias，影响很小（tanh 前少一个常数偏移）。
- 参数量：`131,072 + 131,072 + 32,768 + 1,536`（四个转置卷积）`+ 448`（三个 BN）`= 296,896`。

### 3.2 `Discriminator`：一个开关切换 BN / 谱归一化

```python
class Discriminator(nn.Module):
    def __init__(self, img_channels=3, feat=32, use_sn=False):
        super().__init__()
        layers = []
        def conv(in_c, out_c, bn):
            c = nn.Conv2d(in_c, out_c, 4, 2, 1, bias=not bn)
            if use_sn:
                c = spectral_norm(c)
            layers.append(c)
            if bn and not use_sn:
                layers.append(nn.BatchNorm2d(out_c))
            layers.append(nn.LeakyReLU(0.2, inplace=True))

        conv(img_channels, feat, bn=False)
        conv(feat, feat * 2, bn=True)
        conv(feat * 2, feat * 4, bn=True)
        last = nn.Conv2d(feat * 4, 1, 4, 1, 0)
        layers.append(spectral_norm(last) if use_sn else last)
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).view(-1)
```

- **嵌套函数 + 闭包**：`conv` 定义在 `__init__` 里面，可以直接读写外层的 `layers` 列表和 `use_sn` 参数，不用每次传参——这是"闭包"的典型用法，让搭网络的代码很短。
- 空间尺寸：`32 → 16 → 8 → 4`（三个 `k=4, s=2, p=1` 的卷积），最后 `Conv2d(128, 1, 4, 1, 0)` 把 4×4 压成 1×1，`.view(-1)` 展平为 `(B,)`——每张图一个 logit。
- **DCGAN 规则对照**：第一层（D 的输入层）不加 BN；全部用 `LeakyReLU(0.2)`；没有池化、没有全连接；最后**不加 sigmoid**，输出原始 logit，交给 `binary_cross_entropy_with_logits`（讲义："apply sigmoid only during loss computation"）。
- **谱归一化**：`spectral_norm(c)` 给卷积层挂一个钩子，每次前向前用幂迭代估计权重矩阵的最大奇异值 σ，用 `W/σ` 代替 `W`。逐层把放大倍数限制在约 1，D 就不能变得任意陡峭，缓解"D 完胜"。SN 打开时不再加 BN（讲义 Step 6："A drop-in replacement for BN in the discriminator"）。
- `nn.Sequential(*layers)`：`*` 把列表展开成多个位置参数。
- ⚠️ **小瑕疵**：`bias=not bn` 只看了 `bn`，没看 `use_sn`。`use_sn=True` 时第 2、3 层既没有 BN 也没有 bias。更合理的写法是 `use_bn = bn and not use_sn; bias=not use_bn`（测验 Q10），讲义的 `build_sn_discriminator` 也是保留 bias 的。按原代码，SN 判别器的参数量为 `1,568 + 32,768 + 131,072 + 2,049 = 167,457`。

### 3.3 `train_step`：一次 D 更新 + 一次 G 更新

```python
def train_step(G, D, real, z, opt_g, opt_d, device):
    real = real.to(device)

    opt_d.zero_grad()
    d_real = D(real)
    d_fake = D(G(z).detach())
    loss_d = (F.binary_cross_entropy_with_logits(d_real, torch.ones_like(d_real))
              + F.binary_cross_entropy_with_logits(d_fake, torch.zeros_like(d_fake)))
    loss_d.backward()
    opt_d.step()

    opt_g.zero_grad()
    d_fake = D(G(z))
    loss_g = F.binary_cross_entropy_with_logits(d_fake, torch.ones_like(d_fake))
    loss_g.backward()
    opt_g.step()

    return loss_d.item(), loss_g.item()
```

与讲义公式逐行对应：

| 代码 | 公式 |
|------|------|
| `BCE(d_real, 1)` | `−E_x[log D(x)]` |
| `BCE(d_fake, 0)` | `−E_z[log(1 − D(G(z)))]` |
| `loss_d` = 两者之和 | `L_D` |
| `BCE(D(G(z)), 1)` | `L_G = −E_z[log D(G(z))]`（非饱和） |

- **非饱和损失的实现方式**：G 步把假图的目标标签设成 **1**（"让 D 把它当真图"），BCE 就变成 `−log D(G(z))`，而不是去最小化 `log(1 − D(G(z)))`。
- `torch.ones_like(d_real)`：生成与 `d_real` 同形状、同设备、同 dtype 的全 1 张量，省去手动指定 device。
- `G(z).detach()`：把假图从 G 的计算图上切下来，D 的损失不会反传进 G。在本文件的写法里（G 步之前有 `opt_g.zero_grad()`），去掉 `detach` 只会浪费一次穿过 G 的反向传播；但在"每轮开头统一清零"或"复用同一份 fake"的写法里，D 步留下的梯度方向与 G 的目标相反，会直接污染 G 的更新（测验 Q9）。
- G 步重新算了一次 `D(G(z))`：此时 D 已经更新过，G 拿到的是"新 D"的反馈；注意 G 步的反向传播也会经过 D，为 D 的参数算出梯度，但下一轮 D 步开头的 `opt_d.zero_grad()` 会清掉它们，`opt_g.step()` 也只更新 G。
- D 步和 G 步用的是同一个 `z`，都会让 G 里的 BN 在训练模式下更新一次 running stats。
- `.item()` 把 0 维张量转成 Python 浮点数，返回值不再持有计算图。

### 3.4 `synthetic_circles`：[-1, 1] 范围的数据

```python
def synthetic_circles(num=800, size=32, seed=0):
    rng = np.random.default_rng(seed)
    imgs = np.full((num, 3, size, size), -1.0, dtype=np.float32)
    yy, xx = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    for i in range(num):
        r = rng.uniform(6, 10)
        cx, cy = rng.uniform(r, size - r, size=2)
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 < r ** 2
        color = rng.uniform(-0.3, 1.0, size=3)
        for c in range(3):
            imgs[i, c][mask] = color[c]
    return torch.from_numpy(imgs)
```

- `np.full(..., -1.0)`：背景全部是 −1，即 tanh 范围里的"纯黑"。数据范围必须与 G 的输出范围 `[-1, 1]` 一致，否则 D 只看像素范围就能分辨真假。
- 圆的半径 6–10 像素、圆心保证整个圆在图内（`uniform(r, size - r)`）、颜色每个通道在 `[-0.3, 1.0]` 中随机——所以真实分布是"位置、大小、颜色三维连续变化的圆"，是检查模式崩溃的好例子：如果生成的圆全是同一位置同一颜色，就是崩溃了。
- 直接生成 `(N, C, H, W)` 布局，不需要再 `permute`。
- 讲义版本把 `meshgrid` 放在循环里，这里提到循环外只算一次。

### 3.5 `sample`：采样的正确姿势

```python
@torch.no_grad()
def sample(G, n=8, z_dim=64, device="cpu"):
    G.eval()
    z = torch.randn(n, z_dim, device=device)
    out = G(z)
    G.train()
    return ((out + 1) / 2).clamp(0, 1)
```

- `@torch.no_grad()`：采样不需要梯度，省显存。
- `G.eval()`：BN 改用训练时积累的 running mean/var，而不是当前这 8 张图的 batch 统计量——讲义强调"Always switch to eval mode before sampling"。
- `G.train()`：采样后**恢复训练模式**，这样在训练循环中途调用 `sample` 也不会把后续训练搞成 eval 模式（讲义版本缺少这一行）。
- `(out + 1) / 2`：把 `[-1, 1]` 映射到 `[0, 1]`，再 `clamp` 防止数值越界，便于保存成图片。

### 3.6 `main()`：组装与训练

```python
    data = synthetic_circles(num=400)
    loader = DataLoader(TensorDataset(data), batch_size=32, shuffle=True)

    G = Generator(z_dim=z_dim, img_channels=3, feat=32).to(device)
    D = Discriminator(img_channels=3, feat=32, use_sn=True).to(device)
    opt_g = torch.optim.Adam(G.parameters(), lr=2e-4, betas=(0.5, 0.999))
    opt_d = torch.optim.Adam(D.parameters(), lr=2e-4, betas=(0.5, 0.999))
    # ...
    for epoch in range(5):
        ld_sum, lg_sum, n = 0.0, 0.0, 0
        for (batch,) in loader:
            z = torch.randn(batch.size(0), z_dim, device=device)
            ld, lg = train_step(G, D, batch, z, opt_g, opt_d, device)
            # ...
        print(f"epoch {epoch}  D {ld_sum/n:.3f}  G {lg_sum/n:.3f}")
```

- `TensorDataset(data)` 每次返回一个**只含一个元素的元组** `(tensor,)`，所以循环写成 `for (batch,) in loader`——这是单元素元组解包，少了逗号就会拿到一个元组而不是张量。
- 400 张图、batch 32 → 每个 epoch 13 个 batch（最后一个 16 张）。`z` 的 batch 维跟随真实 batch 大小。
- 默认用 SN 判别器（`use_sn=True`），两个优化器都是 DCGAN 默认 `lr=2e-4, β1=0.5`，没有用 TTUR——讲义说换上 SN 后往往不需要 TTUR。
- 每个 epoch 打印**平均**损失（讲义版本只打印最后一个 batch 的损失，噪声更大）。
- ⚠️ 规模刻意很小（400 张、5 个 epoch），只为验证管道能跑通；要看到清晰的圆，需要更多 epoch（讲义练习 1）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 全卷积、无全连接、无池化 | DCGAN 规则，训练更稳定 | 分辨率高时需要更多层或渐进式结构（StyleGAN） |
| G 输出 tanh、数据缩放到 [-1,1] | 输出范围有界、与数据对齐 | 保存图像时需要映射回 [0,1] |
| D 输出 logit + `BCE_with_logits` | 数值稳定，避免 `log(0)` | — |
| 非饱和 G 损失（目标标签设 1） | 训练初期 G 也有大梯度 | 仍可能 D 完胜，可换 hinge / WGAN-GP |
| `use_sn` 开关 | 一份代码对比 BN 与 SN | 原实现开 SN 时丢了 bias |
| D、G 同学习率 `2e-4` | SN 已经稳定 D | 不稳定时可上 TTUR |
| `sample` 里 eval/train 切换 | BN 用 running stats，且不破坏训练状态 | — |
| 小数据、5 个 epoch | 几分钟跑完 | 真实训练需要 FID 监控与大量迭代 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 多重赋值 | `ld_sum, lg_sum, n = 0.0, 0.0, 0` | 一行初始化多个变量 |
| 增量赋值 | `ld_sum += ld` | 等价于 `ld_sum = ld_sum + ld` |
| 单元素元组解包 | `for (batch,) in loader` | `TensorDataset` 返回 `(tensor,)`，用 `(batch,)` 取出唯一元素 |
| 条件表达式 | `spectral_norm(last) if use_sn else last` | `a if 条件 else b` |
| 嵌套函数 / 闭包 | `__init__` 里的 `def conv(in_c, out_c, bn)` | 内部函数能访问外层的 `layers`、`use_sn` |
| `*` 展开列表 | `nn.Sequential(*layers)` | 把列表元素作为多个位置参数传入 |
| `not` 布尔取反 | `bias=not bn` | 布尔值作为关键字参数 |
| 位置参数简写 | `nn.ConvTranspose2d(z_dim, feat * 4, 4, 1, 0, bias=False)` | 依次是 in、out、kernel、stride、padding |
| 类继承 + `super()` | `class Generator(nn.Module)` | 继承 PyTorch 模块 |
| 装饰器 | `@torch.no_grad()` | 给整个函数关闭梯度 |
| f-string 格式符 | `f"{ld_sum/n:.3f}"`、`f"{sum(...):,}"` | 3 位小数；千分位分隔 |
| 生成器表达式 | `sum(p.numel() for p in G.parameters())` | 统计参数量 |
| `if __name__ == "__main__":` | 文件末尾 | 只有直接运行时才执行 `main()` |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 参数量是由结构决定的确定值，其余为根据代码推出的预期：

```text
G params: 296,896
D params: 167,457
epoch 0  D 1.xxx  G 0.xxx
epoch 1  D ...    G ...
epoch 2  D ...    G ...
epoch 3  D ...    G ...
epoch 4  D ...    G ...
generated shape: (8, 3, 32, 32)  range [0.xx, 0.xx]
```

逐行解读：

- `G params: 296,896`、`D params: 167,457`：生成器比判别器大，这是 DCGAN 的常见比例；`spectral_norm` 只把 `weight` 改名为 `weight_orig`、另加两个 buffer，不改变参数数量。
- **损失的参照值**：D 输出 0.5 时 `loss_d = 2·ln2 ≈ 1.386`、`loss_g = ln2 ≈ 0.693`。初始化阶段两者都在这附近。健康的训练里两个损失会在这附近来回波动，而不是单调下降：
  - D 损失稳定在 1.0–1.4、G 损失在 0.7–2 之间波动 → 博弈正常；
  - D 损失一路降到接近 0、G 损失持续升高 → D 完胜（讲义的失败模式 2）；
  - 两个损失剧烈摆动且没有任何趋势 → 振荡。
- `generated shape: (8, 3, 32, 32)`：8 张 32×32 的 RGB 图。`range` 一定落在 `[0, 1]` 内（tanh 映射 + clamp）。如果最小值接近 0（对应 tanh 的 −1，即"黑色背景"），说明 G 至少学会了背景；要判断有没有学会"圆"，必须把样本保存成图片肉眼看——讲义说这一步"Non-negotiable"。
- 5 个 epoch 只有 65 次更新，样本大概率还只是模糊色块；这是规模问题，不是代码问题。

---

## 7. 动手改一改

1. 每个 epoch 结束用**固定的一组 z** 调用 `sample`，用 `torchvision.utils.save_image` 或 matplotlib 存成 4×4 网格，观察圆从第几个 epoch 开始成形（讲义练习 1）。
2. 修正 `Discriminator` 的 bias 问题，并分别用 `use_sn=False` / `True` 训练三个随机种子，比较损失曲线的方差（讲义练习 2）。
3. 把 G 步改成饱和形式 `loss_g = -F.binary_cross_entropy_with_logits(d_fake, torch.zeros_like(d_fake))`（即最小化 `log(1 − D(G(z)))`），对比前几百步 G 的梯度范数。
4. 实现 one-sided 标签平滑（真实标签 0.9）和 TTUR（D 4e-4、G 1e-4），观察对曲线的影响（测验 Q11）。
5. 写一个简单的模式崩溃检测：对 64 个生成样本计算两两像素距离的平均值，与真实数据的同一统计量对比。
6. 实现条件 DCGAN：把 one-hot 类别拼接到噪声上、在 D 里加一个类别 embedding 通道，用第 07 节的"圆 vs 方"数据训练（讲义练习 3）。

---

## 8. 常见坑

- **数据范围与 tanh 不匹配**：数据在 [0,1]、G 输出在 [-1,1]，D 只看亮度就能区分真假，G 永远学不好。
- **D 末尾加了 sigmoid 又用 `BCE_with_logits`**：相当于 sigmoid 两次，梯度很小。
- **忘记 `detach` 且清零位置不对**：D 步的梯度会以相反方向污染 G。
- **采样时忘了 `eval()`**：小 batch 的 BN 统计量很抖，样本质量看起来比实际差；采样后忘了 `train()` 又会让后续训练出错。
- **把损失下降当成训练成功**：GAN 的损失不是质量指标，一定要看样本、看 FID。
- **谱归一化层的 bias / BN 搭配**：去掉 BN 后要把 bias 加回来（本文件的小瑕疵）。
