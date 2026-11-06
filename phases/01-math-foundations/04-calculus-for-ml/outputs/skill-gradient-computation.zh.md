---
name: skill-gradient-computation
description: Compute gradients of common ML loss functions and choose the right derivative approach
version: 1.0.0
phase: 1
lesson: 4
tags: [calculus, gradients, backpropagation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="gradient-computation-for-ml"></a>

# Gradient 机器学习计算

loss functions、activation functions的计算gradients以及神经网络中使用的层操作的实用参考。

<a id="decision-checklist"></a>

## 决策清单

1. 该函数是否由简单的原语（power、exp、log、trig）组成？使用分析导数和 chain rule。
2. 该函数是自定义操作还是黑盒操作？使用数值微分：`(f(x+h) - f(x-h)) / (2h)`，其中 h = 1e-7。
3. 该函数是由 PyTorch/JAX 中的 tensor 操作构建的吗？让 autograd 处理。通过数值检查进行验证。
4. 您是否需要标量损失的 gradient？ weights 的矩阵？通过计算图应用 chain rule，一次一个节点。
5. 是否存在不可微运算（argmax、舍入、sampling）？使用直通估计器或重新参数化技巧。

<a id="when-to-use-each-approach"></a>

## 何时使用每种方法

| 方法 | 何时使用 | 成本 |
|---|---|---|
| 分析（手工得出） | 功能简单，验证autograd输出 | 运行时免费 |
| 数值（finite differences） | 调试、gradient检查、黑盒功能 | 2n forward passes 为 n parameters |
| 自动微分 | 任何可微的计算图（默认） | 1个 backward pass |
| 符号（SymPy、Mathematica） | 导出论文的封闭形式 gradients | 仅编译时 |

<a id="quick-reference-common-derivatives"></a>

## 快速参考：常见衍生品

| 功能 | f(x) | f'(x) | 机器学习环境 |
|---|---|---|---|
| 均方误差损失 | (1/n) sum(y_hat - y)^2 | (2/n)(y_hat - y) | 回归 |
| Cross-entropy（二进制） | -(y log(p) + (1-y) log(1-p)) | p - y（sigmoid 之后） | 二元分类 |
| Cross-entropy（多） | -log(p_true_class) | p - one_hot(y)（在softmax之后） | 多类分类 |
| Sigmoid | 1 / (1 + e^(-x)) | 西格玛(x) * (1 - 西格玛(x)) | 输出门，二进制输出 |
| 谭 | (e^x - e^(-x)) / (e^x + e^(-x)) | 1 - tanh(x)^2 | 隐藏激活（旧版） |
| ReLU | max(0, x) | 如果 x > 0，则为 1；如果 x < 0，则为 0 | 默认隐藏激活 |
| 泄漏 ReLU | max(0.01x, x) | 如果 x > 0，则为 1；如果 x < 0，则为 0.01 | 避免死亡的神经元 |
| GELU | x * Phi(x) | Phi(x) + x * phi(x) | Transformers |
| Softmax_i | e^(x_i) / sum(e^(x_j)) | s_i(1 - s_i) 对于 i=j，-s_i*s_j 对于 i!=j | 输出层（Jacobian） |
| 日志-softmax | x_i - log(sum(e^(x_j))) | 1 - 第 i 个条目的 softmax(x_i) | 数值稳定CE |
| 线性层 | y = Wx + b | dL/dW = dL/dy * x^T, dL/db = dL/dy | 每一层 |
| L2正则化 | lambda * sum(w^2) | 2 * 拉姆达 * | Weight decay |
| L1 正则化 | lambda * sum(\|w\|) | lambda * 符号(w) | 稀疏性 |

<a id="common-mistakes"></a>

## 常见错误

- 忘记批量平均损失中的 1/n 因子（MSE，cross-entropy）。 gradient 由 batch size 缩放。
- 将 softmax gradient 作为向量计算，而实际上它是 Jacobian 矩阵。对于 cross-entropy + softmax 组合，gradient 简化为 (p - y)，这避免了完整的 Jacobian。
- 以错误的顺序应用 chain rule。从损失逆推：dL/dW = dL/dy * dy/dW。
- 使用太大 (h = 0.1) 或太小 (h = 1e-15) 的 h 进行数值导数。对于 float64，坚持 h = 1e-7。
- 忘记 ReLU 在 x = 0 处未定义 gradient。实际上，将其设置为 0 或 0.5。

<a id="gradient-checking-recipe"></a>

## Gradient 检查配方

```
For each parameter w:
  numeric_grad = (loss(w + h) - loss(w - h)) / (2h)
  auto_grad = backward pass value
  relative_error = |numeric - auto| / max(|numeric|, |auto|, 1e-8)
  assert relative_error < 1e-5
```

相对误差高于 1e-3 表示出现问题。在 1e-5 和 1e-3 之间进行调查。
