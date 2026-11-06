---
name: skill-refusal-evaluation
description: Two-sided refusal metrics with calibration and per-category breakdown over a labeled prompt corpus
version: 1.0.0
phase: 19
lesson: 84
tags: [safety, evaluation, calibration]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="refusal-evaluation"></a>

# Refusal Evaluation

标签的安全和不安全的体积 prompts 执行一个或多个模式政策。 产出被归类为拒绝或回答。 框架返回 :

- 拒绝后:回答 prompts 标签为不安全/完全不安全
- 拒绝:拒绝 prompts 标签安全/ 全部安全
- 准确度:(正确拒绝+正确回答) / 总计
- 欧洲经委会:预期 calibration 由已声明的置信度中键入错误
- 拒绝后每一类:结合课程82

<a id="plugging-in-a-real-model"></a>

## 插进一个真正的模型

模拟 LLM 是一个可调用 `(prompt: str) -> str`替换为 HTTP 折叠, 返回模型输出并嵌入信任标记( 或修改) `parse_confidence` 阅读提供者所揭露的一切。其他的都保持不变。

<a id="artifact"></a>

## Artifact

`outputs/refusal_eval_report.json` 87学说为本报告中设定了阈值。
