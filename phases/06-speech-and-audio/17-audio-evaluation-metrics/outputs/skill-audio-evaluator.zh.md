---
name: audio-evaluator
description: Pick metrics, benchmarks, normalization rules, and reporting format for any audio model release.
version: 1.0.0
phase: 6
lesson: 17
tags: [evaluation, wer, mos, utmos, eer, der, fad, mmau, leaderboard]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定任务（ASR / TTS /克隆/扬声器验证/分类/分类/音乐/ LALM / streaming S2S），输出：

1. 主要指标。 WER · MOS · UTMOS · SECS · EER · DER · mAP · FAD · MMAU-Pro 精度 · 延迟 P95。一种选择。
2. 次要指标。 1-3 个附加轴（速度、多样性、鲁棒性）和原因。
3. Normalization 规则。小写、标点符号、数字扩展、空格折叠。使用 Whisper-normalizer 或自定义，记录下来。
4. 公共基准。进行报告的规范排行榜（Open ASR、TTS Arena、MMAU-Pro、VoxCeleb1-O、AudioSet、LongAudioBench 等）。
5. 内部设置。保留具有 N 个样本的域数据；人口统计/声学切片细分。
6. 报告格式。分布（延迟为 P50/P95/P99；分类为每类召回；MMAU 为每类别）。发行说明模板。

拒绝单个数字 evaluation 的延迟（报告百分位数）。拒绝仅聚合进行分类（按类别报告）。拒绝没有 MOS/UTMOS 和 SECS 的 TTS 发布（克隆时）。拒绝没有 WER normalization 规范的 ASR 版本。拒绝只用 FAD 发布音乐——始终与人类 MOS 面板配对。

输入示例：“发布新的英语-西班牙语会话 TTS。需要说服团队它比现有的 Cartesia-Sonic 基线更好。”

输出示例：
- 主要：UTMOS（每种语言 50 个 prompts 上的配对音频样本）+ 人工面板 MOS（每种语言 20 个听众，盲 A/B 与基线）。
- 次要：TTFA 中值和 P95（必须匹配基线）； SECS > 0.80 与固定语音参考（无说话人回归）；往返 ASR (Whisper-large-v3-turbo) 的 CER < 2%。
- Normalization：Whisper标准化英语 + Hugging Face 多语言标准化西班牙语，用于往返 WER。
- 公共基准：TTS Arena（英文）和人工分析语音，用于相对 ELO 定位。目标：与最接近的竞争对手的 50 ELO 以内。
- 内部：200 个保留的 prompts（每 lang 100 个），涵盖金钱、日期、产品名称、2 句旁白、情感阅读、代码转换。 10种人口声音。
- 报告：带标题的发行说明 (UTMOS + MOS)、P50/P95 TTFA 直方图、SECS CDF、CER 按类别细分、故障模式标注（代码转换 prompts 在 X% 时失败）。
