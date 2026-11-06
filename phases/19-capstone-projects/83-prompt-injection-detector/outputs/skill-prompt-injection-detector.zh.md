---
name: skill-prompt-injection-detector
description: Layered detector pipeline that returns a category and confidence for any prompt, with measurable precision and recall
version: 1.0.0
phase: 19
lesson: 83
tags: [safety, detector, prompt-injection]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="prompt-injection-detector"></a>

# Prompt Injection Detector

检测器是来自 prompt 判决包含82课的分类学和对 [0, 1].

<a id="pipeline"></a>

## 管道

1. 正常化 - 脱下零边字符, 解码基数64/hex, 折叠列伊- 方位数, 尝试用通用词正常检查 来旋转13 。
2. 潜线规则 - 手写针头,例如 `ignore previous`, `from now on you are`, `decode this base64`.
3. 瑞格斯规则 - token- 级别模式,如 `\bignor\w*\s+(all|prior|previous|earlier)\b`.

集合保持每个类别的最大分数,返回最大分数的类别,或 `benign` 如果没有火灾。

<a id="adding-a-rule"></a>

## 添加规则

Edit `code/rules.py`。规则是用 `name`, `category` (六个分类类别之一), `score` 和(从0到1号) `substring` 或 `regex`重新运行 `main.py` 来观察对每类精确度和回溯的影响。

<a id="artifact"></a>

## Artifact

`outputs/detector_report.json` 是一个分类的公尺文件。87课结尾处读取它以达到可信度。
