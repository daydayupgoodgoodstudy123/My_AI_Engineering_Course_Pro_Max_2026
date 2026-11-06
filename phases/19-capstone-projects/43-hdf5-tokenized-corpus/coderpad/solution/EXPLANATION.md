# 参考解释：HDF5 Tokenized Corpus

## 核心：重叠窗口切块

步长等于 size-overlap；一旦覆盖末尾立即停止，避免冗余的尾部块。

准确合同：Require exact integers size>0 and 0<=overlap<size. Return windows starting at 0 then advancing size-overlap; include a short final window, stop once a window reaches the end. Empty tokens yields []. Invalid configuration raises ValueError.

## 加分：内容指纹与漂移

内容以 UTF-8 编码后做 SHA256；路径排序保证重现，digest 本身不证明可信发布者。

准确合同：files maps relative path strings to text. Return path->SHA256 hex of UTF-8 content, with keys inserted in sorted path order. Reject absolute paths or any '..' path component with ValueError. Do not read disk.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
