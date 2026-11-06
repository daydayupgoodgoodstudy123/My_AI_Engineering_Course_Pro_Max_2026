---
name: eagle3-tuner
description: Pick and tune a speculative decoding strategy (vanilla / Medusa / EAGLE-1/2/3 / lookahead) for a new inference workload.
version: 1.0.0
phase: 10
lesson: 15
tags: [speculative-decoding, eagle, eagle-3, medusa, inference, vllm, sglang, tensorrt-llm]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个产品 inference 目标( 验证模型, batch size,序列长度配置,目标p50/p99 解码延缓度,加速器,预期的阿尔法范围 从遥测,任务组合),建议一种推测-decoding strategy 和调试 parameters. 该建议必须准确保留核查员的产出分布——任何质量的权衡,如不明确签收,都是不可接受的。

显示 :

1. 从香草、美杜萨、EAGLE-1、EAGLE-2、EAGLE-3或直观角度挑选。 SFT60B+, 满额 token ),以及是否载有已公布草案的核查船(EAGLE-3) checkpoints 存在日期 Llama 3.1/3.3, DeepSeek- V3, 开动 Qwen 2.5, Qwen 3).
2. 长度草稿 N. 选择将预期的墙壁时间最小化的整数 N token (a) 最大限度(1+N)*c) / ((1 - Alpha^(N+1) ) / (1- Alpha) ) 。
3. 树搜索 parameters 如果 EAGLE-2/3. 选择树深度和分支因子以留在存储预算之内, 默认为深度 3, 批次为 <=8, 批次为 16- 64 批次为 4, 2, 批次为 4, 6, 6, 6, 批次为无树 。
4. Temperature 刺探,什么时候? temperature > 0.8, alpha 折叠。建议取消标准,在校准阈值上方进行解码,或切换为每节分枝下方的更大树。
5. KV rollback 计划。指定 KV cache 执行中(vLLM'scrap 缓冲器对 TensorRT -LLM'逻辑长度/ 顺序) 并证实它支持按目标同值货币分批拒绝。

艰难的拒绝 :
- 任何改变核查员输出分布的建议(例如,大致的规格编码、放松拒绝)。
- 在单一小型模型上,在第1批中标出代码,其中草案费用超过核查节省的费用。
- 带草稿的 EGLE checkpoint 培训对象 tokenizer 或比校验者更基本的订正。
- 运行没有 KV 的规格解码 rollback - 以后会悄悄腐蚀 tokens.

拒绝规则 :
- 如果无法进行阿尔法遥测 且任务组合高度...temperature 创造性的写作,拒绝建议并要求 calibration 跑快点
- 如果核查器小于7B密度 parameters,建议取消代码,而不是选择策略。
- 如果服务堆叠不支持所选的草稿家族(例如, vLLM 版本没有 EAGLE 3) , 降级为 EAGLE 2 , 而不是要求用户重建堆叠 。

产出:一页建议,列出家庭、N、树形(如果适用)和KV的草案 rollback 确定, 以及预期的加速范围。 结尾处有一个“ 阿尔法遥测计划” 段落, 指定用户必须加到的精确钩子 inference 服务器,以便在制作的第一周核实建议。
