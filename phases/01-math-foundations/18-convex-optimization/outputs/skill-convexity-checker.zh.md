---
name: skill-convexity-checker
description: Determine if an optimization problem is convex and choose the right solver
version: 1.0.0
phase: 1
lesson: 18
tags: [optimization, convexity, solvers]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="convexity-checker"></a>

# 凸性检查器

如何验证优化问题是否凸，以及如何处理答案。

<a id="decision-checklist"></a>

## 决策清单

1. 目标函数是凸函数吗？ （检查Hessian正半定性或使用组合规则。）
2. 是否所有形式为 g_i(x) <= 0 的不等式约束，其中每个 g_i 都是凸的？
3. 所有等式约束都是仿射（线性）吗？
4. 如果这三个都为是，则问题是凸的。使用具有收敛保证的凸求解器。
5. 如果有任何一个不是，则该问题是非凸的。使用 SGD/Adam 并接受局部最优值。

<a id="how-to-test-convexity-of-a-function"></a>

## 如何测试函数的凸性

| 测试 | 适用于 | 方法 |
|---|---|---|
| 二阶导数 >= 0 | 标量函数 f(x) | 计算 f''(x)。如果对于所有 x，f''(x) >= 0，则凸。 |
| Hessian 是 PSD | 多元函数 f(x) | 计算 H(x)。如果所有地方都 eigenvalues >= 0，则凸。 |
| 定义测试 | 任何功能 | 检查采样的 x、y、t 的 f(tx + (1-t)y) <= t*f(x) + (1-t)*f(y)。 |
| 构图规则 | 组合函数 | 参见下面的成分表。 |
| 限制为一条线 | 多元 f | f 是凸的，当且仅当 g(t) = f(x + tv) 对于所有 x、v 在 t 中都是凸的。 |

<a id="composition-rules-preserving-convexity"></a>

## 组合规则（保持凸性）

| 操作 | 结果 |
|---|---|
| f + g（均为凸） | 凸面 |
| c * f（c > 0，f 凸） | 凸面 |
| max(f, g)（均为凸） | 凸面 |
| f(Ax + b) 其中 f 是凸的 | 凸面 |
| g(f(x)) 其中 g 是凸非递减的，f 是凸的 | 凸面 |
| g(f(x)) 其中 g 是凸非增函数，f 是凹函数 | 凸面 |
| 凸函数之和 | 凸面 |
| 凸函数的逐点至上 | 凸面 |

<a id="common-ml-objectives-convex-or-not"></a>

## 常见的 ML 目标：凸与否？

| 目的 | 凸？ | 原因 |
|---|---|---|
| MSE: (1/n) sum(y - Xw)^2 | 是的 | w 的二次方，Hessian = (2/n) X^T X 是 PSD |
| 逻辑损失： sum(log(1 + exp(-y_i * w^T x_i))) | 是的 | 凸函数之和（log-sum-exp 系列） |
| 铰链损失： sum(max(0, 1 - y_i * w^T x_i)) | 是的 | 凸（线性）函数的最大值 |
| L2正则化：lambda * \|\|w\|\|^2 | 是的 | 二次，Hessian = 2*lambda*I |
| L1正则化：lambda * \|\|w\|\|_1 | 是的 | 绝对值之和（凸但不可微） |
| 岭回归：MSE + L2 | 是的 | 两个凸函数之和 |
| 套索：MSE + L1 | 是的 | 两个凸函数之和 |
| 弹性网：MSE + L1 + L2 | 是的 | 凸函数之和 |
| SVM（原始）：铰链 + L2 | 是的 | 凸函数之和 |
| Cross-entropy 与 softmax | 是（在 logits 中） | 对数和表达式是凸的 |
| 神经网络（任何损失） | 否 | 非线性激活创建非凸组合 |
| k-均值目标 | 否 | 离散分配步骤 |
| 矩阵分解：\|\|X - UV^T\|\|^2 | 否 | U 和 V 中的双线性 |
| GAN 损失 | 否 | Minimax，生成器中的非凸 |
| 对比损失 (InfoNCE) | 否 | 负样本指数比的对数 |

<a id="solver-selection-based-on-convexity"></a>

## 基于凸性的求解器选择

| 问题类型 | 求解器 | 收敛保证 |
|---|---|---|
| 凸面、光滑、无约束 | Gradient descent | O(1/k) 到全局最小值 |
| 凸面、光滑、无约束 | L-BFGS | 超线性到全局最小值 |
| 凸面、光滑、无约束 | 牛顿法 | 二次接近最小值（如果 Hessian 易于处理） |
| 凸面、光滑、约束 | 内点法 | 多项式时间 |
| 凸面，非光滑 (L1) | 近端 gradient / ISTA | O(1/k) 到全局最小值 |
| 凸面，非光滑 (L1) | ADMM | 灵活，处理约束 |
| 凸、二次 | 共轭 gradient | 精确n步 |
| 非凸、光滑 | SGD / Adam | 收敛到局部最小值 |
| 非凸、光滑 | SGD + 重新启动 | 平均而言更好的局部最小值 |
| 非凸、光滑 | 过度参数化 + SGD | 平坦的最小值，良好的泛化能力 |

<a id="common-mistakes"></a>

## 常见错误

- 假设问题是凸的，因为 loss function 是凸的。您正在优化的 parameters 中的损失必须是凸的。 Cross-entropy 在 logits 中是凸的，但从输入到 logits 的完整神经网络映射是非凸的。
- 使用牛顿法解决非凸问题。 Hessian 可能具有负 eigenvalues，导致牛顿向鞍点或最大值而不是最小值移动。
- 忘记 L1 正则化会使目标在零处不可微。标准 gradient descent 效果不佳。使用近端 gradient descent 或次梯度方法。
- 通过形成 A^T A 对条件数进行平方。如果需要求解最小二乘问题并且 A 是病态的，请使用 QR 或 SVD 而不是正规方程。
- 未经检查就声明问题为非凸问题。许多机器学习问题（线性模型、支持向量机、逻辑回归）都是凸问题，并且受益于更强大的求解器。

<a id="quick-test-is-my-problem-convex"></a>

## 快速测试：我的问题是凸的吗？

```
1. Write out the objective: minimize f(w) subject to constraints
2. For each term in f(w):
   - Is it quadratic with PSD matrix? -> Convex
   - Is it a norm? -> Convex
   - Is it log-sum-exp? -> Convex
   - Does it involve w nonlinearly (sigmoid(w), w1*w2)? -> Likely non-convex
3. Are all constraints linear or convex inequalities?
4. If ALL terms are convex and constraints are convex/linear -> problem is convex
5. If ANY term is non-convex -> problem is non-convex
```
