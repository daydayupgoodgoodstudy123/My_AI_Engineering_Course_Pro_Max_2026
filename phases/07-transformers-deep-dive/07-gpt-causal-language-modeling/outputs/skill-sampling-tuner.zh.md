---
name: sampling-tuner
description: Pick decoding strategy (greedy / temperature / top-k / top-p / min-p / speculative) for a given generation task.
version: 1.0.0
phase: 7
lesson: 7
tags: [gpt, sampling, decoding, inference]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定生成任务（代码、创意写作、推理、对话、structured output）和延迟/质量目标，输出：

1. Sampling方法。其中之一：贪婪、temperature-only、top-k、top-p、min-p、beam-k、投机。一句话理由。
2. Parameter 值。 Temperature、top-k、top-p、min-p、重复惩罚——与任务类型相关的具体数字。 （例如，代码为 temperature 0.2 + top-p 1.0；聊天为 min-p 0.1 + temperature 0.7。）
3. 停止条件。 `max_new_tokens`，止损token列表，基于形态的止损（例如平仓`</tool_call>`）。
4. 决定论切换。固定种子以提高再现性；标记用例（eval、legal）是否需要它。
5. 质量检查。针对任务目标的一行测试（编译/通过单元测试、事实性、格式有效性等）。

拒绝为 structured output 或代码补全推荐 temperature > 1.0 — hallucination 风险急剧上升。拒绝推荐纯粹贪婪的开放式对话——模型会循环。当模型可以生成模板/工具时，拒绝发送没有指定 stop-token 列表的 sampling 配置。
