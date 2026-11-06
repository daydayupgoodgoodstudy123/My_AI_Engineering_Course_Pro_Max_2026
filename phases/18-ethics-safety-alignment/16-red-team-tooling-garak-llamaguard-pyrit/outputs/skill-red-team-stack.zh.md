---
name: red-team-stack
description: Recommend a red-team tool stack and configuration for a given deployment.
version: 1.0.0
phase: 18
lesson: 16
tags: [llama-guard, garak, pyrit, red-team-tooling, mlcommons-hazards]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以部署描述,建议红色队工具堆和回归加速。

显示 :

1. 分类位置。 建议 Llama 输入、输出或两者兼备的警卫(3-8B、3-1B-INT4或4-12B)。 Llama 4号警卫
2. 探测器扫描器配置。 建议与部署相关的加拉克探测器 : hallucination (用于 RAG systems), data leakage (以PII为邻) prompt injection (always), jailbreaks (总是)指定 Prompt- 保镖86M+ Llama- 顶端对齐保护罩 evaluation.
3. 运动管弦手。 建议 PyRIT 用于以具有新能力的模型为对象的预释放运动。 指定要运行的转换器链( 参数、 编码、 翻译、 角色扮演) 和 管弦( 复制升级, 使用 TAP 分支) 。
4. 夏洛克夜夜回归 极速释放 Llama 警卫不断部署。
5. Judge calibration。指定法官 LLM (GPT-4涡轮,强力,内部) 每一个工具使用。 calibration 驱动器报告 ASR。

艰难的拒绝 :
- 任何部署,但至少没有一次 Llama 保护类输入或输出分类器
- 任何释放,没有加拉克或相等的单向回归。
- 任何高压部署都没有在释放前进行类似PyRIT运动。

拒绝规则 :
- 如果用户要求一个单一的“最佳”工具,就拒绝——三个层覆盖不同的层,是一层层而不是替换。
- 如果用户要求采用全对齐的商业替代方法,则拒绝建议,指出2026年的状态:三种开放工具是目前的最佳做法堆。

输出: 一份一页的建议, 列出分类器位置、 探测配置、 运动管弦、 回归音节和判断身份 。 Cite Meta (arXiv: 2407.21783), NVIDIA Garak 和 Microsoft PyRIT 各自一次 。
