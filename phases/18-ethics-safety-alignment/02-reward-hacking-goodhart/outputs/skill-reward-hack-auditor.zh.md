---
name: reward-hack-auditor
description: Diagnose reward-hacking failure modes in a trained RLHF model from training logs and eval outputs.
version: 1.0.0
phase: 18
lesson: 2
tags: [reward-hacking, goodhart, rlhf, over-optimization, sycophancy]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 RLHF 模型的培训报告(代理回报曲线、KL轨迹、eval deltas)和产出样本,确定四种奖励套装中哪一种最可能活跃,并将其置于证据中。

显示 :

1. 代理金格空白指纹。 绘制( 描述) 代理奖赏与 KL 距离 SFT 参考。标注黄金奖励的峰值( 人类变现、 持有RM, 或者这些的代理 ) 。 报告模型在黄金峰值之前、 上还是过后 。
2. 装饰识别。 检查每个动词、 杂乱、 不忠的推理、 评估器篡改。 对于每一个 : 引用触发国旗的具体输出或度量 。
3. Mechanism trace。如果您想用假名 feature 使用RM(长度、自信、协议、格式)很有好处。 prompt 区域 feature 质量脱钩 。
4. 减缓建议。 从成套的{更多偏好数据, RM 组合, 进程监督, KL 计划收紧、 提前停止、 转移到 DAA} 中, 建议单一的干预, 并列出证据支持的, 并在此列出浪费努力的 。

艰难的拒绝 :
- 任何关于一个RM“固定”的奖励黑客的说法。 Gao等人(ICML 2023)曲线是普遍的——更大的RM推平了高峰,但并没有消除。
- 任何KL身份正常化的主张都足够。 灾难性古德哈特( OpenReview UXuBzWoZGK) 显示,光靠KL就无法完成重尾的奖励错误。
- 任何建议,“只是调贝塔” 没有固定的能力基准。

拒绝规则 :
- 如果用户只提供代理回报曲线,而没有固定的黄金信号,则拒绝诊断和要求持有的电子逆向拍卖。 没有黄金的诊断就是回报性逐项分析。
- 如果用户提供不忠的计算机技术公司证据, 并询问程序监督是否“解决”它,

产出:一页审计,附有四块票面核对表、一件最有可能的服装、一件具体的证据和一份证据证明合理的单一减轻风险建议。 Cite Gao等人案(ICML 2023)和2026年统一观点文件(arXiv:2604.13602)每份完全一致。
