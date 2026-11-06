# 04-computer-vision：CoderPad 练习

本章 28 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [Image Fundamentals — Pixels, Channels, Color Spaces](01-image-fundamentals/coderpad/README.md) | 矩阵转置 | 训练统计量与变换 |
| 02 | [Convolutions from Scratch](02-convolutions-from-scratch/coderpad/README.md) | 一维卷积窗口 | 池化与补齐 |
| 03 | [CNNs — LeNet to ResNet](03-cnns-lenet-to-resnet/coderpad/README.md) | 模型参数与内存估算 | 一维卷积窗口 |
| 04 | [Image Classification](04-image-classification/coderpad/README.md) | 分类混淆矩阵指标 | 集成投票与并列 |
| 05 | [Transfer Learning & Fine-Tuning](05-transfer-learning/coderpad/README.md) | 模型参数与内存估算 | LoRA 增量与参数量 |
| 06 | [Object Detection — YOLO from Scratch](06-object-detection-yolo/coderpad/README.md) | 边框 IoU | 非极大值抑制 |
| 07 | [Semantic Segmentation — U-Net](07-semantic-segmentation-unet/coderpad/README.md) | 分割 Dice | 分类混淆矩阵指标 |
| 08 | [Instance Segmentation — Mask R-CNN](08-instance-segmentation-mask-rcnn/coderpad/README.md) | 图像 Patch 切分 | 边框 IoU |
| 09 | [Image Generation — GANs](09-image-generation-gans/coderpad/README.md) | 分类交叉熵 | 数值梯度 |
| 10 | [Image Generation — Diffusion Models](10-image-generation-diffusion/coderpad/README.md) | 前向加噪 | Warmup 与余弦学习率 |
| 11 | [Stable Diffusion — Architecture & Fine-Tuning](11-stable-diffusion/coderpad/README.md) | 前向加噪 | 模型参数与内存估算 |
| 12 | [Video Understanding — Temporal Modeling](12-video-understanding/coderpad/README.md) | 视频均匀采样 | 音频分帧 |
| 13 | [3D Vision — Point Clouds & NeRFs](13-3d-vision-nerf/coderpad/README.md) | 二维仿射变换 | 单头注意力 |
| 14 | [Vision Transformers (ViT)](14-vision-transformers/coderpad/README.md) | 图像 Patch 切分 | 单头注意力 |
| 15 | [Real-Time Vision — Edge Deployment](15-real-time-edge/coderpad/README.md) | 分位数与 Goodput | 模型参数与内存估算 |
| 16 | [Build a Complete Vision Pipeline — Capstone](16-vision-pipeline-capstone/coderpad/README.md) | 依赖计划拓扑排序 | 分位数与 Goodput |
| 17 | [Self-Supervised Vision — SimCLR, DINO, MAE](17-self-supervised-vision/coderpad/README.md) | Embedding 余弦相似度 | 分类交叉熵 |
| 18 | [Open-Vocabulary Vision — CLIP](18-open-vocab-clip/coderpad/README.md) | Embedding 余弦相似度 | 稀疏路由 Top-K |
| 19 | [OCR & Document Understanding](19-ocr-document-understanding/coderpad/README.md) | CTC 贪心解码 | 编辑距离 |
| 20 | [Image Retrieval & Metric Learning](20-image-retrieval-metric/coderpad/README.md) | 距离与形状校验 | 检索指标 |
| 21 | [Keypoint Detection & Pose Estimation](21-keypoint-pose/coderpad/README.md) | 热图坐标解码 | 二维仿射变换 |
| 22 | [3D Gaussian Splatting from Scratch](22-3d-gaussian-splatting/coderpad/README.md) | 二维仿射变换 | Rectified Flow 一步积分 |
| 23 | [Diffusion Transformers & Rectified Flow](23-diffusion-transformers-rectified-flow/coderpad/README.md) | Rectified Flow 一步积分 | 前向加噪 |
| 24 | [SAM 3 & Open-Vocabulary Segmentation](24-sam3-open-vocab-segmentation/coderpad/README.md) | 掩码游程编码 | 分割 Dice |
| 25 | [Vision-Language Models — The ViT-MLP-LLM Pattern](25-vision-language-models/coderpad/README.md) | 单头注意力 | 图像 Patch 切分 |
| 26 | [Monocular Depth & Geometry Estimation](26-monocular-depth/coderpad/README.md) | 深度估计相对误差 | 回归误差与形状 |
| 27 | [Multi-Object Tracking & Video Memory](27-multi-object-tracking/coderpad/README.md) | 边框 IoU | 合法状态转换 |
| 28 | [World Models & Video Diffusion](28-world-models-video-diffusion/coderpad/README.md) | 视频均匀采样 | KV Cache 内存预算 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
