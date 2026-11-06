# 12-multimodal-ai：CoderPad 练习

本章 25 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [Vision Transformers and the Patch-Token Primitive](01-vision-transformer-patch-tokens/coderpad/README.md) | 图像 Patch 切分 | Sinusoidal 位置编码 |
| 02 | [CLIP and Contrastive Vision-Language Pretraining](02-clip-contrastive-pretraining/coderpad/README.md) | Embedding 余弦相似度 | 分类交叉熵 |
| 03 | [From CLIP to BLIP-2 — Q-Former as Modality Bridge](03-blip2-qformer-bridge/coderpad/README.md) | 单头注意力 | 矩阵乘法 |
| 04 | [Flamingo and Gated Cross-Attention for Few-Shot VLMs](04-flamingo-gated-cross-attention/coderpad/README.md) | 单头注意力 | Rectified Flow 一步积分 |
| 05 | [LLaVA and Visual Instruction Tuning](05-llava-visual-instruction-tuning/coderpad/README.md) | 受限解码分布 | 上下文预算装箱 |
| 06 | [Any-Resolution Vision: Patch-n'-Pack and NaFlex](06-any-resolution-patch-n-pack/coderpad/README.md) | 图像 Patch 切分 | 有界批处理装箱 |
| 07 | [Open-Weight VLM Recipes: What Actually Matters](07-open-weight-vlm-recipes/coderpad/README.md) | 模型参数与内存估算 | 对称整数化 |
| 08 | [LLaVA-OneVision: Single-Image, Multi-Image, Video in One Model](08-llava-onevision-single-multi-video/coderpad/README.md) | 视频均匀采样 | 图像 Patch 切分 |
| 09 | [Qwen-VL Family and Dynamic-FPS Video](09-qwen-vl-family-dynamic-fps/coderpad/README.md) | 视频均匀采样 | 上下文预算装箱 |
| 10 | [InternVL3: Native Multimodal Pretraining](10-internvl3-native-multimodal/coderpad/README.md) | 图像 Patch 切分 | 模型参数与内存估算 |
| 11 | [Chameleon and Early-Fusion Token-Only Multimodal Models](11-chameleon-early-fusion-tokens/coderpad/README.md) | 重叠窗口切块 | 受限解码分布 |
| 12 | [Emu3: Next-Token Prediction for Image and Video Generation](12-emu3-next-token-for-generation/coderpad/README.md) | 因果与窗口 Attention Mask | 向量量化最近码字 |
| 13 | [Transfusion: Autoregressive Text + Diffusion Image in One Transformer](13-transfusion-autoregressive-diffusion/coderpad/README.md) | 前向加噪 | 因果与窗口 Attention Mask |
| 14 | [Show-o and Discrete-Diffusion Unified Models](14-show-o-discrete-diffusion-unified/coderpad/README.md) | 受限解码分布 | 前向加噪 |
| 15 | [Janus-Pro: Decoupled Encoders for Unified Multimodal Models](15-janus-pro-decoupled-encoders/coderpad/README.md) | Embedding 余弦相似度 | 线性层前向 |
| 16 | [MIO and Any-to-Any Streaming Multimodal Models](16-mio-any-to-any-streaming/coderpad/README.md) | 优先级任务调度 | 分位数与 Goodput |
| 17 | [Video-Language Models: Temporal Tokens and Grounding](17-video-language-temporal-grounding/coderpad/README.md) | 视频均匀采样 | 边框 IoU |
| 18 | [Long-Video Understanding at Million-Token Context](18-long-video-million-token/coderpad/README.md) | 上下文预算装箱 | KV Cache 内存预算 |
| 19 | [Audio-Language Models: the Whisper to Audio Flamingo 3 Arc](19-audio-language-whisper-to-af3/coderpad/README.md) | 音频分帧 | CTC 贪心解码 |
| 20 | [Omni Models: Qwen2.5-Omni and the Thinker-Talker Split](20-omni-models-thinker-talker/coderpad/README.md) | 依赖计划拓扑排序 | 优先级任务调度 |
| 21 | [Embodied VLAs: RT-2, OpenVLA, π0, GR00T](21-embodied-vlas-openvla-pi0-groot/coderpad/README.md) | Rectified Flow 一步积分 | 独立权限与批准 |
| 22 | [Document and Diagram Understanding](22-document-diagram-understanding/coderpad/README.md) | BIO 标签到实体片段 | 图像 Patch 切分 |
| 23 | [ColPali and Vision-Native Document RAG](23-colpali-vision-native-rag/coderpad/README.md) | Embedding 余弦相似度 | 检索指标 |
| 24 | [Multimodal RAG and Cross-Modal Retrieval](24-multimodal-rag-cross-modal/coderpad/README.md) | 倒数排名融合 | 上下文预算装箱 |
| 25 | [Multimodal Agents and Computer-Use (Capstone)](25-multimodal-agents-computer-use/coderpad/README.md) | 独立权限与批准 | 词法路径包含边界 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
