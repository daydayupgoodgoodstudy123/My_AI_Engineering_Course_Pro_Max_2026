---
name: skill-freeze-inspector
description: Report which parameters are trainable, which BatchNorm layers are in eval mode, and whether the optimizer is actually consuming the trainable parameters
version: 1.0.0
phase: 4
lesson: 5
tags: [computer-vision, transfer-learning, debugging, pytorch]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="freeze-inspector"></a>

# 冷冻检查员

迁移学习错误隐藏在三个地方：应该被冻结但没有冻结的 parameters、应该可训练但不可训练的 parameters 以及在冻结状态更改之前构建的 optimizers。此技能一次即可显示所有三个技能。

<a id="when-to-use"></a>

## 何时使用

- 在 parameters 的子集上设置 `requires_grad` 后。
- 在微调运行的第一个训练步骤之前。
- 调用 `freeze_bn_stats` 或任何翻转 BN 模式的助手后。
- 当 val 准确度随机陷入并且你怀疑实际上没有任何训练时。

<a id="inputs"></a>

## 输入

- `model`：PyTorch `nn.Module`。
- `optimizer`：即将用于训练的optimizer。
- 可选 `expected_frozen_prefixes`：应冻结的 parameter 名称前缀列表（例如 `["conv1", "bn1", "layer1"]`）。

<a id="steps"></a>

## 步骤

1. **Walk parameters.** 对于每个 `(name, param)`：
   - 记录`requires_grad`
   - 记录`shape`和`numel`

2. **Walk 模块。** 对于每个模块：
   - 如果是BatchNorm，则记录其是否处于eval模式以及其仿射parameters是否可训练。

3. **检查 optimizer.** 对于每个 parameter 组：
   - 将其 `params` 压平为一组 `id(p)`。
   - 与参数的所有 `id(p)` 的集合进行比较，其中 `requires_grad == True`。

4. **检测四种故障模式：**
   - `leaked_train`：参数具有 `requires_grad=True` 但未出现在 optimizer 中（gradient 已计算但从未应用）。
   - `ghost_train`：参数出现在optimizer中，但有`requires_grad=False`（optimizer状态被浪费；如果稍后重新启用requires_grad，也可能导致错误）。
   - `bn_mismatch`：(a) BN 层处于训练模式（累积运行统计数据），而其仿射 parameters（`weight`、`bias`）被冻结，或 (b) BN 层处于评估模式（冻结统计数据），而其仿射parameters 是可训练的。两种状态不一致并且几乎总是一个错误。
   - `expected_vs_actual`：`expected_frozen_prefixes`中列出的任何前缀仍然具有可训练的parameter。

<a id="report"></a>

## 报告

```
[freeze-inspector]
  model trainable params: <N>
  model frozen params:    <N>
  batchnorm layers in eval mode: <count>
  batchnorm layers in train mode: <count>

[optimizer coverage]
  trainable params fed to optimizer: <M> of <N>
  leaked_train: <list of names> (trainable but not in optimizer)
  ghost_train:  <list of names> (in optimizer but frozen)

[bn audit]
  mismatched layers: <list of names>

[expectations]
  expected_frozen_prefixes: <...>
  violating params:         <list>

[verdict]
  ok | <one-line summary of the most severe issue>
```

<a id="rules"></a>

## 规则

- 只报告parameter名称；切勿自行打印 weights。
- 按 parameter 名称的字母顺序对每个列表进行排序。
- 如果 optimizer 覆盖率为 100% 并且没有不匹配，则返回 `ok` 并停止。
- 对于 `leaked_train`，始终建议在冻结状态更改后重建 optimizer。
- 对于 `ghost_train`，如果目的是训练它，建议删除 parameter 组或设置 `requires_grad=True`。
