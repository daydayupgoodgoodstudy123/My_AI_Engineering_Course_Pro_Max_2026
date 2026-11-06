# 参考答案讲解：ContextLoom（11/05）

计时结束后再看。参考实现在同目录的 `contextloom/`，只使用本地内容和 deterministic summarizer。

## Part 1 配对、分配与历史压缩

filter 的 documents 和 scores 必须使用同一选择结果。完整 scores 配缩短 docs 会在正确 pair consumer 处违反长度合同；这里没有把 source zip 假装成会报 IndexError。

替换 allocation 时先在 used 中排除本 slot 的旧贡献，再计算新内容的可用空间。mandatory system/query 先获分配，optional slots 竞争剩余空间；最终仍按 system、optional、query 布局。

完整 history word total 包括每个 user/assistant 标签、两个 section headers 与 rolling summary。最后只应用一次本课 `int(words*1.3)` 估计，不能把每条 content 的 floor 值简单相加。正确 deque、12-word rolling summary、source-id 累积和无法容纳最近两对时的拒绝策略都已给定。

性能修复只改变 retained words 的维护：每对 exchange 预计算一次，evict 时扣除，再执行相同 summary update。1,200 对 exchanges 的三次功能已修慢版约 0.586–0.604 秒，参考版约 0.0028–0.0028 秒；0.06 秒限值双侧余量均超过 8 倍。计时包含真实摘要/provenance 更新、输入检查与最终输出，不能靠删必要工作过关。

## Part 2 revision log 与 checkpoint

每次 append 写一个完整编码 revision，replay 用 key 折叠最新 live component，dict 的第一次插入位置决定稳定 slot 顺序。旧版本不再贡献 live tokens。与当前 live value 相同版本的冲突拒绝；append 必须严格增加该组件 revision，相同 payload 的同版本重写也拒绝，并保持文件不变；covered older versions 被忽略，这不是全历史完整性审计。

checkpoint 保存完整有序 state，之后清 covered log。重开先读 checkpoint，再看 log，旧 covered revision 跳过。text/role/revision/integer token estimate 与 provenance 由给定 codec 保留。日志按真实 LF 分 record；splitlines 还会分开 JSON 字符串内合法的 U+2028/NEL，破坏 Unicode round-trip。它是本地 append/checkpoint 格式，不提供事务、fsync 或坏半行恢复保证。

## Part 3 retrieved block 的 zigzag

稳定按 score 降序取得 rank；偶数下标 ranks 1/3/5... 正序，奇数下标 ranks 2/4/6... 反转接到后面。这样最强两项在 block 首尾，低 rank 在中间，奇偶长度都不重复、不丢失。

同分不比较文字，重复 text 也不是重复 component。零分是合法 relevance，已经选入的 component 不能在 placement 时被真值判断丢弃。P1 budget/layout dependency 保留 mandatory system/query 与 reserve；P3 不重新实现 admission 或 history compression，也不把 block 的两端说成整个 prompt 的两端。

## Part 4 coherent SSE revision

同步 `encode_revision` 用当前 component 调用给定 `session.apply`，再逐项投影完整 contents、allocations、used、reserve、remaining、selected 与 session revision。contents 保留全部已准入的 slot，包括空文本，selected 只列非空 slot，并保留同一 live layout 次序；只发送刚更新的 slot 不能代表当前完整上下文。

id 取 session revision，event 固定为 context，data 是单行 JSON snapshot，block 以一个空行结束。text 内的换行交给 JSON 序列化保留。reserve 仍是 session 指定的生成预留，不能归入 remaining；每个数值和 slot 都属于这次 apply 的同一状态。

正确给定的 `encode_revisions` 直接拉取一条、调用同步 callback、发布一个 event，然后才拉下一条；`stream_revisions` 关闭 encoder/source。候选人不实现这些异步循环。原节奏、early-close 和跨 revision allocations 检查仍验证真实给定 driver 的集成，测试不连接网络或真实模型。

## Part 5 bottom-up document digest

递归到 children 得到各自 digest，按顺序 newline-join，再对当前 node 的 local budget 处理。fitting text 保持原样，超限时给定 helper 才调 callback 并检查结果。

source paths 由 root 到 paragraph 的 keys 组成，不能用 title 当 identity。重复 title 和 paragraph local key 在不同分支都保留；每个 parent 汇总 child 的 ordered leaf paths。这里的顺序是文档 children 的顺序，不能对 path 排序。Source 讲 recursive summarization 概念，本题的 DocumentNode/tree 算法是显式教学扩展。

## 这套题证明了什么，没证明什么

通过说明你能修复 context pairing 和预算流水线，保存 revision state，完成 retrieved block placement、coherent SSE 回放与 bottom-up digest。它没有测量真实 tokenizer、中文 token 准确率、LLM 摘要质量、lost-in-the-middle 的实证收益、真实应用 latency 或 crash durability。所有 summary 是确定性本地 bookkeeping，60 分钟难度与时间分配尚未经过真人校准。
