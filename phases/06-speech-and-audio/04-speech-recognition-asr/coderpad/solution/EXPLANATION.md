# 参考解释：Speech Recognition (ASR) — CTC, RNN-T, Attention

## 核心：CTC 贪心解码

先压缩连续重复，再去 blank；blank 可以分隔两个应保留的相同字符。

准确合同：Collapse adjacent repeated tokens first, then remove blank tokens. A blank separates repetitions, so [1,0,1] decodes to [1,1]. Tokens and blank are provided scalar ids; empty input returns [].

## 加分：编辑距离

动态规划每格比较插入、删除和替换；上一行足够，不必存整张表。

准确合同：Return Levenshtein distance between two token lists, using unit insertion/deletion/substitution costs. Inputs are lists of scalar tokens. Empty sequences are valid; no transposition operation.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
