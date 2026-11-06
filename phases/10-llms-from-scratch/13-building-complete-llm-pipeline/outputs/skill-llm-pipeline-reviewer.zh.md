---
name: llm-pipeline-reviewer
description: Review an end-to-end LLM training pipeline manifest before a multi-million-dollar run.
version: 1.0.0
phase: 10
lesson: 13
tags: [pipeline, training, manifest, eval-gate, cost, rollback]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于拟议训练编审名单(YAML 或 JSON describing tokenizer数据,训练前, SFT, alignment,评估, quantization审评内容包括:

1. 阶段图。 确认每个阶段都输入了输入和输出。 调出缺少的依存关系、 隐含状态, 或任何消耗光目录而不是名副其实的文物散列的阶段 。
2. 散列链。 校验输出_N阶段的散列等于输入之一_每个下游阶段的混凝土。任何不匹配都意味着舱单不连贯,输油管也不得启动。
3. Eval 门。 门表中的每个标准必须是数字、 运算符、 阈值和测量源。 拒绝任何主观( “ 看上去不错 ” ) 、 未绑定( 没有门槛 ) 或根据训练数据测量的门 。
4. 回归保护。 新模型的核心基准( MMLU、 MATH、 HumanEval+、 GPQA 或特定域等值) 必须附加基线数字 。 没有基线的运行是没有回归检测的运行 。
5. KL预算。 Alignment 阶段(RLHF, DPOCAI公司,CAI公司, GRPO) 必须在引用时声明累积 KL 上限。无界 KL 是无界漂移 。
6. 污染检查。 eval sets 必须进行有文件记录的重叠检查( A)exact match 或13克)要求的通过阈值:<0.1%。
7. 成本估算:每个阶段的预运行估计数加上一个总数,与预算门相比。如果估计 > 预算,管道就拒绝启动。
8. Rollback 计划。每个阶段,命名的失败动作:重新运行、返回到以前的工艺品、修改输入和下游再运行。 昂贵的阶段( 预修阶段) 必须有一个温暖的阶段 checkpoint 战略。
9. 人工商店。 Checkpoints,数据集, tokenizers, Eval 报告必须是内容处理 (SHA-256) , 文件名处理的文物 (“ last.pt”) 是一个硬性拒绝 。
10. Observability。每个阶段必须排放结构化的日志,并 trace ID、 舞台名称、 输入杂交、 输出散列、 挂钟和成本 。 失踪 trace 身份显示在事后无法调试 。

阻止审查的红旗:
- 缺少测量源的门( 标准开口不计算阶梯)
- 共享的阶段 checkpoint 具有下游阶段(没有将关注问题分开)
- 一个 alignment 没有参考模型的阶段( KL 没有锁定)
- 一个 LLM- 法官撤职,法官是同一种模范家庭(污染)
- a 超出预算20%以上的费用估计数。
- 一个 rollback 完全由"从零开始"组成的计划

产出:每扇门用PASS/HOLD进行两页审查,得出每项裁决的准确清单字段或缺失字段,以及将 HOLD 转换成PASS所需的最小修改。
