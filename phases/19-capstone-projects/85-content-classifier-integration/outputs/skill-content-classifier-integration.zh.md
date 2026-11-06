---
name: skill-content-classifier-integration
description: Three output-side classifiers (toxicity, PII, instruction-leakage) behind a single severity router with block, redact, warn, log actions
version: 1.0.0
phase: 19
lesson: 85
tags: [safety, classifier, output-filter]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="content-classifier-integration"></a>

# 内容分类整合

三个分类器,一个路由器,四个动作

<a id="verdict-structure"></a>

## 判决结构

```text
ClassifierVerdict
  name: str
  severity: none | low | medium | high
  score: float in [0, 1]
  findings: list[str]
```

<a id="action-table"></a>

## 行动表

| Severity | 动作 | 效果 |
|---|---|---|
| 高 | block | 被政策拒绝取代的产出 |
| 中等 | redact | 按顺序应用的分类编辑器 |
| 低 | warn | 输出随软通知附加而发运 |
| 无 | log | 输出未变运, 已记录 |

<a id="per-classifier-behavior"></a>

## 分类行为

- 毒性 - 带有白空格界限的骚扰条件和小型左窗否定检查; `[redacted-language]`
- pii - 电子邮件、电话、SSN、Luhn-valided卡、IPv4;SSN和卡的强度升级;每个形状都编辑成标签
- 教学渗漏 - 三重弦对已知的 system prompt; 重力尺度与重叠; 编辑第一个系统-prompt line

<a id="artifact"></a>

## Artifact

`outputs/classifier_report.json` 带有动作动词、 严重性、 编辑输出, 以及每个案件的全部判决列表 。
