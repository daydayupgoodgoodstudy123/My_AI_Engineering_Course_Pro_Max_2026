# EvalPair 参考讲解

## Part 1

judge fixture 返回完整 EvalScore，build_result 保留 typed object；正确 average_score 读 score 属性，不在内存组装时 asdict。average 用真除法，空分数为 0.0。source ROUGE-L 对 lowercase split tokens 算 LCS，保留重复与先后；F1 最后 round4，None/empty 返回零。LCS 动态规划保存上一行与当前行，避免重复后缀子问题；完整 metric request 必要工作与输出仍保留。完整计时包含原 disjoint 序列和共享 interior token 的正 LCS 序列，消费两条完整输出与正分 0.0769。最终连续三慢 2.057934/2.013349/2.061825 秒、三快 0.000027834/0.000027459/0.000027709 秒，限值 0.08，双侧余量 25.17/2874.19 倍；完整证据在 SCOPE 指向的包外 timing-final。disjoint-only shortcut 保留递归的错修也被实际抓住。

## Part 2

run metadata 用 JSON，observations 用 newline="" 的 CSV writer/reader。两个 presence 字段区分 missing reference/empty reference、unjudged score/数字零。原 score_text 和 output/reference/reasoning 不经 float 或手工拼行。run id 不覆盖，重开保留原顺序、model/prompt/seed；大整数 seed 不经 float，首尾空白也属于原文本。没有事务或崩溃原子性承诺。

## Part 3

两侧严格匹配 case_id/criterion 键和 category，拒绝 unjudged。criterion group 的样本是 case 的差值；category/overall 先在每 case 内平均 criterion 差值，再采样 case。每 group 用自己的 Random(seed)，差值与均值不提前 round；每次采样允许重复抽中同一个 case，不能以无放回打乱替代。B 个排序后采样均值的端点采用 docstring 的 floor/减一/夹取约定，upper index 至少为 lower index，单 case 退化为自身。upper<-tolerance 的 criterion 或 category block，overall 正收益不覆盖局部不利证据。source demo 是数据派生 LCG/独立 run CI/固定均值阈值；本题配对与 seeded Random 是 docs/讲解练习支持的明确替代，不冒称 source 原来已经实现。

## Part 4

同步 encode_testcase 只编码一条完成记录：用本 case_id/category 和给定 seconds helper 构造属性，消费正确 GIVEN normalizer 的 kind/message，生成恰当且唯一的 outcome 子节点；success 没有 error/failure/skipped。system-out.text 保存字段身份正确的原始 output/reference JSON，ET 负责 XML attribute/text 的结构转义。返回完整 testcase XML，不维护跨 case 状态。

正确 GIVEN suite driver 先发布固定 opening，每拉到一条完成记录就调用同步 encoder 并发布完整返回值，再拉下一条，最后发布 closing；empty suite 也完整。source、encoder 和 pending jobs 的关闭由给定 driver/外壳管理。可观察性、binding 和 close 断言验证这个整合边界，候选不重新写 async 发布算法。有限本地 subset 不等于完整 runner/provider 协议。

## Part 5

catalog 校验给定；逐 category/case/criterion 按原顺序看同一个 (case_id,criterion) 两侧的 score presence，报告四种 coverage。category 内 per-criterion paired count 单独累计，typed input path 为每个 criterion 保留自己的索引，没有 case 的 category 也保留零 coverage 与原 evidence。category evidence 直接取 comparison.categories 原对象并附原 key path，即使 overall 有利也不抹掉负向或缺测 category。这里没有重采样、统计判定、分数平均或 hierarchy weights。

## 这套题证明了什么，没证明什么

它验证来源中的本地 judge/ROUGE、exact evaluation artifacts、明确配对统计、完成报告和 evidence coverage。没有真实 LLM judge、事实准确率、行业 benchmark、生产并发/崩溃恢复、完整 JUnit 协议、部署有效性或真人面试校准证据。
