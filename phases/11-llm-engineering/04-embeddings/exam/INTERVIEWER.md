# 面试官手册：BitVecBank（11/04）

候选人计时期间不要看。候选人手里只有 README、`bitvecbank/` 和 `tests/`。

## 开场（2 分钟）

- 总时长 60 分钟，含开场 2 分钟。请候选人边做边说明想法，可以提问、查官方文档。
- 五关参考时长为 10、11、15、12、10 分钟，合计 58 分钟。记录变绿时间、pytest 次数和提示次数。时间分配未经真人校准。
- 不代写；卡住约 5 分钟后，一次只给一级提示。

## 澄清问题的标准答案

只在候选人问到时回答，用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 截断前已经 normalized 也要再处理吗？ | "Yes. Normalize the retained prefix with the supplied stable helper. A zero prefix stays zero." |
| 1 | 0 和 -0.0 的 bit 呢？ | "Both map to zero. Only strictly positive coordinates map to one." |
| 1 | score 是负距离吗？ | "No. This exercise reports raw distances. Use the supplied metric-specific rank key." |
| 2 | float32 可以吗？ | "No. Preserve the binary64 coordinate representation, including signed zero and tiny values." |
| 2 | sidecar 的长度怎么数？ | "Count its encoded UTF-8 bytes, not Python characters." |
| 2 | 两个文件是原子事务吗？ | "No. Validate before writing, but this local two-file format makes no crash-atomicity guarantee." |
| 3 | packed code 的最后几个 bit 呢？ | "MSB-first. Ignore unused low tail bits, even when they contain nonzero padding." |
| 3 | m 和 k 是同一个数吗？ | "No. Select m by Hamming, rescore only those candidates, then return at most k." |
| 3 | m=0 或 k=0 呢？ | "Return no hits and perform no dense rescore." |
| 3 | 平局和 rank 怎么定？ | "Use original bank position for ties in both stages. index is zero-based; binary_rank and rank are one-based." |
| 3 | 全库 dense 最佳能补进来吗？ | "No. A candidate excluded by the binary shortlist cannot re-enter." |
| 4 | 是现有向量数据库协议吗？ | "No. Use the documented local BVS1 format and supplied metadata/bit codecs." |
| 4 | 空输入还要 header 吗？ | "Yes. Emit exactly one dimension header before pulling any embedding." |
| 5 | 同一个 node 跨层出现是环吗？ | "No. Reinspect its different neighborhood on each layer and carry the best node downward." |
| 5 | 等距离还能移动吗？ | "Yes, only toward an earlier original bank position. The complete rank key must strictly improve." |
| 5 | 要构建 HNSW 吗？ | "No. Only inspect the supplied finite graph and report the greedy path." |

## 每关：要看什么、提示、追问

### Part 1 修向量检查（目标 10 分钟）

四层缺陷：

1. truncate_embedding 先归一化完整向量再截 prefix，等价于用完整向量 norm 作除数。错误的 projected vector 经过 VectorService.inspect_projection，交给正确的 projection_card，才在单位范数断言暴露。不是 shape 异常，不能修改消费者吞掉错误。
2. binarize 用 >=0，让两种零都变 1。源码合同是 >0。
3. order_hits 不区分 raw distance 和 similarity，全部按大值优先。正确 score_key 已给定；Euclidean/Hamming 小值在前，cosine/dot 大值在前，平局保留 bank 顺序。
4. cosine 的 coordinate loop 里反复重算同一个 stored vector norm。移到循环外后仍要除以两边 norm，不能把 cosine 换成 dot。

性能测试计算 1 对 32,768 维向量的三次功能已修慢版约 1.331–1.385 秒，参考版约 0.0061–0.0072 秒，限值 0.10 秒，两侧余量均超过 8 倍。24 条向量、2 个 query、1,024 维的 48 对完整结果提供独立功能对照；wide pair 也对照正确 cosine。每个坐标都参与真实 cosine；只衡量本地 numeric cosine，不是 embedding/API latency。防过修断言保留全部 score、非单位向量、反向向量、零向量与 source 坐标。

正确的 direction_scale、unit_direction、math.hypot norm 和 math.dist 已给定。它们覆盖 finite 输入的 tiny、huge、subnormal 和混合尺度；候选人只需把保留 prefix 交给正确 helper，并保留 cosine 内相同 stored norm 外提的修法。有限坐标 validator 不能缩窄；消费者不能把 tiny 非零向量当成零。数值 helper 是护栏，不是第五层缺陷。

提示：H1 "Which norm was used before this card received the vector?"；H2 "Is the retained prefix a unit vector?"；H3 指向 projection producer，而非 card assertion。

追问："When is dot equivalent to cosine?"（两边向量都 normalized）；"How often does the same vector norm change inside one dot loop?"（不变）。

### Part 2 binary64 bank（目标 11 分钟）

坑：

- 文件 payload 必须是声明的 little-endian binary64；save/load 对称地写错端序也不合格，不能只看 roundtrip。
- 这是精确 vector bank，不是展示格式。float32 narrowing 会丢低位和 tiny values；普通 float equality 看不出 -0.0，要比较 struct 打包字节。
- Header 的 dimensions/count 必须与完整 payload 对应，少一字节、多一字节都拒绝。strict header helper 给定，不能拿 unpack_from 的宽松读取掩盖尾部垃圾。
- Metadata 用 UTF-8；header 记录字节数。sidecar entry 顺序与 row-major vectors 必须一致，不能单独按 key 排序。Unicode、CRLF、空字符串都保留。

提示：H1 "What precision does the bank promise?"；H2 "Do these two zeros compare equal but have different bits?"；H3 提醒固定 header、完整 binary64 payload 和 ordered sidecar。

追问："What happens if one of the two files is missing after a crash?"（格式没有事务保证，load 不能默默拼出半份 bank；本题不实现双文件恢复）。

### Part 3 packed shortlist 与 dense rerank（目标 15 分钟）

这关是独立 TODO。P1 sign mapping、projection、dense metric/direction 已修好，P3 不重写它们。

坑：

- 对 packed bytes 做 XOR/popcount，只有声明维度的有效 bit 参与。非 byte-aligned 最后字节只取高位；byte-aligned 不能误清整个末字节。
- shortlist_m 决定 binary 候选池，final_k 决定最终输出。只复评池内每一条；池外再好的 dense hit 也不能进来。m<k 最多 m 条，超出 bank 的预算截断。
- 两阶段平局都按原始 bank index，而不是 key 文本或 coarse 遇见顺序。dense 重排后保留原 binary_rank，最终 rank 从 1 开始。

提示：H1 "Which bits actually belong to this vector?"；H2 "Which candidates were permitted to reach dense scoring?"；H3 提醒先明确 coarse candidate indices，再调修好的 dense helpers。

追问："Does increasing m always preserve the exact dense top-k?"（只有 m 覆盖必要候选才可能；本题不承诺真实召回率）；"Why expose both ranks?"（核对候选池与最终重排来源）。

### Part 4 原始 binary records（目标 12 分钟）

候选人实现同步 `encode_vector_header` 与 `encode_vector_record`。正确 async driver、header-before-pull、逐 record 发布和 source/encoder 关闭均 GIVEN；测试继续核这些整合边界，不把 buffer-all 当作候选新主坑。

坑：

- BVS1 header 存向量坐标 dimension，不是 packed code 的字节数。每条 row 依 header 声明的 dimension 校验，不能拿自身长度自证正确。
- record prefix 存 metadata UTF-8 字节数。prefix、当前 row 的完整 metadata、完整 sign code 按声明布局连接，不能把字符数或其它段长度写进 metadata extent。
- 坐标顺序决定 packed code 的含义，metadata 也属于当前 row。正确 JSON codec 与 sign packer 已给定，候选不重写它们，不排序坐标或丢掉任一段。

header/empty source、当前 record 的可观察性、任意 transport byte chunks 和关闭均由正确 GIVEN driver 负责，并由 integration guards 验证。buffer-all/header-after-pull wrong 在正确 driver 内作整合验证，不属于 candidate 主责。

提示：H1 "Which dimension does the header declare?"；H2 "Which bytes belong to each field?"；H3 指向同步 header/record callbacks 的字段与段布局。

追问："Can a transport split a Unicode character or a packed code?"（可以；parser 按声明 byte lengths 重组，不能把 output chunk 当 record）。

### Part 5 给定多层图（目标 10 分钟）

坑：

- 邻接边按给定方向使用；不能擅自补反向边或扫描全层。没有改善的邻居时停在 local optimum，即使别处存在更优 node。
- 上一层找到的 best 是下一层起点，不能每层回原 entry。
- 一个 node 可以在多层出现，每层的邻居不同，global visited 不能屏蔽下层探索。
- 先看当前 node 和全部 neighbors 再挑最优，不是找到第一个好邻居就走。完整 metric/index key 必须严格改善，平分 plateau 也能有限终止。

严格 membership/shape helper 已给定。输入是 HNSW-style graph，不实现 insertion、efSearch、多候选 beam 或 ANN top-k 质量保证。

提示：H1 "Which node should enter this lower layer?"；H2 "Does this node have the same neighbors on both layers?"；H3 提醒每层独立路径与严格改善 key。

追问："Is this a full HNSW implementation?"（不是；只解释给定多层图的 greedy descent mechanics）。

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 从下游不变量追到 projection 生产者，逐层重跑 |
| 代码质量 | 15 | 精度、完整字节长度、严格 shape 与可读阶段边界 |
| 沟通 | 15 | 主动澄清 raw metric、m/k、tail bits 和排名 |
| 生产意识 | 10 | 召回范围、文件完整性、流式读取与模拟边界 |

每项写具体观察证据，没观察到就写“未观察”。
