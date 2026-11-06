---
name: skill-3dgs-export-router
description: Pick the right 3DGS export format (.ply / .splat / glTF KHR_gaussian_splatting / USD) given the downstream viewer or engine
version: 1.0.0
phase: 4
lesson: 22
tags: [3d-gaussian-splatting, export, glTF, OpenUSD, pipeline]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="3dgs-export-router"></a>

# 3DGS 导出路由器

将下游目标映射到正确的 3DGS 文件格式。节省“未加载”调试的时间。

<a id="when-to-use"></a>

## 何时使用

- 训练 3DGS 场景后，在与内容管道共享之前。
- 在研究级 (.ply) 和生产级 (glTF / USD) 格式之间进行选择。
- 管道 handoff：捕捉团队 -> 3DGS 工程师 -> 游戏设计师/VFX 艺术家/Web 开发人员。

<a id="inputs"></a>

## 输入

- `target_engine`：不真实 | 团结 | 全宇宙 | 搅拌机 | 愿景_pro | 三_js | 巴比伦_js | 铯 | 画布 | 超级泼溅
- `priority`：便携性 | 文件_大小 | 质量_保存
- `include_sh_degree`: 0 | 1 | 2 | 3

<a id="format-decision"></a>

## 格式决定

| 目标 | 推荐格式 | 为什么 |
|--------|--------------------|-----|
| 虚幻引擎（虚拟制作） | Volinga 插件或 glTF KHR_gaussian_splatting | 原生虚幻 SDK 路径 |
| Unity（XR/游戏） | .ply 通过 Aras-P Unity-GaussianSplatting 插件 | 社区标准 Unity 管道 |
| NVIDIA Omniverse、皮克斯工具 | OpenUSD 26.03 (UsdVolParticleField3DGaussianSplat) | 本机美元 prim 类型 |
| 苹果视觉专业版 | 开盘USD 26.03 | 原生于visionOS 2.x |
| 搅拌机 | .ply + KIRI 引擎插件 | 社区附加组件读取原始 splats |
| Three.js 网页查看器 | glTF KHR_gaussian_splatting 或 .splat | 浏览器标准，与 `GaussianSplats3D` 配合使用 |
| Babylon.js V9+ | glTF KHR_gaussian_splatting | V9添加了原生支持 |
| Cesium（CesiumJS 1.139+，Cesium for Unreal 2.23+） | glTF KHR_高斯_splatting | 提供明确的支持 |
| 播放画布 | .splat | PlayCanvas 原生量化格式 |
| 超级斯普拉特（编辑） | .ply 或 .splat | 导入+导出 |

<a id="quantisation-trade-offs"></a>

## 量化权衡

- `.ply` 全精度：最大文件，无损，任何查看器。
- `.splat`：缩小 4-8 倍，SH3 系数略有质量损失，PlayCanvas 生态系统标准。
- glTF KHR：通过EXT_meshopt_压缩进行配置；最小，兼容性最高。
- USD：通过USDZ打包压缩； Apple 管道中最小的。

<a id="output-report"></a>

## 输出报告

```
[export plan]
  target:         <engine>
  format:         <name>
  sh degree:      <0|1|2|3>
  compression:    <none|meshopt|quantisation|usdz>
  expected size:  <MB>
  compatible with: <list of viewers>

[pipeline]
  1. source: <.ply from training>
  2. optional: SuperSplat cleanup pass
  3. convert: <tool + CLI or API call>
  4. package: <.gltf / .glb / .usd / .usdz / .splat / .ply>
  5. validate: <viewer sanity check>
```

<a id="rules"></a>

## 规则

- 切勿默默地去除 SH3 系数——它会明显改变镜面反射。
- 如果是`priority == file_size`，推荐使用`.splat`或glTF with meshopt；警告质量损失。
- 对于Apple平台，2026年优先选择USD/USDZ而非glTF； USDZ 拥有一流的visionOS 支持。
- 如果目标查看器的 3DGS 支持是预标准的（2026 年 2 月之前），推荐 `.ply` 和查看器的自定义加载程序； Khronos 标准 glTF 尚未被识别。
- 在移交之前，请务必在至少一个查看器中验证导出的文件；量化过程中会发生无声损坏。
