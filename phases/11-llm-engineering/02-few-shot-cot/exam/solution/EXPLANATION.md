# 参考答案讲解：CoTBallot（11/02）

计时结束后再看。参考实现在同目录的 `cotballot/`，测试只使用本地数据。

## Part 1 修示例流水线

formatter 报 TypeError，是因为上游 selector 把完整记录投影成 answer 字符串。要恢复 question、reasoning、answer 都在的独立记录，不能在 formatter 里凭一个答案补出示例。

extractor 只看最后非空行上的终值标记，不用推理里的第一个数字补答案。formatter 则保留 worked reasoning；否则只是普通 few-shot。

性能问题在同一 query 的选槽循环里：每个槽位都重新 rank 全 corpus。参考版只 rank 一次，先取各 label 的最佳示例，再填剩下的排名。固定 corpus token 预处理在两边都相同，所以修法不是重新做 archive token 缓存。

6,000 条示例、160 槽位的本机三次慢版为 0.709–1.197 秒，参考版为 0.0065–0.0077 秒，限值 0.075 秒。这只是本地选择算法 CPU 时间，不是 LLM latency 或示例质量测量。

## Part 2 示例库

SQLite 的 seq 负责 corpus 顺序，id 负责更新定位。UPSERT 更新字段时保留原 seq；不能删除重插。question、reasoning、answer、label 原样用 TEXT 存，difficulty 用 INTEGER。成功写入提交后，重开看到同样的顺序和词面。记录必须恰好包含六个字段，difficulty 是非负整数（不接受 bool）；拒绝缺字段、多字段和负难度，保留已有记录。

示例的 answer 不在存储时归一化。`+00024.00` 是应保留的教学/回放词面；“与 24 数值相同”是投票阶段的判断。

## Part 3 精确数值投票

提取器先保留 raw lexeme，再由完整匹配的有限 grammar 判断合法性。Decimal 转 Fraction 可以精确表示有限小数，整数分数也直接转 Fraction，不经过 float。分数两侧的逗号分组也在去逗号前完整验证；末尾标记只能占据整行，不能从一句话内部 search 出答案。输出用整数或约分后的 numerator/denominator 作 canonical key。

Counter 只接收合法值，包括零。confidence 是赢家票数除以 valid，attempted 另报；没有有效票时 winner=None、confidence=0。平票用精确数值最小值，不能靠字符串排序或 Counter 的遇见顺序。

这份 grammar 比源码的简化 unsigned extractor 更明确，支持符号、合法千位分组和整数分数，但不支持指数、单位、NaN 等。它是练习的有限合同，不代表真实模型一定按该格式输出。

## Part 4 累计 ballot 事件投影

ballot_event 将当前 sample 的原始 text 追加到本批 reasonings，调用已完成的 tally_samples，再构造一条完整 NDJSON。index 使用 attempted，当前 answer 取 answers 的最后一项，winner、confidence、votes 是累计结果。无效答案仍有一次尝试与一个事件。confidence 保持有效票份额，votes 保留全部答案的分布，不把赢家摘要当作完整投票表。

sample_id 和 text 不做归一化。JSON 转义内嵌换行，完整对象后只加一个 LF。stream_ballots 的新建批内 history、完整消费/发布循环和关闭 source 都正确 GIVEN；候选不写 async loop。它只为当前样本调用一次 callback，发布后再取下一样本，空源不调用 callback。所有 reasoning 为短批次保存在内存，没有固定内存或无限吞吐承诺。

## Part 5 给定轨迹的路径与总账

DFS 只遍历输入中已经存在的节点。每次访问累加当前祖先路径及其 tokens；遇到合法终值就记录路径，并继续看已提供的 children。这样不会漏掉兄弟、低分分支或更深的已记录答案。

全局 seen 按 node id 记一次实际执行节点。共享节点在两条路径上都出现，但全局只记一次 generation 和一次 evaluation；没有终值的叶子也有已消耗成本。当前路径检测环，全局 signature 检测同 id 矛盾记录，两者职责不同。score 校验为有限的 [0,1] 数值，generation/evaluation token 字段校验为非负整数，排除 bool 和小数；这些是给定轨迹的字段约束。

## 这套题证明了什么，没证明什么

通过说明你能修复 worked-example 流水线，持久化精确示例，实现有限 grammar 的 self-consistency、逐样本结果流和给定 ToT 轨迹核对。它没有请求真实 LLM、评估真实数学准确率、验证 CoT 的质量收益，也没有实现 ToT/MCTS 搜索或证明票份额是校准置信度。60 分钟的难度与时间分配尚未经过真人校准。
