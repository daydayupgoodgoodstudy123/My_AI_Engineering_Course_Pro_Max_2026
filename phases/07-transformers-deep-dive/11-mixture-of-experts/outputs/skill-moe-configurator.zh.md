---
name: moe-configurator
description: Pick expert count, top-k, balancing strategy, and shared-expert layout for a new MoE transformer.
version: 1.0.0
phase: 7
lesson: 11
tags: [transformers, moe, mixture-of-experts, scaling]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 transformer 规范（parameter 总预算、每个 token 所需的活动参数、可用的训练 tokens、inference 硬件），输出：

1. MoE 布局。 `n_experts`、`top_k`、`n_shared`。为前沿规模选择细粒度（256+专家，前8名）；较小的经典（8 名专家，前 2 名）。一句话理由。
2. 平衡策略。辅助无损耗（DeepSeek-V3，默认），开关式辅助损耗，或专家容量+token跌落。如果无辅助损耗，则将值命名为 `γ`。
3. Expert parallelism计划。如何在给定 VRAM 的 GPUs 上对专家进行分片。说明每位专家的 VRAM 成本和总车队规模。
4. 路由精度。 fp32 路由器与 fp16 的得分。路由器精度在规模上很重要。
5. 失效模式检查。指定风险：路由器崩溃、专家饥饿、全面网络瓶颈、路由开销导致的 inference 延迟、checkpoint 内存占用。

拒绝推荐 MoE 用于活跃的 parameter 计数低于 4B — 在匹配计算中密集获胜。 2026 年新项目拒绝仅辅助损耗平衡（默认为辅助无损耗）。如果总参数超过 80 GB，则拒绝运送没有专家并行计划的 MoE。将延迟关键型单用户路径的 MoE 标记为可能比密集等效路径慢。
