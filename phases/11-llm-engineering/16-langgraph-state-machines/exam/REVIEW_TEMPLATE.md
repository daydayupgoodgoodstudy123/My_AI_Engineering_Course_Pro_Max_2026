# 复盘记录

日期：____　实际总用时：____　开场2分钟计入：____

| Part | 预算 | 实际 | 通过/提示 | expected/actual/责任文件 |
|---|---:|---:|---|---|
| 1 | 12 | | | |
| 2 | 10 | | | |
| 3 | 16 | | | |
| 4 | 10 | | | |
| 5 | 10 | | | |

首错production返回什么，正确consumer在哪里失败：____
parent、branch、thread、checkpoint四种身份如何区别：____
fork与普通恢复/重跑旧节点区别：____
旧snapshot嵌套对象是否变化：____
P1single-delta、路径重复祖先检测与P3barrier各负责什么：____
正确scoped parent lookup、path-local cycle membership与跨查询状态各是什么职责：____
完整祖先记录是否保留各自state而非当前head的state：____
完整Given ownership runtime和候选assembler的边界：____
为什么completion order不能决定append顺序：____
overwrite冲突、重复到达和空batch的处理：____
空delta证据与收集后不重新调用worker的保证：____
artifact/index失败窗口、孤立artifact与身份核验、不承诺的durability：____
JSON Pointer、new field/nonprefix list与exact parent/完整commit证据：____
最近祖先、相同head/branch标签、完整path与分歧suffix如何定义：____
Given依赖、教学扩展、没有SDK验证的部分：____
下一次只练一个薄弱点：____
