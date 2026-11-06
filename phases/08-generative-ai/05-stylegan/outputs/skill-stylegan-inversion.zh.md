---
name: stylegan-inversion
description: Choose an inversion and editing pipeline for a pretrained StyleGAN over a real photo.
version: 1.0.0
phase: 8
lesson: 05
tags: [stylegan, inversion, editing]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定真实照片+预训练的StyleGAN checkpoint（FFHQ-1024，StyleGAN-XL，自定义微调）和目标编辑（年龄，微笑，姿势，头发，身份保留），输出：

1. 反演法。 e4e（快速、低保真度）、ReStyle（迭代 encoder）、HyperStyle（超网络）、PTI（关键调整）或直接 W 优化。一句话原因与保真度与速度相关。
2. 目标空间。 W、W+ 或样式空间。权衡：W = 最解缠结但保真度最低，W+ = 每层 w，StyleSpace = 通道级。
3. 编辑方向。命名方向源：InterFaceGAN（基于 SVM）、StyleSpace 通道、GANSpace PCA 或学习分类器。
4. 保真预算。身份漂移前的 LPIPS 阈值； rollback 启发式。
5. 评估。 ID 相似度（ArcFace 余弦）、原始 LPIPS、编辑强度（目标属性分类器得分）。

拒绝任何直接在Z（纠缠）中编辑的管道。拒绝未经身份检查的大编辑（W 中 >1.5 sigma）。标记需要开放域编辑的请求（例如“让他成为卡通”）——这些请求需要扩散 + IP 适配器，而不是 StyleGAN。
