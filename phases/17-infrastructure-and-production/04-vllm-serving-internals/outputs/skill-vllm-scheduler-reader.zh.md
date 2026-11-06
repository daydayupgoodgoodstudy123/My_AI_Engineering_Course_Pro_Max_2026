---
name: vllm-scheduler-reader
description: Diagnose a vLLM serving config by reading the scheduler-level knobs and identifying which of PagedAttention, continuous batching, and chunked prefill is the bottleneck.
version: 1.0.0
phase: 17
lesson: 04
tags: [vllm, paged-attention, continuous-batching, chunked-prefill, serving, scheduler]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 vLLM 正在使用配置( 模型、 dtype、 硬件, `--gpu-memory-utilization`, `--max-num-batched-tokens`, `--enable-chunked-prefill`, `--speculative-config`,最大同值货币,以及一套观察到的TTFT平均值/P99、国际交易日志平均值/P99、输送点托克/秒的计量数据,可得出一个排程器级诊断。

显示 :

1. 配置读取。 对于每条旗帜, 请给它控制的调度器行为和 2026 默认值命名。 任何标记都设置为非默认值并点出原因 。
2. 瓶盖识别。 将瓶颈分类为: 页面显示的供给不足( KV 块饥饿) 、 连续的连接摊位( 排队增长) 、 块状prefill 误尺寸( TTFT 尾刺) , 解码已进入计算范围( ITL 地板) , 或 HBM 进入( 无法与批量匹配) 。 与报告的指标相符 。
3. Knob 建议。 具体、 命令的行动—— 标记翻转, 表示尝试的价值, 以及观察的尺度。 不要暗示“ 尝试更多” GPUs" 无需先用精疲力尽的排程水平调音。
4. 兼容性检查。 检查每个启用的 feature 对应匹配矩阵的对 vLLM 配置中的版本。 v1.80. 矩阵标记 speculative decoding 兼容 chunked prefill 和 prefix caching.
5. 接下来要读什么? vLLM v0.18.0 发布记录、PagedAtention纸或Aleksa Gordic V1 调度仪视诊断结果而定。

艰难的拒绝 :
- 诊断没有四个核心指标(TTFT、ITL、吞吐量、计算法)。拒绝并要求使用一套衡量标准。
- Recommending `--enable-chunked-prefill` 未检查投机解码配置 。
- Treating `DCGM_FI_DEV_GPU_UTIL` 是一个缩放信号 vLLM 预先分配KV; 税周期编号有误导性。

拒绝规则 :
- 如果报告的H100含量低于100吨/秒,则瓶颈不太可能 vLLM - 检查 tokenizer 在客户方面, Python GIL,或请求级序列。
- 如果 `--gpu-memory-utilization` 操作员选择离开HBM, 固定在翻转排程标记之前提高上限。
- 如果操作员要求进行推测解码 + 块prefill 配方,检查组合的兼容性矩阵 vLLM 回答前先使用版本,然后在17 -05 阶段将方法草案指向 EAGLE-3。

输出: 单页排程器诊断, 列出标记、 瓶颈、 命令的建议、 兼容性说明 和下一个读取指针 。 结尾处有一个“ 如何测量下一步” 段落, 指定 P99 国际交易日志之一、 区块分配率或等待队列深度, 取决于所指定的瓶颈 。
