---
name: gradient-accumulation
description: Train at an effective batch larger than device memory by scaling micro-batch losses and stepping the optimizer once per window.
version: 1.0.0
phase: 19
lesson: 46
tags: [training, batch-size, distributed, scaling]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="when-to-use"></a>

## 何时使用

有效的批量是拉平 gradient 并匹配 learning rate schedule。当您无法支付单项 forward pass这是食谱

<a id="recipe"></a>

## 食谱

1. Pick `micro_batch` 以最大尺寸 适合记忆 和饱和加速器。
2. Pick `effective_batch` 来自 learning rate schedule.
3. Set `accum_steps = effective_batch // (micro_batch * world_size)` 并且称之为平分。
4. 每个微批量 : `loss = criterion(model(x), y) / accum_steps; loss.backward()`.
5. 非最后微数,请输入 `model.no_sync()` 跳过 gradient 全部在 DDP 中减少。
6. 上一批小货之后,快跑 `optimizer.step()` 一次,零 gradients 下一个窗口前。
7. 该 optimizer 规定每批有效分批支付一次预付款; learning rate schedule 键每批有效 。

<a id="logging"></a>

## Logging

少许的 JSON 记录 `samples_per_sec`, `median_step_ms`, `sync_calls`, `accum_steps`, `effective_batch`。没有这种能力,成本交易是看不见的。

<a id="failure-modes"></a>

## 失效模式

- 忘记 `/ accum_steps` scaling: gradients 由N爆炸。
- 中窗口步态 : parameters drift.
- 同步每个小批量: 网络将无法获取统计收益 。
- 混合此与 mixed precision 取消缩放: 仅缩放未缩放的损失 。
