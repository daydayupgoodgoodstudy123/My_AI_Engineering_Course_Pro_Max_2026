---
name: nsa-integrator
description: Integration plan for Native Sparse Attention in a long-context pre-training run.
version: 1.0.0
phase: 10
lesson: 17
tags: [nsa, sparse-attention, long-context, pre-training, kernel-aligned, deepseek]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于训练前的规格(目标背景、基础架构、训练)具有长期的文字 tokens 可用, GPU NSA的一体化计划。

显示 :

1. 压缩块大小 `l`选择32、64或128,对照目标背景说明: `l = 32` 16k -32k, `l = 64` 64k-128k, `l = 128` 256k+. 大 `l` 表示压缩键较少,但路径信号粗略。
2. 最大选择数。 选择 8 到 32 之间。 纸张的默认值是 16 。 在目标任务组合下说明理由: 推理重( math, code) 的好处是更高 `k` 因为选择精度更重要。 回收重任务在较低位置工作 `k`.
3. 滑动窗口 `W`。选择 256、512或1024。默认 512。对于结构严谨的内容(代码),如果当地环境足够,则更短;对于文章来说更长。
4. 门 MLP 指定宽度和初始化。 默认: 线性层 `hidden` 至 3, 与 `sigmoid` 或 `softplus` 启动,警告门 weights 自动折叠以有利于一个 branch - 这表示 `l`, `k`, 或 `W` 被误判了
5. 内核选择。 确认 Triton 或 CUDA kernel availability 对于目标加速器。 拒绝后退到密度 attention 在 inference 如果只有前内核存在而不是后向,就拒绝预先培训,并建议继续培训现有的密集分子。 checkpoints.

艰难的拒绝 :
- NSA的模型 训练有素,密度高 attention 没有继续训练前训练 无法在 inference.
- 目标背景在16公里以下branch 顶部居主导地位。
- Inference- 仅在堆叠上部署没有NSA内核支持。 attention 改为.

拒绝规则 :
- 如果长字符 evaluation 数据(RULER、LongBennch、针头)不详、拒绝和请求 calibration 数据先。
- 如果培训-数据背景分布以短顺序为主,则拒绝并建议在纳入消极安全保证之前对数据进行重新加权。
- 如果加速器大于A100,则拒绝——消极安全保证的内核优势假定为H100/H200/MI300记忆级。

产出:一页集成计划清单 `l`, `k`, `W`, Gate 配置、 内核路径, 以及预期在目标上下文中计算节余。 结尾处有一个“ 成功标准” 段落: 特定的 RULER 或 LongBench 编号( 百分比点与密钥对齐)attention 包括一个 rollback 触发点——基准阈值,低于该阈值的结构应恢复为司法协助或密集的GQA。
