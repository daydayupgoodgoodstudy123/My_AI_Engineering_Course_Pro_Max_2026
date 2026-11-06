# 18-ethics-safety-alignment：CoderPad 练习

本章 30 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
核心 6 cases、加分 2 cases。题目是原课程中的一个编码切面，不要求运行完整训练、云服务或 GPU。
相同基础 kernel 会在相关课程复用；请在复盘中区分“未见题”与“重复练习”。
运行方法：进入任一项目的 `coderpad/`，阅读 README/PROMPT，再执行：

```bash
python3 run_tests.py --list
python3 run_tests.py --core
```

初始失败是 TODO 的正常起点；计时结束后才打开 solution 或使用 `--solution`。
面试官材料、评分与复盘模板均在每套目录；计时器自行设置。

| 课号 | 主题与题目入口 | 核心 | 加分 |
| --- | --- | --- | --- |
| 01 | [Instruction-Following as Alignment Signal](01-instruction-following-alignment-signal/coderpad/README.md) | 配置合同校验 | 分类混淆矩阵指标 |
| 02 | [Reward Hacking and Goodhart's Law](02-reward-hacking-goodhart/coderpad/README.md) | 评估锚点漂移 | 分类混淆矩阵指标 |
| 03 | [The Direct Preference Optimization Family](03-direct-preference-optimization-family/coderpad/README.md) | 偏好对的稳定 Loss | 分类交叉熵 |
| 04 | [Sycophancy as RLHF Amplification](04-sycophancy-rlhf-amplification/coderpad/README.md) | 分类混淆矩阵指标 | Expected Calibration Error |
| 05 | [Constitutional AI and RLAIF](05-constitutional-ai-rlaif/coderpad/README.md) | 分类信号合并 | 声明与证据绑定 |
| 06 | [Mesa-Optimization and Deceptive Alignment](06-mesa-optimization-deceptive-alignment/coderpad/README.md) | 证据分层 Gate | 评估锚点漂移 |
| 07 | [Sleeper Agents — Persistent Deception](07-sleeper-agents-persistent-deception/coderpad/README.md) | 评估锚点漂移 | 证据分层 Gate |
| 08 | [In-Context Scheming in Frontier Models](08-in-context-scheming-frontier-models/coderpad/README.md) | 独立权限与批准 | 声明与证据绑定 |
| 09 | [Alignment Faking](09-alignment-faking/coderpad/README.md) | 评估锚点漂移 | Expected Calibration Error |
| 10 | [AI Control — Safety Despite Subversion](10-ai-control-subversion/coderpad/README.md) | 独立权限与批准 | 风险登记与排序 |
| 11 | [Scalable Oversight and Weak-to-Strong Generalization](11-scalable-oversight-weak-to-strong/coderpad/README.md) | 证据分层 Gate | 声明与证据绑定 |
| 12 | [Red-Teaming: PAIR and Automated Attacks](12-red-teaming-pair-automated-attacks/coderpad/README.md) | 分类混淆矩阵指标 | 风险登记与排序 |
| 13 | [Many-Shot Jailbreaking](13-many-shot-jailbreaking/coderpad/README.md) | 上下文预算装箱 | 成本预算治理 |
| 14 | [ASCII Art and Visual Jailbreaks](14-ascii-art-visual-jailbreaks/coderpad/README.md) | 文本归一化与分词 | 分类信号合并 |
| 15 | [Indirect Prompt Injection — Production Attack Surface](15-indirect-prompt-injection/coderpad/README.md) | 声明与证据绑定 | 独立权限与批准 |
| 16 | [Red-Team Tooling — Garak, Llama Guard, PyRIT](16-red-team-tooling-garak-llamaguard-pyrit/coderpad/README.md) | 分类信号合并 | 分类混淆矩阵指标 |
| 17 | [WMDP and Dual-Use Capability Evaluation](17-wmdp-dual-use-evaluation/coderpad/README.md) | 分类混淆矩阵指标 | 类别权重 |
| 18 | [Frontier Safety Frameworks — RSP, PF, FSF](18-frontier-safety-frameworks-rsp-pf-fsf/coderpad/README.md) | 风险登记与排序 | 证据分层 Gate |
| 19 | [Anthropic's Model Welfare Program](19-model-welfare-research/coderpad/README.md) | 声明与证据绑定 | 风险登记与排序 |
| 20 | [Bias and Representational Harm in LLMs](20-bias-representational-harm/coderpad/README.md) | 分组选择率差异 | 分类混淆矩阵指标 |
| 21 | [Fairness Criteria — Group, Individual, Counterfactual](21-fairness-criteria-group-individual-counterfactual/coderpad/README.md) | 分组选择率差异 | Expected Calibration Error |
| 22 | [Differential Privacy for LLMs](22-differential-privacy-for-llms/coderpad/README.md) | 基础隐私预算组合 | 成本预算治理 |
| 23 | [Watermarking — SynthID, Stable Signature, C2PA](23-watermarking-synthid-stable-signature-c2pa/coderpad/README.md) | 水印比特一致率 | 声明与证据绑定 |
| 24 | [Regulatory Frameworks — EU, US, UK, Korea](24-regulatory-frameworks-eu-us-uk-korea/coderpad/README.md) | 配置合同校验 | 声明与证据绑定 |
| 25 | [EchoLeak and the Emergence of CVEs for AI](25-echoleak-cves-for-ai/coderpad/README.md) | 独立权限与批准 | 结构化日志脱敏 |
| 26 | [Model, System, and Dataset Cards](26-model-system-dataset-cards/coderpad/README.md) | 配置合同校验 | 可验证任务交接 |
| 27 | [Data Provenance and Training-Data Governance](27-data-provenance-training-governance/coderpad/README.md) | 声明与证据绑定 | 内容指纹与漂移 |
| 28 | [Alignment Research Ecosystem — MATS, Redwood, Apollo, METR](28-alignment-research-ecosystem/coderpad/README.md) | 声明与证据绑定 | 依赖计划拓扑排序 |
| 29 | [Moderation Systems — OpenAI, Perspective, Llama Guard](29-moderation-systems-openai-perspective-llamaguard/coderpad/README.md) | 分类信号合并 | Expected Calibration Error |
| 30 | [Dual-Use Risk — Cyber, Bio, Chem, Nuclear Uplift](30-dual-use-risk-cyber-bio-chem-nuclear/coderpad/README.md) | 风险登记与排序 | 独立权限与批准 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
