# 参考解释：Tree of Thoughts and LATS: Deliberate Search

## 核心：最短路径搜索

第一次发现节点就标记 seen；队列保证最短边数，排序邻居保证并列结果稳定。

准确合同：graph maps string nodes to neighbor lists; missing nodes have no neighbors. Use BFS with neighbors sorted lexicographically and return the first shortest path including endpoints; return None if unreachable. start==goal returns [start]. Cycles must terminate.

## 加分：探索与利用调度

未探索候选优先，否则平衡均值与探索项；并列采用固定索引顺序。

准确合同：means/visits must be same-length nonempty lists; visits are exact nonnegative ints; total exact int >=1, exploration>=0. Return first unvisited index if any; else maximize mean+c*sqrt(log(total)/visits), ties lower index. Invalid input raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
