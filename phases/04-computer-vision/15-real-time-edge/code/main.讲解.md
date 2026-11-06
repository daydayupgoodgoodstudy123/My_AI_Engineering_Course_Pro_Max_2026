# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 15 节 实时视觉——边缘部署 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数；在 CPU 上依次测 4 个模型，约需数十秒，耗时取决于机器） ｜ **依赖**：`torch`、`torchvision`（`mobilenet_v3_small`、`resnet18`、`efficientnet_v2_s`、`convnext_tiny`，均 `weights=None`，不下载权重）、标准库 `time`；无需联网
>
> 同目录另有 `main.rs`（用 Rust 标准库实现 depthwise separable 卷积并测延迟百分位），不在本讲解范围内。

---

## 1. 这份代码在考察什么

讲义的核心观点是"无法测量就无法优化"。这份代码就是一个最小的**测量工具箱**，并用它给 4 个候选 backbone 生成部署决策所需的对比表：

1. **延迟测量纪律**：`eval()` + `no_grad()`、warmup、CUDA 同步、`time.perf_counter()`、排序后取百分位。
2. **参数量**：一行生成器表达式。
3. **FLOPs 估算**：用 `register_forward_hook` 在前向时"偷看"每个 Conv/Linear 的输出形状，按公式累加；正确处理分组卷积 / depthwise 卷积。
4. **横向对比**：MobileNetV3-Small、ResNet-18、EfficientNetV2-S、ConvNeXt-Tiny 在 160×160 上的 (params, GFLOPs, p50, p95)，直观感受"FLOPs 与延迟并不成正比"。

> 一句话：**边缘部署的每个决定都应该来自一张实测的对比表**；这份代码教你怎么把表里的每一格测"对"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `measure_latency(model, input_shape, device, warmup, iters)` | 函数 | 返回 p50 / p95 / p99 / mean（毫秒） | 延迟预算、测量纪律 |
| `parameter_count(model)` | 函数 | 统计参数总数 | 模型大小 |
| `flops_estimate(model, input_shape)` | 函数 | 用 forward hook 估算 Conv2d / Linear 的 FLOPs | FLOPs 作为代理指标 |
| `compare_backbones(resolution)` | 函数 | 构造 4 个模型，逐个测参数、FLOPs、延迟 | 边缘架构选型 |
| `main()` | 入口 | 打印对齐的对比表 | 部署决策表 |

调用关系：`main → compare_backbones → (parameter_count, flops_estimate, measure_latency)`。讲义 Step 3（PTQ）和 Step 4（ONNX 导出）没有放进代码，代码只覆盖"测量"这一环。

---

## 3. 逐段精讲

### 3.1 `measure_latency`：把一个数字测"对"

```python
def measure_latency(model, input_shape, device="cpu", warmup=5, iters=20):
    model = model.to(device).eval()
    x = torch.randn(input_shape, device=device)
    with torch.no_grad():
        for _ in range(warmup):
            model(x)
        if device == "cuda":
            torch.cuda.synchronize()
        times = []
        for _ in range(iters):
            if device == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            model(x)
            if device == "cuda":
                torch.cuda.synchronize()
            times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    return {
        "p50_ms": times[len(times) // 2],
        "p95_ms": times[int(len(times) * 0.95)],
        "p99_ms": times[-1],
        "mean_ms": sum(times) / len(times),
    }
```

逐条对应讲义的"三条测量纪律"：

| 代码 | 纪律 | 为什么 |
|------|------|-------|
| `.eval()` + `torch.no_grad()` | 推理模式 | BN 用 running 统计量、Dropout 关闭；不构建计算图，省内存也更快 |
| `for _ in range(warmup)` | 1. warmup | 首次前向会触发内存分配、算子选择、缓存冷启动，数字不具代表性 |
| 前后两次 `torch.cuda.synchronize()` | 2. 同步 | CUDA kernel 异步执行；前一次同步清空队列，后一次等这次前向真正跑完 |
| 固定的 `input_shape` | 3. 固定尺寸 | 224×224 的延迟不等于 512×512 的延迟 |
| `time.perf_counter()` | 高精度计时 | 单调、高分辨率；不要用 `time.time()`（可能被系统校时打乱） |
| `times.sort()` + 下标 | 百分位 | 实时系统在长尾上出问题，均值会掩盖它 |

- 输入张量 `x` 只创建一次并直接放在目标设备上，计时只包含前向，不包含数据搬运。
- 乘以 1000 把秒换成毫秒。
- ⚠️ **百分位下标的问题**：默认 `iters=20` 时，`int(20 × 0.95) = 19`，p95 取到的是**最大值**，与 `p99 = times[-1]` 完全相同。也就是说，打印出来的 "p95" 其实是 20 次里最慢的那一次，一次偶发抖动就会让它变得很难看。按最近秩定义，p95 应取第 `⌈0.95n⌉` 小的样本（`n=20` 时为下标 18）；而且 20 个样本本来就不足以区分 p95 和 p99。skill 文件的模板默认 `iters=100`、`warmup=10`。（讲义版本 `iters=50`，p95 取下标 47、p99 取下标 49，问题较轻。）
- ⚠️ `p50` 取 `times[n // 2]`，n 为偶数时是"上中位数"，差别很小。
- ⚠️ 只处理了 `cuda` 一种需要同步的设备；在 Apple 芯片上用 `mps` 时还需要 `torch.mps.synchronize()`（skill 文件中有）。
- ⚠️ CPU 计时没有固定线程数（`torch.set_num_threads`），不同机器、不同负载下数字差异很大，需要在报告中注明。

### 3.2 `parameter_count`

```python
def parameter_count(model):
    return sum(p.numel() for p in model.parameters())
```

- `numel()` 返回张量的元素个数。`parameters()` 只包含可训练参数，不包含 BN 的 `running_mean/var` 这类 buffer。
- 参数量决定模型文件大小：FP32 下约 `params × 4` 字节，INT8 约 `params × 1` 字节。例如 ResNet-18（10 类）约 1,118 万参数，FP32 约 45 MB、INT8 约 11 MB。

### 3.3 `flops_estimate`：用 forward hook 统计计算量

```python
def flops_estimate(model, input_shape):
    total = [0]

    def conv_hook(m, inp, out):
        c_out, c_in_per_group, kh, kw = m.weight.shape
        h, w = out.shape[-2:]
        # Groups account for depthwise / grouped convs: each output channel
        # only touches c_in_per_group inputs, not all c_in.
        total[0] += 2 * c_in_per_group * c_out * kh * kw * h * w

    def linear_hook(m, inp, out):
        total[0] += 2 * m.in_features * m.out_features

    hooks = []
    for m in model.modules():
        if isinstance(m, nn.Conv2d):
            hooks.append(m.register_forward_hook(conv_hook))
        elif isinstance(m, nn.Linear):
            hooks.append(m.register_forward_hook(linear_hook))

    model.eval()
    with torch.no_grad():
        model(torch.randn(input_shape))
    for h in hooks:
        h.remove()
    return total[0]
```

- **forward hook**：`register_forward_hook(fn)` 让模块每次前向结束后调用 `fn(module, input, output)`。这样不用改模型代码，跑一次前向就能拿到每一层**实际的**输出尺寸——比手推每层的空间大小可靠得多。
- **公式**：每个输出元素需要 `c_in_per_group × kh × kw` 次乘加，一次乘加按 2 个 FLOPs 计（乘一次、加一次），乘以输出元素个数 `c_out × h × w`。
- **分组卷积**：PyTorch 的卷积权重形状是 `(out, in // groups, kh, kw)`，直接从权重读出 `c_in_per_group`，普通卷积、分组卷积、depthwise 卷积三种情况自动兼容。讲义版本把这个变量叫 `c_in`，数值相同，但代码中的新命名和注释更清楚地表达了含义。
- **`total = [0]` 而不是 `total = 0`**：嵌套函数里对外层变量做 `+=` 会被当成赋值局部变量，从而抛出 `UnboundLocalError`。讲义用 `nonlocal total` 解决；代码改用"可变容器"技巧：修改列表的元素不算重新绑定变量名，所以不需要 `nonlocal`。两种写法都对。
- **用完要 `remove()`**：hook 会一直挂在模型上，不移除的话，之后 `measure_latency` 的每次前向都会白白执行 hook，拖慢测量结果。这里在测延迟之前就把它们全部移除了，顺序正确。
- ⚠️ **`linear_hook` 的 bug**：它假设 `nn.Linear` 只作用于一个向量。torchvision 的 ConvNeXt block 把特征图 `permute` 成 `(N, H, W, C)`，再用 `nn.Linear` 做逐点 MLP——这时 Linear 在 `H × W` 个位置上各算一次，而 hook 只算了一次。按结构逐层计算，160×160 输入下这个估算器给 `convnext_tiny` 的结果约 0.35 GFLOPs，真实值约 4.55 GFLOPs，被低估了约 13 倍。修复：

  ```python
  def linear_hook(m, inp, out):
      positions = out.numel() // out.shape[-1]
      total[0] += 2 * m.in_features * m.out_features * positions
  ```

  （对 MobileNet / ResNet / EfficientNet 末尾的分类头，`positions = 1`，结果不变。）
- ⚠️ `conv_hook` 没有乘 batch 大小（`out.shape[0]`），`input_shape` 的 batch 不是 1 时会少算。
- ⚠️ 只统计 Conv2d 和 Linear，忽略 BN、激活、池化、逐元素加法和 attention 的矩阵乘——这些 FLOPs 不多，但访存开销可能不小。生产中用 `fvcore` 或 `ptflops`（讲义推荐）。
- `model(torch.randn(input_shape))` 没有指定 device，所以要求模型在 CPU 上。`compare_backbones` 中先调用 `flops_estimate`、后调用 `measure_latency`，此时模型确实还在 CPU 上。

### 3.4 `compare_backbones`：生成决策表

```python
def compare_backbones(resolution=160):
    from torchvision.models import (
        mobilenet_v3_small, resnet18, efficientnet_v2_s, convnext_tiny,
    )
    candidates = [
        ("mobilenet_v3_small", mobilenet_v3_small(weights=None, num_classes=10)),
        ("resnet18", resnet18(weights=None, num_classes=10)),
        ("efficientnet_v2_s", efficientnet_v2_s(weights=None, num_classes=10)),
        ("convnext_tiny", convnext_tiny(weights=None, num_classes=10)),
    ]
    shape = (1, 3, resolution, resolution)
    results = []
    for name, model in candidates:
        params = parameter_count(model)
        flops = flops_estimate(model, shape)
        lat = measure_latency(model, shape, device="cpu")
        results.append({
            "model": name, "params_m": params / 1e6,
            "gflops": flops / 1e9,
            "p50_ms": lat["p50_ms"],
            "p95_ms": lat["p95_ms"],
        })
    return results
```

- **函数内 `import`**：只有真正调用对比时才导入 torchvision，`measure_latency` 等工具函数可以在没有 torchvision 的环境里单独复用。
- **`weights=None`**：随机初始化。延迟和 FLOPs 只取决于结构，与权重值无关，所以不需要下载预训练权重。⚠️ 但随机权重测不了精度，真实决策表还需要精度这一列（以及峰值内存，讲义的"三个预算"之一）。
- **160×160 而不是 224×224**：为了让 4 个模型在 CPU 上快速跑完。计算量约为 224 时的 `(160/224)² ≈ 51%`。
- **batch = 1**：边缘端实时推理的典型场景——一帧来了就要马上出结果，没有攒 batch 的余地。
- 每个结果是一个字典，`params / 1e6` 换算成"百万"，`flops / 1e9` 换算成 GFLOPs。

### 3.5 `main()`：对齐打印

```python
    header = f"{'model':22s} {'params(M)':>10s} {'GFLOPs':>8s} {'p50(ms)':>9s} {'p95(ms)':>9s}"
    print(header)
    print("-" * len(header))
    for r in compare_backbones(resolution=160):
        print(f"{r['model']:22s} {r['params_m']:>10.2f} {r['gflops']:>8.2f} "
              f"{r['p50_ms']:>9.1f} {r['p95_ms']:>9.1f}")
```

- f-string 格式说明符：`:22s` 左对齐占 22 格；`:>10s` 右对齐；`:>10.2f` 右对齐、保留 2 位小数。表头和数据行使用相同的宽度，列就能对齐。
- `"-" * len(header)` 用字符串乘法画一条与表头等长的分隔线。
- 两段相邻的 f-string 字面量会被 Python 自动拼接（隐式字符串连接），用来把长行拆开。
- `torch.manual_seed(0)` 让随机初始化和随机输入可复现；但延迟本身受机器状态影响，每次运行都会有波动。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| warmup 5 次、计时 20 次 | 4 个模型在 CPU 上能较快跑完 | 百分位不可靠（p95 = p99 = 最大值）；生产中用 ≥100 次迭代、10 次以上 warmup |
| 只在 `cuda` 上同步 | 覆盖最常见的 GPU 情况 | `mps` 等设备也需要同步；skill 文件中有通用的 `sync()` |
| 用 forward hook 统计 FLOPs | 不改模型代码，自动拿到真实形状 | 只覆盖 Conv2d / Linear，且 Linear 的多位置计算有 bug；生产中用 `fvcore` / `ptflops` |
| `weights=None` | 不联网，测速与权重值无关 | 不能得到精度列 |
| 160×160、batch 1 | 速度快，贴近边缘实时场景 | 部署时必须用生产分辨率重测 |
| 在开发机 CPU 上用 PyTorch eager 测 | 零配置即可运行 | 讲义强调"每一格都要在目标设备上测"；eager 模式也不是部署运行时，应再测 ONNX Runtime / TensorRT / TFLite |
| 没有内存测量 | 保持代码简短 | skill 文件用 `torch.cuda.max_memory_allocated` 和 `psutil` RSS 补齐 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def measure_latency(model, input_shape, device="cpu", warmup=5, iters=20)` | 调用时可以只传前两个参数 |
| `for _ in range(n)` | `for _ in range(warmup): model(x)` | `_` 表示不需要使用循环变量 |
| 列表 `sort()` | `times.sort()` | 原地升序排序，返回 `None` |
| 下标与负数下标 | `times[len(times) // 2]`、`times[-1]` | `//` 整除得到下标；`-1` 表示最后一个 |
| `int()` 截断 | `int(len(times) * 0.95)` | 向零取整：`int(19.0) = 19` |
| 字典字面量 | `{"p50_ms": ..., "p95_ms": ...}` | 用键名返回多个结果，比元组更清晰 |
| 生成器表达式 | `sum(p.numel() for p in model.parameters())` | 不建中间列表 |
| 嵌套函数（闭包） | `def conv_hook(m, inp, out): ... total[0] += ...` | 内层函数可以读取外层变量 |
| 可变容器绕过 `nonlocal` | `total = [0]`、`total[0] += ...` | 修改列表元素不算重新绑定变量，无需 `nonlocal` |
| 元组解包 | `c_out, c_in_per_group, kh, kw = m.weight.shape`、`h, w = out.shape[-2:]` | 一次取多个维度 |
| `isinstance` 分派 | `if isinstance(m, nn.Conv2d): ... elif isinstance(m, nn.Linear): ...` | 按类型注册不同的 hook |
| 函数作为参数 | `m.register_forward_hook(conv_hook)` | 把函数对象传进去，由框架在合适的时机回调 |
| 函数内 `import` 与多行导入 | `from torchvision.models import (mobilenet_v3_small, ...)` | 括号内可以换行；放在函数里实现延迟导入 |
| 元组列表遍历 | `for name, model in candidates:` | 每个元素是 `(名字, 模型)`，直接解包 |
| `with` 上下文管理器 | `with torch.no_grad():` | 代码块内关闭梯度 |
| 科学计数法字面量 | `params / 1e6`、`flops / 1e9` | `1e6` 即 1,000,000（浮点数） |
| f-string 对齐格式 | `{'model':22s}`、`{r['p50_ms']:>9.1f}` | 宽度、对齐方向（`>` 右对齐）、小数位数 |
| 字符串乘法 | `"-" * len(header)` | 重复字符串 |
| 隐式字符串拼接 | `f"..." f"..."` 写在两行 | 相邻的字符串字面量会被自动连接 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch` / `torchvision`）。** 下面的参数量由 torchvision 官方公布的参数数（MobileNetV3-Small 2,542,856、ResNet-18 11,689,512、EfficientNetV2-S 21,458,488、ConvNeXt-Tiny 28,589,128）换算到 10 类分类头得到；GFLOPs 是按各模型结构、用与代码相同的计数规则逐层推算的结果（推算出的 224 分辨率 MAC 数与 torchvision 公布的计算量吻合）。延迟取决于你的 CPU，无法预知，表中以"…"表示：

```text
Comparing edge backbones on CPU at 160x160:

model                   params(M)   GFLOPs   p50(ms)   p95(ms)
--------------------------------------------------------------
mobilenet_v3_small           1.53     0.06         …         …
resnet18                    11.18     1.85         …         …
efficientnet_v2_s           20.19     2.91         …         …
convnext_tiny               27.83     0.35         …         …
```

逐行解读：

- **params(M)**：10 类分类头替换了原来的 1000 类头，所以比官方数字略小（例如 ResNet-18：11.69M − 0.513M + 0.005M = 11.18M）。
- **mobilenet_v3_small 0.06 GFLOPs**：depthwise separable + 极窄的通道数，计算量只有 ResNet-18 的约 1/30。
- **resnet18 1.85 GFLOPs**：224 分辨率下约 1.81 GMAC，160 分辨率时乘以 0.51，再按"1 MAC = 2 FLOPs"计，得到约 1.85。
- **convnext_tiny 0.35**：⚠️ 这是估算器 bug 造成的假象（见 3.3），真实值约 4.55 GFLOPs，是四者中最大的。如果直接拿这张表做决策，会误以为 ConvNeXt-Tiny 的计算量只有 ResNet-18 的 1/5。
- **延迟列**：p50 一般会大致随真实计算量升高，但**不成比例**。例如 MobileNetV3-Small 的 FLOPs 只有 ResNet-18 的约 1/30，在 PyTorch eager CPU 上的速度差距通常远小于 30 倍——depthwise 卷积访存受限、层数多、kernel 调度开销大。这正是讲义"FLOPs 是代理，部署看实测"的现场演示。
- **p95 列**：由于 `iters=20`，它其实是 20 次中的最大值，可能明显高于 p50；多跑几次会发现这一列波动最大。

---

## 7. 动手改一改

1. **修正百分位**：实现最近秩 `pct(times, p)`，把 `iters` 提高到 100，同时输出 p90 / p95 / p99 和标准差，观察 p95 与 p99 是否终于分开。
2. **修复 FLOPs 估算器**：按 3.3 修改 `linear_hook`，并在 `conv_hook` 中乘上 batch 大小；重新打印 `convnext_tiny` 的 GFLOPs，确认约为 4.5。
3. **加内存列**：参考 skill 文件，用 `psutil.Process().memory_info().rss` 记录前向前后的 RSS 差值（或在 GPU 上用 `torch.cuda.max_memory_allocated()`）。
4. **固定线程数**：分别在 `torch.set_num_threads(1)` 和 `4` 下运行，比较 MobileNet 和 ResNet 的加速比，体会"小模型难以吃满多核"。
5. **batch 扫描**：对 `batch_size ∈ {1, 4, 16}` 测延迟，计算吞吐量（图/秒），画出延迟—吞吐曲线。
6. **（进阶）讲义练习 3**：把 `convnext_tiny` 导出为 ONNX，用 `onnxruntime` 的 `CPUExecutionProvider` 测延迟，与 PyTorch eager 对比。

---

## 8. 常见坑

- **样本太少却报 p99**：20 次迭代的 p95/p99 就是最大值，结论被一次抖动左右。
- **hook 忘记移除**：后续所有前向都会执行 hook，测出的延迟偏大；用 `try/finally` 保证移除更稳妥。
- **`nonlocal` / 可变容器混淆**：嵌套函数里直接写 `total += x` 会抛 `UnboundLocalError`。
- **用 FLOPs 代替实测延迟做决策**：FLOPs 估算本身还可能漏算（Linear 的多位置计算、attention 的矩阵乘）。
- **在开发机上测完就下结论**：x86 CPU、PyTorch eager 的数字与手机 NPU、TFLite 上的数字可能完全不同，排名都可能颠倒。
- **GPU 计时不同步**：测出的只是 kernel 下发时间，数字好看但毫无意义。
