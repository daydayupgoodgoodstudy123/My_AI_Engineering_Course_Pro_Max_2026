---
name: skill-conv-shape-calculator
description: Walk a CNN spec layer by layer and report output shape, receptive field, and parameter count for every block
version: 1.0.0
phase: 4
lesson: 2
tags: [computer-vision, cnn, architecture, debugging]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="conv-shape-calculator"></a>

# 转换形状计算器

planning 或调试 CNN 的确定性帮助程序。给定输入形状和层规格列表，trace 形状、感受野和 parameter 在不运行模型的情况下进行计数。

<a id="when-to-use"></a>

## 何时使用

- 设计一个新的 CNN 并且您想要验证每个下采样都落在干净的尺寸上。
- 阅读一篇论文并将其架构表翻译成代码。
- 预训练的主干网因分类器头部的形状不匹配而崩溃，您需要知道哪一层改变了空间大小。
- 在训练之前比较两个主干网 parameter 的效率。

<a id="inputs"></a>

## 输入

- `input_shape`: `(C, H, W)`.
- `layers`：层字典的有序列表。每个支持：
  - `{type: "conv", c_out, k, s, p, groups=1, bias=true}`
  - `{type: "pool", mode: "max"|"avg", k, s, p=0}`
  - `{type: "adaptive_pool", out_h, out_w}`
  - `{type: "flatten"}`
  - `{type: "linear", out_features, bias=true}`

<a id="steps"></a>

## 步骤

1. **用`(C, H, W)`初始化trace**，感受野`1`，有效步幅`1`，累积参数`0`。

2. ** 对于每一层**，按以下顺序更新：
   - 计算`C_out`（转换/线性），或通过（池）携带`C_in`。
   - 使用 `(H + 2P - K) / S + 1`（用于卷积和池）、`out_h/out_w`（用于自适应池）、`(1, 1)`（用于在线性之前展平输出形状 `(C * H * W, 1, 1)` 和标量 `1x1`（用于线性）计算空间输出。
   - 更新感受野和有效步幅：
     - 卷积/池：`RF_new = RF_old + (K - 1) * effective_stride`、`effective_stride *= S`。
     - 自适应池：视为有效 `S = H_in / out_h`（向下取整）的池。 `RF_new = RF_old + (H_in - 1) * effective_stride_old`; `effective_stride *= S`。请注意，自适应池的 RF 等于先前的完整空间范围。
     - 扁平/线性：RF和有效步幅不再有意义；将它们冻结为展平之前的值并从后续行中省略。
   - 计算参数：
     - 转化：`C_out * (C_in / groups) * K * K + (C_out if bias else 0)`。
     - 线性：`out_features * in_features + (out_features if bias else 0)`。
     - 池化和展平：0。

3. **检测问题**并标记它们：
   - 非整数输出大小（未对齐的步幅/填充）。
   - `H_out <= 0` 位于堆栈末尾之前。
   - 感受野超过输入大小（该点之后可能浪费计算）。
   - 每层参数突然跳跃 10 倍，表明通道计划错误。

4. **Report** 作为单个表：

```
idx  layer                C_in  C_out  K  S  P  H_out  W_out  RF    params     cum_params
1    conv 3x3 s=1 p=1     3     32     3  1  1  224    224    3     896        896
2    conv 3x3 s=2 p=1     32    64     3  2  1  112    112    7     18,496     19,392
3    pool max 2x2         64    64     2  2  0  56     56     11    0          19,392
...
```

5. **摘要行**：最终`(C, H, W)`，最终感受野，总参数，警告。

<a id="rules"></a>

## 规则

- 始终返回空间大小的整数。如果公式生成非整数，则标记为错误并且不要默默地取整。
- 当`groups > 1`时，验证`C_in % groups == 0`和`C_out % groups == 0`；否则错误。
- 对于深度转换（`groups == C_in`），将其标记在 `layer` 列中，以便读者了解参数较低的原因。
- 如果用户提供 BatchNorm 或激活层，则出于形状目的而忽略它们，但向前传递参数（每个 BatchNorm 的 `2 * C`）。
- 永远不要猜测缺失字段的默认值。每个转换和池上都需要 `k`、`s`、`p`。
