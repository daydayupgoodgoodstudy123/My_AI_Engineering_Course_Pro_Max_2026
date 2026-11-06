<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="gradient-checkpointing-and-activation-recomputation"></a>

# Gradient Checkpointing 与激活重计算

> 后螺旋保持每个中间激活。 70B parameters 和 128K 的上下文是每排3个激活的肺结核。 校验用 FLOP 来交换内存: 重新计算而不是保存 。 问题是要下降哪些部分, 答案不是“ 全部 ” 。

**类型:** Build
**语言:** Python (与 numpy,可选火炬)
**先修要求:** 第10阶段 04课程(培训前GPT第10阶段第05课(扩大和分配)
**时间:** ~70分钟

<a id="the-problem"></a>

## 问题

培训a transformer 存储每一层的每个以后向方式区分的活动的投入: attention 投入、Q/K/V预测、 softmax 输出、 FFFN 输入、 规范输出和剩余流。 对于隐藏大小的层 `d`序列长度 `L`,批量 `B`,这是在 `12 * B * L * d` 每个层的浮点数。

用于 `d=8192, L=8192, B=1`,在 BF16 中为800 MB/lay。64 级模型是51GB 激活, 这是在您添加前以微批量大小乘法 attention-softmax 中间体(`L^2` 以每头为单位),在你们之前, tensor- 平行部分副本。

双面法案:BF16 weights plus optimizer 状态可能适合80GB, 但激活会推动你过去。 Gradient 检查( 自动激活的重新计算) 是标准设置 。 大部分的启用都放下; 在后退时重做, 以收回它们 。 成本: 额外的 FLOPs 。 好处: 内存会下降 checkpoint 分层至总层。

如此简单,检查费用每步大约要高出33%的远足FLOPs。 做好了,根据Korthikati等人的“聪明选择”有选择地进行检查,为不到5%的FLOP管理费节省了5x内存。 FSDP卸载了FP8 matmuls, FSDP 卸载了和专家平行。 MoE 这真的很重要: 你负担不起记忆 或浪费的计算。

<a id="the-concept"></a>

## 概念

<a id="what-backward-actually-needs"></a>

### 后退需要什么

`output = layer(input)`. 后退要求 `grad_input` 和 `grad_params`为了计算它们,它需要:

- `input` (计算) `grad_params = input.T @ grad_output` 线性层)
- 某些激活衍生物中间体( ReLU/GELU/softmax 取决于激活值)

该 forward pass 自动存储在 autograd 图表。 `tensor.retain_grad()` 每一个需要投入的作业 都保留一个参考。

<a id="naive-full-checkpointing"></a>

### 原始全面检查

将网络分割成 `N` 片段。 在前方, 只存储 *输入* 当后向需要中间线时, 重新运行该段的 forward pass 以便他们悔悟,而加以区别。

示例:32层 transformer 分成32个区段,各1层。

- 内存:32层输入(小)与32 * (每层活性体积)(大)
- 额外计算:每段增加1个前进点,即前进点总长度为33%以上(因为向后是2x,整步变为1+1+2=4单位,而不是1+2=3)。

这是陈等人2016年的原始食谱:一 checkpoint 每个 `sqrt(L)` 平衡内存和计算。 L=64, 也就是 8 checkpoints.

<a id="selective-checkpointing-korthikanti-2022"></a>

### 选择性检查(Korthikanti 2022)

并非所有的启动成本都一样。 attention softmax 输出为 `B*L*L*heads` 成长 *quadratically* 与序列长度。 FFFN 隐藏的激活 `B*L*4d` 并且长长的线性生长 softmax 统治者。

选择性检查站使廉价到储存的激活(线性预测、剩余物)得以保持,并且只对昂贵的引爆装置进行重新计算(attention。您只需支付最小的 FLOPs 来重新计算,但保存 O(L% 2) 内存。

威震天- 核心执行此功能作为“ 选择性” 激活回调。 大部分 2024 + 边框训练都使用 。

<a id="offload"></a>

### Offload

重新计算的替代办法:船舶激活 CPU 前向和后向之间的内存。 需要 PCIe 带宽; 当闲置带宽超过再物质化成本时有用 。 混合策略很常见 : checkpoint 一些层,卸载其他。

FSDP2 船舶作为头等舱卸载选项。 GPU 在记忆中被卡住了,但 CPU-GPU 调职有主教室

<a id="recompute-cost-model"></a>

### 重新计算成本模型

一步一步的FLOPs,天真地检查每个 `k` 层外 `L`:

```
flops_fwd_normal = L * f_layer
flops_bwd_normal = 2 * L * f_layer
flops_total_normal = 3 * L * f_layer

flops_fwd_ckpt = L * f_layer
flops_recompute = L * f_layer  # one extra forward per layer in the segment
flops_bwd_ckpt = 2 * L * f_layer
flops_total_ckpt = 4 * L * f_layer
overhead = 4 / 3 - 1 = 0.33 = 33%
```

选择检查时,您只重新计算 attention 内核,不是整个层:

```
flops_recompute_selective = L * f_attention ~= L * f_layer * 0.15
overhead_selective = (3 + 0.15) / 3 - 1 = 0.05 = 5%
```

<a id="memory-savings-model"></a>

### 内存存储模式

每层激活量 : `A`. 用于 `L` 层, 全部激活内存 : `L * A`.

Full checkpoint (部分大小1):仅存储 `L * input_volume` (~`L * 1/10 A` 标准 transformer)保存 ~`9 * L * A * 1/10`.

Checkpoint 每个 `k` 层: 存储 `L/k * A` plus `k-1` 在活动区段内值多少层 。

在 `k = sqrt(L)`,内存和重新计算两个比例尺的成本 `sqrt(L)` 统一成本层次的最佳取舍。

<a id="when-not-to-checkpoint"></a>

### 何时不 Checkpoint

- 管道阶段最深层的层已经进入飞行中,它们必须完成。
- 如果第一个和最后一个层 主导了舞台的计算 transformers).
- Attention 内核已经使用 FlashAttention - Flash 已经重新计算 softmax 快速,所以额外的层级检查 在顶部几乎没有增加什么。

<a id="implementation-patterns"></a>

### 执行模式

1. **函数折叠符 :** 将一段段换成 `torch.utils.checkpoint.checkpoint(fn, input)`. PyTorch 仅储存 `input`,重新计算其他的一切 在后向。

2. **基于装饰 :** 标签层是可检查的; 训练员在配置时决定哪些部分被包住 。

3. **手动明确重新计算 :** 写 backward pass 自己说,这是习俗 `recompute_forward` 与存储的输入重复。

三个都给出了相同的功能结果 包装是标准智商

<a id="interaction-with-tp--pp--fp8"></a>

### 与TP/PP/FP8的互动

- **Tensor 平行 :** checkpoint 重新计算时必须收集或收回输入;处理通信费用。
- **管道平行 :** 典型模式为 checkpoint 每个管道阶段都向前移动 所以反序微插管可以再利用激活内存
- **FP8 重新计算 :** 重新计算时更新的 amax 历史必须匹配原始前方或 FP8 比例漂移。 大多数框架都快照比例 。

```figure
activation-recompute
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-a-toy-model-with-segments"></a>

### 步骤1:一个带有段的玩具模型

```python
import numpy as np


def linear_forward(x, w, b):
    return x @ w + b


def relu(x):
    return np.maximum(x, 0)


def layer_forward(x, w1, b1, w2, b2):
    h = relu(linear_forward(x, w1, b1))
    return linear_forward(h, w2, b2)


def model_forward(x, params):
    activations = [x]
    h = x
    for w1, b1, w2, b2 in params:
        h = layer_forward(h, w1, b1, w2, b2)
        activations.append(h)
    return h, activations
```

<a id="step-2-naive-backward-needing-all-activations"></a>

### 第2步:需要一切动力的自然后退

```python
def model_backward(grad_output, activations, params):
    grads = [None] * len(params)
    g = grad_output
    for i in range(len(params) - 1, -1, -1):
        w1, b1, w2, b2 = params[i]
        x_in = activations[i]
        h_pre = linear_forward(x_in, w1, b1)
        h = relu(h_pre)
        gh = g @ w2.T
        gw2 = h.T @ g
        gb2 = g.sum(axis=0)
        g_pre = gh * (h_pre > 0)
        gx = g_pre @ w1.T
        gw1 = x_in.T @ g_pre
        gb1 = g_pre.sum(axis=0)
        grads[i] = (gw1, gb1, gw2, gb2)
        g = gx
    return g, grads
```

<a id="step-3-checkpoint-every-k-memory"></a>

### 步骤3: Checkpoint- 每一个记忆

```python
def model_forward_checkpointed(x, params, k=4):
    saved_inputs = [x]
    h = x
    for i, (w1, b1, w2, b2) in enumerate(params):
        h = layer_forward(h, w1, b1, w2, b2)
        if (i + 1) % k == 0:
            saved_inputs.append(h)
    return h, saved_inputs


def model_backward_checkpointed(grad_output, saved_inputs, params, k=4):
    grads = [None] * len(params)
    g = grad_output
    segments = [(j * k, min((j + 1) * k, len(params))) for j in range(len(saved_inputs))]
    for seg_idx in range(len(saved_inputs) - 1, -1, -1):
        start, end = segments[seg_idx]
        if start >= end:
            continue
        x_in = saved_inputs[seg_idx]
        _, seg_acts = model_forward(x_in, params[start:end])
        g, seg_grads = model_backward(g, seg_acts, params[start:end])
        for j, gr in enumerate(seg_grads):
            grads[start + j] = gr
    return g, grads
```

<a id="step-4-cost-model"></a>

### 第4步:成本模式

```python
def checkpoint_cost(n_layers, segment_size, flops_per_layer=1.0):
    fwd = n_layers * flops_per_layer
    recompute = n_layers * flops_per_layer
    bwd = 2 * n_layers * flops_per_layer
    return {
        "fwd": fwd,
        "recompute": recompute,
        "bwd": bwd,
        "total": fwd + recompute + bwd,
        "overhead_vs_no_ckpt": (fwd + recompute + bwd) / (fwd + bwd) - 1.0,
    }


def selective_checkpoint_cost(n_layers, attention_fraction=0.15,
                              flops_per_layer=1.0):
    fwd = n_layers * flops_per_layer
    recompute = n_layers * attention_fraction * flops_per_layer
    bwd = 2 * n_layers * flops_per_layer
    return {
        "fwd": fwd,
        "recompute": recompute,
        "bwd": bwd,
        "total": fwd + recompute + bwd,
        "overhead_vs_no_ckpt": (fwd + recompute + bwd) / (fwd + bwd) - 1.0,
    }
```

<a id="step-5-memory-estimator"></a>

### 第5步:记忆模拟器

```python
def activation_memory_mb(n_layers, hidden=8192, seq=8192,
                        batch=1, bytes_per_value=2):
    per_layer = 12 * batch * seq * hidden * bytes_per_value
    return n_layers * per_layer / 1e6


def memory_after_checkpoint(n_layers, segment_size, hidden=8192,
                           seq=8192, batch=1, bytes_per_value=2):
    n_seg = max(1, n_layers // segment_size)
    saved = (n_seg + segment_size) * 1 * batch * seq * hidden * bytes_per_value
    return saved / 1e6
```

<a id="step-6-optimal-segment-size"></a>

### 步骤6:最佳区段大小

```python
def optimal_segment(n_layers):
    return int(round(np.sqrt(n_layers)))
```

<a id="step-7-selective-checkpoint-decision"></a>

### 步骤7:选择性 Checkpoint Decision

```python
def should_recompute(layer_type, activation_bytes, recompute_flops_ratio):
    if layer_type == "attention" and activation_bytes > 100 * 1e6:
        return True
    if layer_type == "ffn" and activation_bytes > 500 * 1e6:
        return recompute_flops_ratio < 0.1
    return False
```

<a id="use-it"></a>

## 实际应用

- **火炬,用药。checkpoint**: `from torch.utils.checkpoint import checkpoint` - 金刚石包装纸 PyTorch。将函数折叠;仅存储输入,在后向重新计算。
- **威震天- 核心激活**: 支持 `selective`, `full`, 和 `block` 2024年加边境培训的标准。
- **FSDP2 卸载**: `module.to_empty(device="cpu")` 与 `offload_policy` 在FSDP2 碎片激活 CPU 而不是重新计数。
- **深射ZeRO- Offload**: CPU 卸载 optimizer 和启动, 补充检查站。

<a id="ship-it"></a>

## 交付成果

这个课程产生 `outputs/prompt-activation-recompute-policy.md` — 一个 prompt 使用您的模型配置( 层、 隐藏、 下部、 批次) 并可用 GPU 内存并发布每层重新计算策略( 无/ 选择性/ 完整/ 卸载) 。

<a id="exercises"></a>

## 练习

1. 校验正确性。 运行 `model_forward` + `model_backward` (充分激活) `model_forward_checkpointed` + `model_backward_checkpointed` (部分)。 Parameter gradients 必须与机器精度相同。

2. 扫描段大小 `k` 1个至 `L`。 绘制 FLOP 的顶部和内存, 找到曲线的膝盖 。

3. 实施选择性检查:储存 attention- 模块输入,但不是中间体。测量FLOP 上方对32层模型的全层检查(在以下=8192处)

4. 添加卸载。 将段输入保存到模拟的 "CPU 缓冲"( 单独的列表) 。 测量“ PCIe 带宽” 时/ 字节, 并找到卸载和重新计算之间的平衡点 。

5. 以真实的 PyTorch transformer 有和没有 `torch.utils.checkpoint`测量内存 `torch.cuda.max_memory_allocated`和步骤时间。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| Gradient checkpointing | "通过重做来保存记忆" | 仅存储片段输入; 在后退时重新计算中间线以获取 gradient- 支持 tensors |
| 激活重命名 | "和检查站一样" | 同一技术的 HPC 花式名称 |
| 区段大小 (k) | "有多少层每 checkpoint" | 中间体被一起丢弃和再成物质层数 |
| 选择性检查站 | "科西坎蒂的诡计" | 重新配置仅昂贵到储存的激活( A)attention softmax; 保留廉价的 |
| 全面检查 | "天真无邪" | 重新计算每个段的每一层的中间线 |
| 路障检查 | 粗糙的草皮 | Checkpoint whole transformer 块; 最大颗粒度 |
| FLOP 间接费用 | "计算税" | 每步额外FLOPs = (重新计算 FLOPs) / (fwd + bwd FLOPs); 33% 幼稚, 5% 有选择性 |
| 启动卸载 | "飞到 CPU" | 启动移动到 CPU 向后 > 跨过内存; 重算的替代 |
| sqrt-L 规则 | "古典最优美" | 统一成本层次的最佳 checkpoint 间距为 sqrt( L) 层 |
| Attention-softmax volume | "O(L)2问题" | L^2 * heads * 批量浮点; 在长背景下支配激活内存 |

<a id="further-reading"></a>

## 进一步阅读

- [Chen等人,2016年 -- -- "用子线内存成本训练深网"](https://arxiv.org/abs/1604.06174) - 正式化的原始文件 gradient checkpointing
- [Korthikanti等人,2022年 -- -- " 大规模减少活性反响 " Transformer 模型"](https://arxiv.org/abs/2205.05198) - 选择性启动重计和正式费用分析
- [Pudipeddi等人,2020年 -- -- " 使用新执行算法培训具有恒定内存的大型神经网络 "](https://arxiv.org/abs/2002.05645) -- 通过反向模式再材料化的替代常态模拟方法
- [Ren等人,2021年-“ZeRO-Offload:民主化十亿规模模型培训”](https://arxiv.org/abs/2101.06840) - 启动大规模卸载
- [PyTorch 火炬,用药。checkpoint docs](https://pytorch.org/docs/stable/checkpoint.html) - 标准 API
- [威震天桥激活重编文档](https://docs.nvidia.com/nemo/megatron-bridge/latest/training/activation-recomputation.html) - 选择性、完整和块状模式
