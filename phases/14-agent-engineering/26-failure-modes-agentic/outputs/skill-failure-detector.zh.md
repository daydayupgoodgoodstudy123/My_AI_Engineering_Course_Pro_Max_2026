---
name: failure-detector
description: Generate failure-mode detectors for agent traces, wired to a trace store, tagging the five industry-recurring modes plus domain-specific signatures.
version: 1.0.0
phase: 14
lesson: 26
tags: [failure-modes, masft, detection, observability]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给出产品领域和 trace 储存,生产探测器 agent 失败模式 。

显示 :

1. 检测器/ 模式 : `hallucinated_action`, `scope_creep`, `cascading_errors`, `context_loss`, `tool_misuse`, `success_hallucination`.
2. 域特定探测器(例如,“创建了没有连接问题的公关”用于dev工具,“向 > 5个接收者发送电子邮件,但未经确认”,用于营销工具)。
3. 将所有探测器都应用到每个探测器的塔格 trace 并发布一个分布。
4. 阈值提醒: 如果占今天的5% traces 标记模式、页面或打开票。
5. 样本保留:每个标有标签 trace,保持输入+输出+状态快照供操作员审查。

艰难的拒绝 :

- 需要的探测器 LLM 电话 trace 使用模式探测器;储备 LLM- 做抽样审查的裁判
- 仅对崩溃进行标记。 大多数失败产生有效外观输出。 需要检查内容+状态的签名 。
- 正在存储标记 traces 无效样本含有最坏的内容; 在存储前清洗 。

拒绝规则 :

- 如果用户想要"所有 traces 永久存储,“拒绝成本+合规性原因。用标签+费率抽样。
- 如果产品没有“已知好”基线, 拒绝漂移警报。 Drift 需要参考 。
- 如果探测器没有被版本, 拒绝。 检测器回归会不经通知中断您的信号 。

输出: `detectors.py`, `tagger.py`, `alerts.py`, `retention.py`, `README.md` 解释阈值、 保留政策、 警戒路线。 结尾处指向 24 ()observability 或课程27(prompt injection)用于对抗性故障模式。
