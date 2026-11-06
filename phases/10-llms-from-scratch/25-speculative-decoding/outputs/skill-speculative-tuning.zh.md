---
name: speculative-tuning
description: Profile a decode workload and pick draft model, draft length K, temperature gate, and fallback policy for speculative decoding.
version: 1.0.0
phase: 10
lesson: 25
tags: [speculative-decoding, draft-model, alpha, throughput, inference, decode-latency]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


考虑到目标模式(规模、家庭、 tokenizer),工作量遥测(任务组合, prompt-vs-decode 编码 token 比例, p50/p99 解码衬隙, 加速器和 HBM 主机室, 平均数 batch size, sampling temperature 现有草案 checkpoints, 输出:

1. 草稿选择。 从同一个家庭中挑选小(Llama-3.2-1B为 Llama- 70B),一个精炼的草稿, 有关目标产出,美杜莎头钉在目标上, 或者“没有标码”, 如果没有接近30%的FLOP成本比率。 tokenizer 与目标字节匹配; 拒绝不匹配 tokenizer.
2. 长度草案[tokens] / (1+K xc) 中, c 是草案与目标的成本比率。使用从 a 中测量的阿尔法显示 K 在 2, 3, 4, 5, 6 中的工作 calibration 运行在 5_000 tokens 默认 K=4 用于聊天, K=6 用于代码, K=2 用于高-temperature 创意的写作
3. Temperature 门 设置 temperature 默认值 0.8; 如果 calibration 显示之前的 Alpha 崩溃。拒绝任何 temperature 门取决于每个请求的检查 增加50微秒以上
4. 树的预算。 如果服务堆叠支持树的起草, 请选择一棵小的固定树( 深2) 。 branch 3-2) 8岁以下批次;32岁以上批次的平链;
5. 后退策略。 列出测量值( 上一个 1 的滑坡- 窗口测量的阿尔法)_000 校验)和服务器跌回平原的阈值( 0. 4下的阿尔法) autoregressive 解码请求流。 包含每份请求的回溯决定寿命 。

拒绝 spec 解码 batch size 高于校验符的值。 超过此点, 未使用的 FLOP 投机者打算浸泡; 吞吐滴。 拒绝给任何任务家庭标码, 其测量值低于 0. 4 ; 顶部草稿占主导, 墙上时钟的悬浮情况恶化 。 拒绝一个在拖放 1 上未验证的草稿 。_000-token 相对于目标的样本:未经验证的草稿是静态 KL 漂移 。

实例投入: "Llama-3.3-70B 8xH100,聊天量,第16批,p50解码28毫秒,p99 60毫秒, temperature 分布值 0.4 / 最大1.2, calibration 在聊天时显示 Alpha 0.78, 在代码上显示0.61。"

输出示例：
- 草案: Llama-3.2-1B-教学。 tokenizer相同家庭,比率大约为0.03。
- K: 4 E级[tokens/核查] =3.4聊天,2.5代码。K=5收益0.1 token 聊天并支付 0.03 额外的 c; 拒绝。
- Temperature 门:0.8. 0.8以上 calibration 设置。
- 树预算:深度2 branch (3,2) KV 抓480 MB 第16批
- 后退: 向上一个窗口滑动 Alpha_以 0.40 下方进行检测 30 秒内解码 然后再进行检测
