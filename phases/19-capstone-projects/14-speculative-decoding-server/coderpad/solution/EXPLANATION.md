# 参考解释：Capstone 14 — Speculative-Decoding Inference Server

## 核心：推测解码前缀验收

只验收连续相同前缀，遇到首个不匹配就停止，不保留后面偶然匹配的 token。

准确合同：Return {'accepted':longest matching prefix of draft and verified, 'next':first verified token after that prefix or None}. draft may be shorter; verified may be empty. Exact token equality; no probabilities or sampling are modeled.

## 加分：KV Cache 内存预算

key 与 value 带来系数 2；使用 KV head 数，避免误用 query head 数。

准确合同：All arguments are exact ints. layers,kv_heads,head_dimension,batch,bytes_per_element must be >0; tokens>=0. Return 2*layers*tokens*kv_heads*head_dimension*batch*bytes_per_element. Invalid input raises ValueError. No allocator overhead is included.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
