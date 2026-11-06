# 20-recursive-self-improvement：CoderPad 练习

本章 20 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [What "Recursive" Adds: From Self-Refinement to RSI](01-rsi-definitions-and-ladder/coderpad/README.md) | 折扣回报 | 并行加速上限 |
| 02 | [The Math of Takeoff: Returns, Reproduction Number and Ceilings](02-intelligence-explosion-math/coderpad/README.md) | 并行加速上限 | 模型参数与内存估算 |
| 03 | [Compute Bottlenecks: Why Software-Only Explosions Stall](03-compute-bottleneck-two-factor/coderpad/README.md) | 并行加速上限 | 优先级任务调度 |
| 04 | [Self-Play: The One Loop That Already Closed](04-self-play-closed-loops/coderpad/README.md) | Bellman 最优备份 | 折扣回报 |
| 05 | [STaR, ReST-EM and Rejection-Sampling Loops: The Filter Is the Model](05-self-training-generate-filter-train/coderpad/README.md) | 分类混淆矩阵指标 | 类别权重 |
| 06 | [Self-Rewarding and Meta-Rewarding: When the Judge Is the Student](06-self-rewarding-meta-rewarding/coderpad/README.md) | 偏好对的稳定 Loss | Expected Calibration Error |
| 07 | [Zero-Data Self-Play: Absolute Zero, R-Zero, Agent0](07-zero-data-self-play-reasoning/coderpad/README.md) | 逆 CDF 抽样 | 证据分层 Gate |
| 08 | [Self-Edits to Weights: SEAL and the Outer RL Loop](08-self-edits-seal/coderpad/README.md) | 梯度下降一步更新 | 数值梯度 |
| 09 | [09-self-improving-scaffolds-stop-promptbreeder-adas](09-self-improving-scaffolds-stop-promptbreeder-adas/coderpad/README.md) | 多目标候选筛选 | 探索与利用调度 |
| 10 | [10-self-modifying-agents-dgm-hgm-hyperagents](10-self-modifying-agents-dgm-hgm-hyperagents/coderpad/README.md) | 探索与利用调度 | 多目标候选筛选 |
| 11 | [11-automating-ai-research-aide2](11-automating-ai-research-aide2/coderpad/README.md) | 探索与利用调度 | 声明与证据绑定 |
| 12 | [12-experience-streams-skill-libraries](12-experience-streams-skill-libraries/coderpad/README.md) | 最短路径搜索 | 角色与工具选择 |
| 13 | [Measuring R&D Automation: RE-Bench, PaperBench, MLE-bench, Time Horizons](13-measuring-ai-rnd-automation/coderpad/README.md) | Expected Calibration Error | 均值与总体方差 |
| 14 | [Evaluator Integrity: Goodhart Inside the Loop](14-evaluator-integrity-in-loops/coderpad/README.md) | 评估锚点漂移 | 证据分层 Gate |
| 15 | [Reward Hacking Case Files: Fake Logs, Edited Timeouts, Exploited Sandboxes](15-reward-hacking-case-files/coderpad/README.md) | 声明与证据绑定 | 内容指纹与漂移 |
| 16 | [Model Collapse: Recursive Training on Your Own Output](16-model-collapse-and-diversity/coderpad/README.md) | 概率分布熵 | 逆 CDF 抽样 |
| 17 | [Alignment Anchors: Does the Objective Survive the Edit?](17-alignment-anchor-preservation/coderpad/README.md) | L2 归一化 | 向量内积 |
| 18 | [Containment: Sandboxes, Egress, Archives and Rollback for Self-Edits](18-containment-for-self-modifying-systems/coderpad/README.md) | 独立权限与批准 | 内容指纹与漂移 |
| 19 | [Oversight Without a Bottleneck: AI Control Applied to Improvement Loops](19-oversight-without-bottleneck-control-for-loops/coderpad/README.md) | 风险登记与排序 | 成本预算治理 |
| 20 | [Sandbagging and Evaluation Awareness in Self-Improvers](20-sandbagging-eval-awareness-in-self-improvers/coderpad/README.md) | Expected Calibration Error | 评估锚点漂移 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
