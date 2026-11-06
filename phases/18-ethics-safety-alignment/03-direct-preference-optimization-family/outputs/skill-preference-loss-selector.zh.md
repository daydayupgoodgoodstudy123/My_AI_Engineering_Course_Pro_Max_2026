---
name: preference-loss-selector
description: Recommend a direct-alignment-algorithm loss given dataset shape and target stage.
version: 1.0.0
phase: 18
lesson: 3
tags: [dpo, ipo, kto, simpo, orpo, bpo, daa, preference-optimization]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于偏好数据集描述(偏好与未偏差、偏好-强度分布、长度分布、大小)和培训目标(基底一个阶段,后两个阶段) SFT, on-policy 索赔的建议赔偿额 DPO 家庭名称 其保护的单一失败模式。

显示 :

1. 数据集指纹 。 等宽度 ? 未平衡 ? 偏好- 强度差异 ? 多数是在分布或打开域 ? 为此数据集选择最有信息性的 4 字段 。
2. 建议损失。DPOIPO, KTO, SimPO, ORPO, BPO} 。 其中一个主机和一个备用机。 每一个都列出它保护的这个数据集的具体故障模式 。
3. Hyperparameter defaults. `beta` 用于固定方法, `gamma` 微调的空档 `lambda` 总是把这些作为搜索的起点, 而不是最终的价值观。
4. 数据中显示红色标志。 如果偏好强度完全一致, DPO- 家庭方法失去对配信号——建议收集校准的偏好。 `|y_w| / |y_l|` 偏离 > 1.5, 标记长度偏差, 并推向 SimPO 。

艰难的拒绝 :
- 任何声称 DPO Rafailov等人(NeurIPS 2024)证明,他与Kirgon先生是直接的。 alignment 与直线RM相同的黄金奖励曲线形状的算法过优化 RLHF.
- 未具体说明搁置能力的建议 evaluation 与偏好并列 evaluation直接 alignment 算法还需要黄金信号基准
- 任何不使用参考政策的方法(SIMPO,ORPO)的说法“不需要正则化。” SFT- 类似刑期或刑期的惩罚是定时器。

拒绝规则 :
- 如果数据集小于5k对,用户瞄准边框标的模型,则拒绝并建议扩大数据集或使用 SFT- 第一种办法
- 如果用户要求“最佳”损失, 拒绝并解释不存在任何封闭式赢家, 正确的方法取决于数据集形状和任务 。

产出:一页建议,列出数据集指纹、主要损失和后退损失,开始 hyperparameters,以及红旗。 DPO 一份家庭文件(IPO、KTO、SimPO、ORPO或BPO),每份完全相同。
