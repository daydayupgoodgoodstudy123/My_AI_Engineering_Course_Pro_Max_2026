# 第 06 章分关面试题

每课的 `exam/` 是一套 60 分钟的结对编程题：一个写好一半的服务，5 个测试用 `@pytest.mark.skip("Part N")` 锁住，一次解锁一关。题面是英文 README，用法见每套的 `使用说明.md`。需要 Python 3.10+ 和 pytest，代码只用标准库。

| 课 | 服务 | 1 修 | 2 存 | 3 算 | 4 流 | 5 构 |
|---|---|---|---|---|---|---|
| [01 音频基础](01-audio-fundamentals/exam/) | wavlab | 16-bit PCM 编解码 | WAV 与 wave 模块逐字节一致 | bin 之间的主频、混叠 | 48→16 kHz 流式降采样 | RIFF chunk 树 |
| [02 频谱与 mel](02-spectrograms-mel-features/exam/) | melkit | log-mel 前端 | 特征缓存 | delta 与 CMVN | 在线 CMVN | 配置合并与指纹 |
| [03 音频分类](03-audio-classification/exam/) | cliptag | MFCC 分帧与池化 | SQLite 特征库 | k-NN 与 macro F1 | 窗口打标 | AudioSet 标签树 |
| [04 语音识别](04-speech-recognition-asr/exam/) | asrkit | CTC greedy 与 WER | 转写库（NFC） | CTC prefix beam search | partial / final 词事件 | 词格 n-best |
| [05 Whisper](05-whisper-architecture-finetuning/exam/) | longform | 30 秒窗口计划 | 特殊 token 往返 | 重叠窗口拼接 | 流式转写防幻觉 | LoRA 参数预算 |
| [06 说话人识别](06-speaker-recognition-verification/exam/) | speakerid | trial list 的 EER | 注册库模板 | S-norm 与目标 FAR | 在线 diarization | 聚类树切分 |
| [07 语音合成](07-text-to-speech/exam/) | ttsfront | 文本前端 | 发音词典 | 时长分配到帧 | LLM 文本流切句 | SSML 展开 |
| [08 声音克隆](08-voice-cloning-conversion/exam/) | clonegate | 水印盖章与验证 | 同意登记 | 只用已同意音频的 kNN-VC | 流式水印判定 | 嵌套同意策略 |
| [09 音乐生成](09-music-generation/exam/) | musicbox | prompt 到音符 | 音轨存储（tick） | FAD | 按小节流式输出 | 曲式展开 |
| [10 音频语言模型](10-audio-language-models/exam/) | lalmkit | 解码器输入与 padding | 结果库 | 多选题评分 | 实时上下文预算 | 消息展平 |
| [11 实时音频](11-real-time-audio-processing/exam/) | rtloop | 采集路径与环形缓冲 | 纳秒延迟记录 | 打断（barge-in） | 有界队列流水线 | 处理图与延迟链 |
| [12 语音助手](12-voice-assistant-pipeline/exam/) | voicebot | 工具调度 | 会话库 | 语音工具循环 | 乱序事件算延迟 | 嵌套参数 schema |
| [13 神经音频编解码](13-neural-audio-codecs/exam/) | rvqcodec | RVQ 量化 | 码流按位打包 | k-means++ 码本训练 | 流式编解码 | 树结构 VQ |
| [14 VAD 与轮次](14-voice-activity-detection-turn-taking/exam/) | turnkit | 能量门 | 段落表 | 轮次检测 | VAD 级联 | 重叠话语树 |
| [15 流式语音到语音](15-streaming-speech-to-speech-moshi-hibiki/exam/) | duplex | 双工单步 | 会话日志 | inner monologue 对齐 | 上下行合并 | acoustic delay |
| [16 防伪与水印](16-anti-spoofing-audio-watermarking/exam/) | provenance | 频谱检测器 | 审计日志 | 水印定位 | 伪造告警 | C2PA 来源链 |
| [17 音频评测](17-audio-evaluation-metrics/exam/) | evalsuite | 规范化评分 | 排行榜 | 配对 bootstrap | 流式错误率 | 套件加权得分 |

每套的 `verification.txt` 由 [check_traps.py](../../scripts/exam_curriculum/check_traps.py) 在临时副本上生成：五关默认锁住，参考答案全过，原始代码全挂，Part 1 逐层修复的顺序符合设计，`solution/traps.json` 里的每种错误修法都会被抓住。难度和 60 分钟的时间分配还没有经过真人计时校准。
