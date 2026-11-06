---
name: skill-residual-block-reviewer
description: Review a PyTorch residual block for skip-connection correctness, BN placement, activation order, and shape alignment
version: 1.0.0
phase: 4
lesson: 3
tags: [computer-vision, resnet, code-review, pytorch]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="residual-block-reviewer"></a>

# 剩余块审阅者

任何声称实现残差块的 PyTorch `nn.Module` 的重点审阅者。发现几乎所有 ResNet 重写失败的四个错误。

<a id="when-to-use"></a>

## 何时使用

- 有人编写了自定义的 BasicBlock 或 Bottleneck，损失为 NaN 或准确性被卡住。
- 您正在将一个块从一个框架移植到另一个框架，并希望验证等效性。
- 您正在审查一个更改 ResNet 内部结构（预激活、挤压激励、抗锯齿）的 PR。
- 模型在 CIFAR 大小的输入上运行良好，但在 ImageNet 分辨率上崩溃，因为快捷方式错误。

<a id="inputs"></a>

## 输入

- PyTorch 类定义，作为源文本或可导入路径。
- 可选`variant`：`basic` | `bottleneck` | `preact` | `seblock`.

<a id="four-checks"></a>

## 四项检查

<a id="1-shortcut-shape-alignment"></a>

### 1.快捷形状alignment

对于任何具有 `stride != 1` 或 `in_channels != out_channels` 的块，快捷路径 ** 必须** 是形状匹配模块 - 通常是 1x1 卷积加 BN。在这种情况下，裸露的 `nn.Identity()` 保证了向前时间的形状不匹配错误。

诊断：
```
[shortcut]
  detected:  nn.Identity | 1x1 Conv + BN | 1x1 Conv + BN + ReLU | other
  required:  shape-matching Conv if (stride != 1 or in_c != out_c) else Identity
  verdict:   ok | wrong | unnecessarily heavy
```

<a id="2-bn-placement-relative-to-the-addition"></a>

### 2. 相对于加法的BN放置

添加 `out + shortcut(x)` 必须发生在 **before** 之前，最终的 ReLU（激活后，原始 ResNet）或最终的 ReLU 必须完全不存在（激活 ResNet v2）。在主 branch 中应用 ReLU 然后添加原始快捷方式的块会产生不对称的激活范围，从而损害训练。

诊断：
```
[activation order]
  pattern:  post-act (conv-BN-ReLU-conv-BN-add-ReLU) | pre-act (BN-ReLU-conv-BN-ReLU-conv-add) | other
  verdict:  ok | suspect
```

<a id="3-bias-on-conv-layers"></a>

### 3. 卷积层的偏差

紧接着 BatchNorm 的转换应具有 `bias=False`。 BN 的 beta 已经参数化了偏差，因此额外的转换偏差会浪费 parameters 并且会减慢收敛速度。

诊断：
```
[bias]
  convs with BN and bias=True: <count>
  recommended fix: set bias=False on those layers
```

<a id="4-in-place-relu-and-autograd"></a>

### 4.就地ReLU和autograd

将添加到快捷方式的 `nn.ReLU(inplace=True)` 上的 tensor 会覆盖剩余添加可能仍需要的值。标记任何 `inplace=True`，该层后面没有在添加之前生成新 tensor 的层。

诊断：
```
[in-place]
  risky inplace ops: <list>
  fix: inplace=False before the residual add
```

<a id="report"></a>

## 报告

```
[block-review]
  variant:       basic | bottleneck | preact | se | other
  shortcut:      ok | wrong | heavy
  activation:    ok | suspect
  bias-bn:       ok | <N> convs need bias=False
  in-place:      ok | <N> risky ops
  summary:       one sentence
```

<a id="rules"></a>

## 规则

- 不要重写该块。仅报告。
- 如果块正确，则到处说 `ok` 并停止。没有建议。
- 如果有多个错误，请按上面的顺序列出它们（首先是快捷方式，因为这是导致崩溃的最常见原因）。
- 当用户指定时，切勿将故意的预激活或挤压激励变体标记为错误。
