---
name: 3d-pipeline
description: Choose a 3D generation or reconstruction pipeline given input type, output format, and use case.
version: 1.0.0
phase: 8
lesson: 12
tags: [3d, gaussian-splatting, nerf, mesh]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定输入（文本 prompt / 一张图像 / 几张图像 / 照片捕获 / 视频）、目标输出（网格 / 高斯 splat / NeRF / 点云）和用例（实时渲染、游戏引擎、AR / VR、电影），输出：

1. 管道。 (a) 多视图扩散 + 3D 拟合 (SV3D、CAT3D + 3DGS)、(b) 直接单次拍摄 (LRM、TripoSR、InstantMesh)、(c) 使用 PBR 的文本到网格 (Meshy 4、Rodin Gen-1.5、Hunyuan3D 2.0)、(d) 照片捕捉 + 3DGS (Gsplat、Postshot、Scaniverse)。
2. 基本模型+托管。命名模型+开放/托管。包括商业用途的许可相关性。
3. 迭代预算。首次输出的预期时间、迭代成本、细化策略。
4. 拓扑+材料。需要重新网格化吗？ PBR 通道要求（反照率、粗糙度、金属、法线）？ UV 布局自动还是手动？
5. 评估。 SSIM 保留视图、CLIP 分数、网格防水性、多边形计数、纹理分辨率。
6. 平台目标。 Unity / Unreal / Blender / web (third.js / Babylon) / AR (USDZ / glb)。

拒绝在没有网格转换通道的情况下将 3DGS 直接传送到游戏引擎中（大多数引擎本身不渲染 splats）。对于复杂的铰接角色，请拒绝文本转 3D - 请改用可感知绑定的管道。当下游工具无法渲染 NeRF（大多数 DCC 工具）时，标记任何 NeRF-only 输出。
