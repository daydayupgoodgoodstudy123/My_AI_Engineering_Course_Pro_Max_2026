# 11/04 BitVecBank 复盘

- 日期 / 第几次做：
- 模式：独立计时 / 有人主持 / 重复练习
- 开始和结束时间：
- 看过的材料、用过的帮助、H1/H2/H3 各几次：

| 关 | 解锁时间 | 第一次变绿 | pytest 跑了几次 | 卡在哪 | 修的是根因还是在凑测试 |
|---|---|---|---|---|---|
| 1 向量检查流水线 | | | | | |
| 2 binary64 bank | | | | | |
| 3 packed shortlist + rerank | | | | | |
| 4 BVS1 header 与 record 编码 | | | | | |
| 5 多层图检查 | | | | | |

- 60 分钟时通过了几关：
- 问过的澄清问题，以及该问没问的问题：
- 讲到了哪些取舍：prefix-before-scaling 与给定稳定 primitive、distance/similarity、float64 bits 与 little-endian payload、UTF-8 byte extent、raw record 段布局与声明 dimension、tail mask、m/k、两阶段 rank、有向局部邻居、local optimum 与 HNSW 模拟边界：
- 留下的死代码或临时改动：
- 复盘后补完的关，不算进计时成绩：
- 关掉答案后仍然写不出的关：
- 下次只改一个习惯：
