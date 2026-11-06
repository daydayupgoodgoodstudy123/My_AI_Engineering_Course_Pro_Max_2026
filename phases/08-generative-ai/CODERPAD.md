# 08-generative-ai：CoderPad 练习

本章 15 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [Generative Models — Taxonomy & History](01-generative-models-taxonomy-history/coderpad/README.md) | 概率分布熵 | 逆 CDF 抽样 |
| 02 | [Autoencoders & Variational Autoencoders (VAE)](02-autoencoders-vae/coderpad/README.md) | 回归误差与形状 | 逆 CDF 抽样 |
| 03 | [GANs — Generator vs Discriminator](03-gans-generator-discriminator/coderpad/README.md) | 分类交叉熵 | 梯度下降一步更新 |
| 04 | [Conditional GANs & Pix2Pix](04-conditional-gans-pix2pix/coderpad/README.md) | 二维仿射变换 | 回归误差与形状 |
| 05 | [StyleGAN](05-stylegan/coderpad/README.md) | 均值与总体方差 | 线性层前向 |
| 06 | [Diffusion Models — DDPM from Scratch](06-diffusion-ddpm-from-scratch/coderpad/README.md) | 前向加噪 | Warmup 与余弦学习率 |
| 07 | [Latent Diffusion & Stable Diffusion](07-latent-diffusion-stable-diffusion/coderpad/README.md) | 前向加噪 | 对称整数化 |
| 08 | [ControlNet, LoRA & Conditioning](08-controlnet-lora-conditioning/coderpad/README.md) | LoRA 增量与参数量 | Rectified Flow 一步积分 |
| 09 | [Inpainting, Outpainting & Image Editing](09-inpainting-outpainting-editing/coderpad/README.md) | 掩码游程编码 | 前向加噪 |
| 10 | [Video Generation](10-video-generation/coderpad/README.md) | 视频均匀采样 | Rectified Flow 一步积分 |
| 11 | [Audio Generation](11-audio-generation/coderpad/README.md) | 音频分帧 | 向量量化最近码字 |
| 12 | [3D Generation](12-3d-generation/coderpad/README.md) | 二维仿射变换 | Rectified Flow 一步积分 |
| 13 | [Flow Matching & Rectified Flows](13-flow-matching-rectified-flows/coderpad/README.md) | Rectified Flow 一步积分 | 梯度下降一步更新 |
| 14 | [Evaluation — FID, CLIP Score, Human Preference](14-evaluation-fid-clip-score/coderpad/README.md) | Embedding 余弦相似度 | 均值与总体方差 |
| 19 | [Visual Autoregressive Modeling (VAR): Next-Scale Prediction](19-visual-autoregressive-var/coderpad/README.md) | 因果与窗口 Attention Mask | 受限解码分布 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
