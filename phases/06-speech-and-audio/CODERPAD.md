# 06-speech-and-audio：CoderPad 练习

本章 17 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [Audio Fundamentals — Waveforms, Sampling, Fourier Transform](01-audio-fundamentals/coderpad/README.md) | 离散傅里叶变换 | 能量 VAD 边界 |
| 02 | [Spectrograms, Mel Scale & Audio Features](02-spectrograms-mel-features/coderpad/README.md) | 音频分帧 | 频率与 Mel 转换 |
| 03 | [Audio Classification — From k-NN on MFCCs to AST and BEATs](03-audio-classification/coderpad/README.md) | 能量 VAD 边界 | 确定性的最近邻 |
| 04 | [Speech Recognition (ASR) — CTC, RNN-T, Attention](04-speech-recognition-asr/coderpad/README.md) | CTC 贪心解码 | 编辑距离 |
| 05 | [Whisper — Architecture & Fine-Tuning](05-whisper-architecture-finetuning/coderpad/README.md) | 重叠窗口切块 | 模型参数与内存估算 |
| 06 | [Speaker Recognition & Verification](06-speaker-recognition-verification/coderpad/README.md) | Embedding 余弦相似度 | Expected Calibration Error |
| 07 | [Text-to-Speech (TTS) — From Tacotron to F5 and Kokoro](07-text-to-speech/coderpad/README.md) | 时间序列滞后特征 | Warmup 与余弦学习率 |
| 08 | [Voice Cloning & Voice Conversion](08-voice-cloning-conversion/coderpad/README.md) | Embedding 余弦相似度 | 水印比特一致率 |
| 09 | [Music Generation — MusicGen, Stable Audio, Suno, and the Licensing Earthquake](09-music-generation/coderpad/README.md) | N-gram 计数 | 逆 CDF 抽样 |
| 10 | [Audio-Language Models — Qwen2.5-Omni, Audio Flamingo, GPT-4o Audio](10-audio-language-models/coderpad/README.md) | 音频分帧 | 单头注意力 |
| 11 | [Real-Time Audio Processing](11-real-time-audio-processing/coderpad/README.md) | 能量 VAD 边界 | 分位数与 Goodput |
| 12 | [Build a Voice Assistant Pipeline — The Phase 6 Capstone](12-voice-assistant-pipeline/coderpad/README.md) | 合法状态转换 | 成本预算治理 |
| 13 | [Neural Audio Codecs — EnCodec, SNAC, Mimi, DAC and the Semantic-Acoustic Split](13-neural-audio-codecs/coderpad/README.md) | 向量量化最近码字 | 回归误差与形状 |
| 14 | [Voice Activity Detection & Turn-Taking — Silero, Cobra, and the Flush Trick](14-voice-activity-detection-turn-taking/coderpad/README.md) | 能量 VAD 边界 | 合法状态转换 |
| 15 | [Streaming Speech-to-Speech — Moshi, Hibiki, and Full-Duplex Dialogue](15-streaming-speech-to-speech-moshi-hibiki/coderpad/README.md) | 向量量化最近码字 | 分位数与 Goodput |
| 16 | [Voice Anti-Spoofing & Audio Watermarking — ASVspoof 5, AudioSeal, WaveVerify](16-anti-spoofing-audio-watermarking/coderpad/README.md) | 水印比特一致率 | 分类混淆矩阵指标 |
| 17 | [Audio Evaluation — WER, MOS, UTMOS, MMAU, FAD, and the Open Leaderboards](17-audio-evaluation-metrics/coderpad/README.md) | 编辑距离 | Expected Calibration Error |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
