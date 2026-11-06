# 参考解释：Memory Blocks and Sleep-Time Compute

## 核心：有界记忆保留

先按 id 合并最新记录，再按时间预算保留；同时间取后出现的更新。

准确合同：Records have id, timestamp, text. Keep the most recent record per id (later input wins timestamp ties), then retain limit records by descending timestamp and lexicographic id ties. Return copied records. limit exact nonnegative int; invalid limit raises ValueError.

## 加分：内容指纹与漂移

内容以 UTF-8 编码后做 SHA256；路径排序保证重现，digest 本身不证明可信发布者。

准确合同：files maps relative path strings to text. Return path->SHA256 hex of UTF-8 content, with keys inserted in sorted path order. Reject absolute paths or any '..' path component with ValueError. Do not read disk.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
