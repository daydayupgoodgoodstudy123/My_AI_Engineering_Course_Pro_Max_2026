# 03-deep-learning-core：CoderPad 练习

本章 13 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [The Perceptron](01-the-perceptron/coderpad/README.md) | 线性层前向 | 激活函数前向 |
| 02 | [Multi-Layer Networks and Forward Pass](02-multi-layer-networks/coderpad/README.md) | 线性层前向 | 矩阵乘法 |
| 03 | [Backpropagation from Scratch](03-backpropagation/coderpad/README.md) | 数值梯度 | 多项式求导与链式法则 |
| 04 | [Activation Functions](04-activation-functions/coderpad/README.md) | 激活函数前向 | 稳定 Sigmoid |
| 05 | [Loss Functions](05-loss-functions/coderpad/README.md) | 分类交叉熵 | 回归误差与形状 |
| 06 | [Optimizers](06-optimizers/coderpad/README.md) | 梯度下降一步更新 | 梯度范数裁剪 |
| 07 | [Regularization](07-regularization/coderpad/README.md) | 梯度下降一步更新 | 回归误差与形状 |
| 08 | [Weight Initialization and Training Stability](08-weight-initialization/coderpad/README.md) | 均值与总体方差 | 模型参数与内存估算 |
| 09 | [Learning Rate Schedules and Warmup](09-learning-rate-schedules/coderpad/README.md) | Warmup 与余弦学习率 | 梯度下降一步更新 |
| 10 | [Build Your Own Mini Framework](10-mini-framework/coderpad/README.md) | 线性层前向 | 数值梯度 |
| 11 | [Introduction to PyTorch](11-intro-to-pytorch/coderpad/README.md) | 模型参数与内存估算 | 有界批处理装箱 |
| 12 | [Introduction to JAX](12-intro-to-jax/coderpad/README.md) | 数值梯度 | 矩阵乘法 |
| 13 | [Debugging Neural Networks](13-debugging-neural-networks/coderpad/README.md) | 梯度范数裁剪 | 阈值异常检测 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
