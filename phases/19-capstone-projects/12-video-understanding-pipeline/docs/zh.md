<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-12--video-understanding-pipeline-scene-qa-search"></a>

# 综合项目 12：视频理解流程——场景、问答与搜索

> 12个实验室生产了马雷戈+Pegasus。 API。AI2的闪光灯2号已公开 checkpoints. Gemini 长文字处理本地视频的小时。 TimeLens- 100K 定义的时间 grounding 2026年管道已固定:场景分割、每场字幕+ embedding,记录 alignment,多矢量指数,以及一个查询,回答时标加框架预览(起始、结束)。 hallucination 计算和行动问题。

**类型:** Capstone
**语言:** Python (pipeline), TypeScript (UI)
**先修要求:** 阶段4(CV),阶段6(发言),阶段7(transformers阶段11(LLM 工程,第12阶段(多式),第17阶段(基础设施)
**涉及阶段：**P4 · P6 · P7 · P11 · P12 · P17
**时间:** 30小时

<a id="problem"></a>

## 问题

长式视频QA是2026年规模最缺乏带宽的多式联运问题。 Gemini 2.5 Pro可以本地阅读两小时的视频,但将100小时的视频摄入到可查询的文体中,仍然需要一个场景级索引。 制作形状结合了场景分块(TransNetV2或PySceneSetatory),每场景字幕与VLM(VLM)合在一起(TromNetV2或PySceeneSetatory)。Gemini 2.5, Quen3-VL-Max, 或 Molmo 2, 笔录 alignment (Whiper-V3-turbo, 带有字时间戳) 和一个多矢量索引, 存储标题、 框架 embedding,并同时进行笔录。查询管道的答案,加上(开始、结束)时间戳和框架预览。

基准是公开的(活动网络-QA、NeXT-GQA)加上你自己的100号格子定制。 Hallucination 计算和行动类型的问题就是已知的硬故障类别;综合项目明确测量了它。

<a id="concept"></a>

## 概念

三个管道在毒气中平行运行 **场景分割** 将视频切入场景 **VLM 字幕** 每个场景生成一个标题和一个框架 embedding 关键字框上的 **ASR alignment** 生成字级时间戳。 三个串流被连接( 屏幕)_id, 时间范围。 每个场景都以多矢量指数( Qdrant) 获得三种矢量类型 : embedding键盘 embedding,记录 embedding.

询问时,自然语言会对所有三种向量发生火灾;结果与RRF合并;时间-grounding 适配器(TimeLens-type) 精细化顶部场景中的( 启动、 结束) 窗口。 VLM 合成器 (SymeLens- system)Gemini 2.5 Pro或 Quen3-VL-Max) 使用查询+顶部场景+裁剪框和回答,并使用引用的时间戳和框架预览。

该 hallucination 测量很重要。 计算( “ 有多少人进入房间 ” ) 和行动类型 ( “ 主厨在搅拌前会倒吗 ” ) 问题非常不可靠。 报告准确性与描述性问题分开。

<a id="architecture"></a>

## 建筑

```
video file / URL
      |
      v
PySceneDetect / TransNetV2  (scene segmentation)
      |
      +--- per-scene keyframe --- VLM caption + frame embedding
      |                            (Gemini 2.5 Pro / Qwen3-VL-Max / Molmo 2)
      |
      +--- audio channel --- Whisper-v3-turbo ASR + word timestamps
      |
      v
multi-vector Qdrant: {caption_emb, keyframe_emb, transcript_emb}
      |
query:
  dense queries against all three -> RRF merge -> top-k scenes
      |
      v
TimeLens / VideoITG temporal grounding (refine start/end within scene)
      |
      v
VLM synth: query + top scenes + frame previews
      |
      v
answer + (start, end) timestamps + frame thumbs + citations
```

<a id="stack"></a>

## 堆栈

- 场景分离: TransNetV2(第2024-26条现状)或PyScene探测器
- 答:用字节印快速耳语
- VLM 标题 + 答录器 : Gemini 2.5 纯或克文3-VL-Max或摩尔莫 2
- Temporal grounding: 时间线- 100K 培训的适配器或视频ITG
- 索引: 多矢量支持的 Qdrant (标题/ 框架/ 记录)
- 界面: 下15 个带有 HTML5 视频播放器和场景缩略图
- Eval: 活动网- QA, NeXT- GQA, 自定义 100 个问题手贴集
- Hallucination 基准: 带有手贴标签的计算和动作类型子集

```figure
cf-scene-index
```

<a id="build-it"></a>

## 动手实现

1. **最顽固的行尸** 接受 YouTube URL 或本地 MP4。 如果需要, 降为 720 p 。 永久 `{video_id, file_path}`.

2. **场景分割** 运行 TransNetV2 或 PyScene 检测以生产 `[{scene_id, start_ms, end_ms, keyframe_path}]`目标100小时:~6k-8k场景。

3. **SR通行证** 在音频、导出字级时间戳、每张记录片中运行 Whiseper-V3-turbo。

4. **VLM 字幕。** 每一个场景,打电话 Gemini 2.5 使用键盘和短标题模板的Pro(或 Quen3-VL-Max) 。 生成标题+框架 embedding.

5. **多矢量指数。** 包含三个名为矢量的 Qdrant 收藏。 有效载荷 : `{video_id, scene_id, start_ms, end_ms, keyframe_url}`.

6. **Query.** 自然语言问题引发了三个密集的查询; 与 reciprocal rank fusion; 顶部K=5场景。

7. **Temporal grounding.** 在最上面的场景运行时间Lens 式的适配器, 以精细化场景中的( 开始、 结束) 窗口 。

8. **甚高频合成器** Call Gemini 2.5 附有查询+上三段场景剪辑(作为图像或短片)+记录誊本。 `(video_id, start_ms, end_ms)` citations.

9. **Eval.** 运行活动网络- QA 和 NEXT- GQA 构建一个 100 号自定义集。 报告总体准确度+每类分类细目( 计算、 动作、 描述性) 。

<a id="use-it"></a>

## 实际应用

```
$ video-qa ask --url=https://youtube.com/watch?v=X "how many cars pass the intersection in the first minute?"
[scene]    23 scenes detected
[asr]      transcript complete, 4m12s
[index]    69 vectors written (23 scenes x 3)
[query]    top scene: scene 3 [01:32-01:54], confidence 0.84
[ground]   refined window: [00:12-00:58]
[synth]    gemini 2.5 pro, 1.4s
answer:    5 cars pass the intersection between 00:12 and 00:58.
citations: [scene 3: 00:12-00:58]
          [frame preview at 00:14, 00:27, 00:44, 00:51, 00:57]
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-video-qa.md` 即可交付的。根据YouTube URL 或上传视频,管道索引场景和回答问题时标引用。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | Temporal grounding IoU | 长期存在的交叉工会 grounding set |
| 20 | 质量评估准确性 | 内置- GQA 和自定义 100 查询 |
| 20 | 最显著的输出 | 每美元花费的视频播放时间 |
| 20 | 用户界面和引用 UX | 时间戳链接、缩略图条、跳到框架 |
| 15 | Hallucination rate | 分别计算和动作类型准确性 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. Swap Gemini 2.5 用于字幕通行证上的 Quen3-VL-Max。报告人类50度样本的字幕质量三角洲。

2. 减少每场景框架 embedding 改为一个集合矢量,而不是多矢量。测量回收回归。

3. 构建一个“ 计算严格” 模式: 合成器提取每个计算过的实例, 并加贴时间戳和点击用户来校验 。 测量用户验证是否减少 hallucination.

4. 基准摄取成本: 视频每美元小时 跨越三个VLM选择。 选择甜点 。

5. 添加扬声器分解的音稿: 在音频上播放扬音器的对称, 并嵌入每个音频记录。 演示“ 爱丽丝对 X 怎么说? ” 查询 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 场景分割 | 热探测 | 将视频切入镜头 |
| 多矢量指数 | "标题+框架+记录" | 以每个表示式命名矢量的 Qdrant 收藏 |
| Temporal grounding | "什么时候发生的" | 正在为查询答案精细窗口( 启动、 结束) |
| 车架 embedding | "视觉代表" | 矢量 embedding 用于现场和视觉相似 |
| 革命阵线联合 | "Reciprocal rank fusion" | 合并多个排名列表的战略; 经典的混合检索技巧 |
| Counting hallucination | "Miscount" | 关于“多少 X” 问题的已知 VLMs 失败模式 |
| ActivityNet-QA | "视频QA基准" | 长式视频QA精确度基准 |

<a id="further-reading"></a>

## 进一步阅读

- [AI2 闪光2号](https://allenai.org/blog/molmo2) - 打开VLM checkpoints
- [时间期限(CVPR 2026)](https://github.com/TencentARC/TimeLens) - 时间 grounding 在比例尺上
- [Gemini 视频长字符](https://deepmind.google/technologies/gemini) 托管机构
- [VideoDB](https://videodb.io) - 录像乐器 API reference
- [12个实验室 马雷戈+帕加索斯](https://www.twelvelabs.io) 商业参考
- [TransNetV2](https://github.com/soCzech/TransNetV2) 场景分解模型
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) - 经典开放的替代
- [ActivityNet-QA](https://arxiv.org/abs/1906.02467) 参考评价基准
