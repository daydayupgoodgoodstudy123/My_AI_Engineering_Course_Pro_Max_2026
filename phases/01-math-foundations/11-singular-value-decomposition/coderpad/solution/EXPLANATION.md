# 参考解释：Singular Value Decomposition

## 核心：2×2 实特征值

使用迹与行列式构造二次方程，检查判别式，再对两个实根排序。

准确合同：Require a 2x2 numeric matrix. Return its two real eigenvalues sorted ascending. A negative discriminant or invalid shape raises ValueError. Repeated eigenvalues appear twice.

## 加分：2×2 线性方程

先验证形状并拒绝接近奇异的行列式，再计算两个未知数。

准确合同：Solve A*x=rhs using a 2x2 matrix and two-element rhs. Invalid shapes or abs(det)<1e-12 raises ValueError. Return [x0,x1].

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
