---
name: mtp-planner
description: Plan a multi-token prediction integration for a new pre-training run.
version: 1.0.0
phase: 10
lesson: 18
tags: [mtp, multi-token-prediction, deepseek-v3, pre-training, speculative-decoding]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于训练前操作规格( 模型规模、 隐藏大小、 层、 数据) tokens 预算, GPU 地形学、目标部署以及一个明确的目标(密度训练信号与投机-解码草案和两者)产生了MTP一体化计划。

显示 :

1. 深度D. 选取1或2。 DeepSeek-V3 使用 D=1, 并在80°C报告第一个深度投机解码接受。 D=2 正在减少大多数运行的回报区。 比较计算预算的选择, 每一个额外的深度都增加了大约一个 transformer 计算每个训练步骤的块。
2. Lambda 排程。 默认值: 最初10%的培训为0. 1, 之后为 0.1 。 对于较稠密的信号更重要的小型模型( 7B 下) , 调整到 0. 5 早期 ; 如果您看到MTP 损失主导主要损失, 则调整下来 。
3. Parameter 预算. 每个单元的报告 parameter 根据主模型计算。 确认间接费用低于主机的5%。 parameters (严重)或不足3%(MoE).
4. 内存和计算间接费用。 每步量化额外的前穿 FLOP( 粗略) `D * transformer_block_cost`),额外后传内存(D模块的激活内存)和额外峰值 VRAM(共享) embedding 头不计数,投射 transformer 区块 do )
5. Inference描述如何将MTP模块作为投机性解码草案 inference。命名利维坦规则整合路径和KV-rollback 确认是否与目标兼容 inference 堆叠( T)vLLM, SGLang特索瑞特, 特索瑞特... ...LLM).

艰难的拒绝 :
- 将MTP添加到一个密集模型中, 没有它, 就无法改造—— MTP 模块没有被培训 。
- D > 2 表示第一次整合。 超过 D=1的收益较小; 复杂性迅速增长 。
- 1B 下运行模型的MTP parameters。信号比该规模的间接费用弱。
- 使用平行( Gloeckle- stype) 目标为时头 speculative decoding它们不是因果连锁的。

拒绝规则 :
- 如果训练前数据以短顺序(2k)为主,则拒绝。 MTP的收益假定序列足够长,足以让深度2监督发挥作用。
- 如果目标 inference 堆叠不支持 speculative decoding 注意,MTP仍然购买 更密集的训练信号 并继续进行, 但标记不匹配。
- 如果用户正在对现有的密度进行预训练 checkpoint 没有MTP,仅在清洁训练开始或数据边界重新设置时拒绝并建议增加MTP。

产出:一页集成计划,列出D、羊排时间表, parameter 间接费用(绝对数和百分比),计算间接费用(每个训练步骤的百分比) inference以“成功标准”为结尾的段落点名了衡量数据,说明保持MTP的合理性:50B训练后深度1的接受率 tokens 必须超过70%,否则建筑应该恢复。
