---
name: skill-physical-plausibility-checks
description: Automated checks for object permanence, gravity, and continuity on any generated video before shipping
version: 1.0.0
phase: 4
lesson: 28
tags: [video-generation, quality, physics, evaluation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="physical-plausibility-checks"></a>

# 物理合理性检查

生成视频的生产部署需要自动化 guardrails。人工审核无法扩展；物理检查捕捉经典的故障模式。

<a id="when-to-use"></a>

## 何时使用

- 任何从文本或图像生成视频的产品 prompts。
- 在视频生成 API 端点上自动化 QA。
- 在 fine-tuning 或基础模型更新后监控视频模型的质量漂移。

<a id="inputs"></a>

## 输入

- `video`：tensor `(T, H, W, 3)` 或 mp4 的路径。
- 可选参考信息：预期的对象数量、初始场景描述。

<a id="checks"></a>

## 支票

<a id="1-object-permanence"></a>

### 1. 物体持久性
使用 SAM 3.1 Object Multiplex 跟踪跨帧的每次检测。当稳定轨迹消失 <=3 帧并重新出现时进行标记 - 模型暂时丢失对象。当物体在框架中心附近（而不是边缘）消失时发生硬故障；边缘处出现软故障。

<a id="2-motion-smoothness"></a>

### 2. 运动平滑度
连续帧之间的光流应该大部分是连续的。突然的每像素流量峰值表明隐形传态。用RAFT计算流程；标记第 99 个百分位数的流量大小超过中位数 > 10 的帧。

<a id="3-gravity--support"></a>

### 3.重力/支撑
对于检测为固体的物体（食物、球、工具），检查其垂直位置在没有提升动作的情况下不会增加。除非在物体附近检测到“抓握的手”，否则标记向上漂移。

<a id="4-identity-consistency"></a>

### 4. 身份一致性
对于人物或角色，使用跨帧人脸识别 embedding。 Cosine similarity 应在 5 帧窗口中保持 > 0.8，以实现持久身份。低于阈值意味着角色变形。

<a id="5-hands-and-limbs"></a>

### 5. 手和四肢
运行姿势估计器（第 21 课）。标记手部有 > 5 或 < 4 个可见手指的帧；帧间臂长加倍；四肢通过表面与身体相交的地方。

<a id="6-text-rendering-if-prompt-asked-for-text"></a>

### 6.文本渲染（如果prompt要求文本）
如果用户 prompt 在引号中包含字符串，则 OCR 生成的帧并根据请求的字符串计算 CER。标志 > 20% CER。

<a id="report"></a>

## 报告

```
[plausibility]
  video frames:           <T>
  permanence violations:  <N>
  smoothness violations:  <N>
  gravity violations:     <N>
  identity drift:         <N of 5-frame windows>
  limb anomalies:         <N>
  OCR CER vs requested:   <float>

[verdict]
  ship | hold | reject

[samples for review]
  frame ranges where each failure occurred
```

<a id="rules"></a>

## 规则

- 不要对任何单一检查进行硬阻止；当异常总数超过阈值时，汇总分数并保留视频以供审核。
- Weight 身份漂移和永久性违规最高——用户首先注意到它们。
- 记录一段时间内每次检查的失败率；上升趋势通常意味着基础模型已更新或 prompt 分布发生变化。
- 切勿删除已标记的视频；保留它用于模型调试和事后分析。
- 对于敏感内容（人物、儿童、公众人物），无论分数如何，都需要对每个视频进行人工审核。
