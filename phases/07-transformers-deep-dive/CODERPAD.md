# 07-transformers-deep-dive：CoderPad 练习

本章 16 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [Why Transformers — The Problems with RNNs](01-why-transformers/coderpad/README.md) | 并行加速上限 | 单头注意力 |
| 02 | [Self-Attention from Scratch](02-self-attention-from-scratch/coderpad/README.md) | 单头注意力 | 数值稳定的 Softmax |
| 03 | [Multi-Head Attention](03-multi-head-attention/coderpad/README.md) | 矩阵乘法 | 单头注意力 |
| 04 | [Positional Encoding — Sinusoidal, RoPE, ALiBi](04-positional-encoding/coderpad/README.md) | Sinusoidal 位置编码 | 二维仿射变换 |
| 05 | [The Full Transformer — Encoder + Decoder](05-full-transformer/coderpad/README.md) | 单头注意力 | 因果与窗口 Attention Mask |
| 06 | [BERT — Masked Language Modeling](06-bert-masked-language-modeling/coderpad/README.md) | 受限解码分布 | 分类交叉熵 |
| 07 | [GPT — Causal Language Modeling](07-gpt-causal-language-modeling/coderpad/README.md) | 因果与窗口 Attention Mask | Perplexity 与长度 |
| 08 | [T5, BART — Encoder-Decoder Models](08-t5-bart-encoder-decoder/coderpad/README.md) | 单头注意力 | 受限解码分布 |
| 09 | [Vision Transformers (ViT)](09-vision-transformers/coderpad/README.md) | 图像 Patch 切分 | Sinusoidal 位置编码 |
| 10 | [Audio Transformers — Whisper Architecture](10-audio-transformers-whisper/coderpad/README.md) | 音频分帧 | 单头注意力 |
| 11 | [Mixture of Experts (MoE)](11-mixture-of-experts/coderpad/README.md) | 稀疏路由 Top-K | 数值稳定的 Softmax |
| 12 | [KV Cache, Flash Attention & Inference Optimization](12-kv-cache-flash-attention/coderpad/README.md) | KV Cache 内存预算 | 单头注意力 |
| 13 | [Scaling Laws](13-scaling-laws/coderpad/README.md) | 模型参数与内存估算 | 并行加速上限 |
| 14 | [Build a Transformer from Scratch — The Capstone](14-build-a-transformer-capstone/coderpad/README.md) | 因果与窗口 Attention Mask | 模型参数与内存估算 |
| 15 | [Attention Variants — Sliding Window, Sparse, Differential](15-attention-variants/coderpad/README.md) | 因果与窗口 Attention Mask | 稀疏路由 Top-K |
| 16 | [Speculative Decoding — Draft, Verify, Repeat](16-speculative-decoding/coderpad/README.md) | 推测解码前缀验收 | Perplexity 与长度 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
