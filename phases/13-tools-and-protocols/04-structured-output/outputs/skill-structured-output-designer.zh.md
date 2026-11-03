---
name: structured-output-designer
description: Design a strict-mode-compatible JSON Schema plus Pydantic model for a free-text extraction target, with typed refusal and retry handling stubbed in.
version: 1.0.0
phase: 13
lesson: 04
tags: [structured-output, json-schema, pydantic, strict-mode, extraction]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以自由文本提取目标(发票、简历、支持票、研究摘要)为条件,可签订一份可供生产提取的合同: JSON 2020-12, 皮但提型, 拒绝处理器, 和重新尝试政策 。

显示 :

1. JSON 2020-12号计划,每处财产都打过字 `required` 列出所有财产。 `additionalProperties: false` 用于封闭值组的 Enums。 `$ref`。 无模糊 `oneOf` / `anyOf`. 对照 OpenAI 严格模式要求。
2. 平时 v2 基础模型。 与 Python types. `model_json_schema()` 必须产生相当于(1)的系统。
3. 拒绝处理器。 键入 `Refusal(reason: str, category: str)` 结果。 列出分类 : `safety`, `input_mismatch`, `insufficient_info`.
4. 重试政策。 三种重试形状:(a) 输入验证错误并重试一次(严格模式之外);(b) 接受拒绝为最终(严格模式);(c) 升级为反复拒绝的更强模型。
5. 测试矢量。 包含幸福路径、 对抗字段、 部分输入和拒绝触发的大小写。 每个都具有预期结果 。

艰难的拒绝 :
- 任何带有未输入字段的图案。如果使用严格模式,则会同时验证。
- 任何计划缺失 `additionalProperties: false`。泄漏 hallucinations.
- 任何使用图案的 `oneOf` 毫无歧视,模糊的解码
- 任何没有它的小矮人模型 JSON 检查了轮回路线

拒绝规则 :
- 如果目标领域包括个人识别数据,而没有记录的目的,则拒绝提供数据,并选择前往第18阶段(伦理学),以进行合法辩论。
- 如果用户要求的图案无法以 JSON 2020-12号计划(例如,递归性任意图表)拒绝并提出最直接的可表达的放松。
- 如果提取目标“从任何事物中提取结构化数据”,则拒绝并要求特定域。

产出:与计划签订一页合同 JSON, Pydantic 类,拒绝和重试政策,以及十种测试矢量。结尾处有第一个目标提供者的注解和原因。
