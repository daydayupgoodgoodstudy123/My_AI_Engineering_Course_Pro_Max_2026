# 参考解释：The Perceptron

## 核心：线性层前向

权重每一行对应一个输出，bias 长度必须等于输出数。

准确合同：weights is a list of output rows, each matching len(features); bias length equals row count. Return dot(row,features)+bias per row. Invalid shapes raise ValueError. Empty output weights and bias yield [].

## 加分：激活函数前向

分别实现三种映射；负区间的 leaky_relu 梯度不是零。

准确合同：Map numeric values through relu, leaky_relu, or tanh. relu=max(0,x); leaky_relu uses slope*x only for x<0. Unknown kind or negative slope raises ValueError; empty input returns [].

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
