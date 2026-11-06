# 参考解释：Data Pipelines for Pre-Training

## 核心：重叠窗口切块

步长等于 size-overlap；一旦覆盖末尾立即停止，避免冗余的尾部块。

准确合同：Require exact integers size>0 and 0<=overlap<size. Return windows starting at 0 then advancing size-overlap; include a short final window, stop once a window reaches the end. Empty tokens yields []. Invalid configuration raises ValueError.

## 加分：可复现数据划分

按既有顺序切三段，先验证数量，避免切片静默接受超范围配置。

准确合同：Preserve record order. Counts are exact nonnegative ints and their sum cannot exceed input length. Return {'train':prefix,'validation':next records,'test':remainder}. Return copies of list slices; invalid counts raise ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
