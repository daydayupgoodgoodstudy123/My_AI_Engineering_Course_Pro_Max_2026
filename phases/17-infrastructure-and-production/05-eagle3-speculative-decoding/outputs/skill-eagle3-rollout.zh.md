---
name: eagle3-rollout
description: Produce a staged EAGLE-3 speculative-decoding rollout plan that measures acceptance rate alpha on real traffic before shipping.
version: 1.0.0
phase: 17
lesson: 05
tags: [speculative-decoding, eagle-3, vllm, alpha, production-rollout]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


目标模型,硬件(GPU 类型和计算)、交通说明(一般聊天/代码/专门)、货币指标和当前基准度量(TTFT、国际交易日志、吞吐量),产生分阶段的EAGLE-3 rollout plan.

显示 :

1. 基准测量计划。 基准( LLMPerf、 GENAI-Perf 或生产阴影) prompt 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 计算单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位:
2. 预选首选项。 共享 GPT 培训的 EAGLE 3 用于一般聊天。 域培训的 EAGLE 3 用于专门交通( 代码、 医学、 法律) 或决定在运输前培训 。
3. 配置。 精确 vLLM `speculative_config` 字段(方法、模型、 num)_speculative_设置的兼容矩阵 vLLM 版本 (v0.1.8.0马克) speculative decoding 兼容 chunked prefill).
4. 阿尔法门,目标阿尔法0.55 生产货币 shadow traffic 24小时,日志 vLLM `spec_decode_metrics`,已接受的分隔 tokens 。 如果在任何1小时的窗口中阿尔法跌落到0.45以下, 则击落开关 。
5. 尾表。 绘制 P99 独立的交易日志三角形( 标注 - 标注关闭) 。 如果 delta 是正数, 则拒绝的双向图案模式正在被咬。 减少 K 或禁用此工作量 。
6. 平衡检查。 在报告的货币计算时, 计算当前验证的折中值 alpha。 只有在测量到阿尔法时, 才能将折中值至少清除 0.1 。

艰难的拒绝 :
- 运输不测量生产流量的阿尔法,拒绝,需要24小时影子测量。
- 要求2 -3x加速,没有命名测量的阿尔法。
- Enabling speculative decoding 用于不连接的批量工作, 延迟不是限制 。
- Combining speculative decoding 与 pipeline parallelism 在 vLLM 0.15.0或更早。推测解码文件将它列为不兼容的。

拒绝规则 :
- 如果流量主要为极短的产出(不到50个) tokens 船头的轮廓占优势,船平目标。
- 如果硬件是消费者(RTX 4090 / 5090)和 batch size 留在8之下,建议采用简单的目标——对间接费用需求进行分批摊,使硬件无法供应。
- 如果用户想要 K 的自动调音而不使用测量循环, 请拒绝。 K 从测量的 Alpha 加上校验管理费中选择; 没有自动调频替换测量 。

产出:一页 rollout 计划列出  配置  Alpha 门  尾部表  折叠确认 。 结尾处有一个“ 如何测量下一步” 段落, 指定特定域 EAGLE-3 训练, 低 K 或根据诊断恢复为普通目标 。
