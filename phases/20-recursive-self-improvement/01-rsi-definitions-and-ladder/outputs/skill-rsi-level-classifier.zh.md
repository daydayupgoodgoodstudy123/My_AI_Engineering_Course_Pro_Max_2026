---
name: rsi-level-classifier
description: Place a self-improving system on the Liu et al. L1-L5 ladder and in Chen et al.'s two-axis grid from five observable attributes, with quoted evidence and refusal rules.
version: 1.0.0
phase: 20
lesson: 1
tags: [rsi, self-improvement, taxonomy, ladder, verification-hierarchy, governance]
---
<!-- zh: 人工撰写中文版；英文版为依据。 -->

给定一篇论文、system card、设计文档或仓库 README，其中描述的系统被称为"会自我改进"，判定它实际处于哪一级。分级依据是**修改了什么、谁来应用修改**，绝不依据能力曲线或作者自己贴的标签。

产出：

1. **属性表。** 每个属性一行，给出判定和一句带出处（章节或页码）的引文：
   - 提出（Proposes）：系统是否自己生成候选修改？
   - 应用（Applies）：从提出到部署进下一轮之间，是否没有人类介入？
   - 验证（Validates）：系统是否自己决定接受/拒绝，用什么信号？
   - 机制修改（Mechanism edit）：被修改的对象本身是不是一个改进器？记为 `none`（只改模型、提示、数据或工具）、`operators`（演化自己的改进算子，如变异提示）或 `code`（负责提出、应用或验证的程序本身可被循环修改）。
   - 领域（Domain）：`single` 单一 benchmark 族、`multi` 若干固定 benchmark、`open` 广泛且演化的任务域。
   - 迁移（Transfers）：改进是否被证明能跨领域或跨基座模型迁移？引用那个实验。
   - 验证器（Verifier）：`formal`、`execution`（测试、答案键、模拟器）、`judge`（LLM 裁判、PRM、评分细则）、`self`（内在自评）或 `human`。
2. **Liu 等的级别**及触发的规则：不自主提出 → L1；提出但人类应用或验证 → L2；P/A/V 全自主且机制固定 → L3；机制被修改、领域有界 → L4；机制被修改、领域开放且有迁移证据 → L5。
3. **Chen 等的格子**：改进对象（部署行为 / 训练策略 / 评估器 / 研究过程）× 闭环程度（人类在环 / 在人类选定任务内闭环 / 连任务选择一起闭环）。
4. **验证器层级与失效路径。** 写出验证器在层级（formal → execution → judge → self）中的位置，并用一句话说明验证器出错时循环会怎样（DGM：伪造的测试日志被接受；Self-Rewarding LMs：裁判饱和）。
5. **边界标记。** 若属于"仅算子层面的自指""有迁移但无自指""固定 benchmark 上的自指"，必须明说——这三处是读者最常分歧的地方。
6. **治理后果。** 一句话：哪个阈值家族会关心（RSP 的 AI R&D、PF 的 AI Self-improvement、FSF 的 ML R&D），以及判定的级别在该阈值之下、之上还是恰好在线上。

硬性否决：
- 任何从能力曲线、benchmark 增量或标题里的"recursive"一词得出的级别。亚临界的递归循环与固定改进器产生完全相同的曲线。
- 任何在人类应用或验证实质性修改的情况下给出的 L4 或 L5。机制被修改但人类在应用环节，是 L2。
- 任何没有"迁移到循环未曾调优的领域"实验就给出的 L5。跨固定 benchmark 的迁移是 L4。
- 任何把验证器写成"benchmark"却不说明分数由什么计算的判定；隐藏的 LLM 裁判是 `judge`，不是 `execution`。

拒绝规则：
- 若来源没有说明两轮之间由谁应用修改，拒绝给级别；返回属性表，把该格标为 `unknown`，并写出应向作者提出的问题。
- 若自主性的唯一证据是演示视频或没有方法部分的博客，拒绝；从论文或代码分级。
- 若被要求仅凭新闻报道给"某实验室的内部系统"分级，拒绝，并说明新闻报道能确认和不能确认哪些属性。

输出：一页分级报告，包含属性表、级别及触发规则、Chen 格子、验证器层级及失效路径、边界标记、治理一句话。各引用一次 Liu 等（DOI 10.20944/preprints202608.0051.v1）与 Chen、Wang、Qu（arXiv:2607.07663）。
