# 参考答案讲解：BitVecBank（11/04）

计时结束后再看。参考实现在同目录的 `bitvecbank/`，只使用本地向量与给定 graph。

## Part 1 修向量检查

projection_card 的单位范数断言是正确的消费者合同。truncate_embedding 先切 prefix，再交给正确的 unit_direction。先归一化完整向量再截断，等价于拿原 norm 当除数，通常不是单位向量。zero prefix 保留零。

direction_scale 先按最大绝对值缩放，unit_direction 再按缩放后的 norm 归一化；这让 subnormal 坐标和原 norm 超出 float 范围的向量都保留方向。必须先切 prefix，避免被省略的 huge 尾部使 tiny prefix 在缩放时丢失。cosine 两侧分别缩放后再算 dot/norm，消费者用 math.hypot 区分 tiny 非零与真正零；Euclidean 给定分派用 math.dist 避免中间平方溢出。这些正确 primitive 已给定，候选人不需要另解数值算法，validator 继续接受全部 finite 坐标。

符号映射用 >0，零与负零都是 bit0。排序用已有 score_key 区分 raw distance 与 similarity；这里公开的 Euclidean/Hamming 是非负 raw distance，与源码统一输出负距离的展示方式不同，合同已明确。

cosine 的 coordinate loop 只累加 dot，norm_b 在循环外算一次。1 对 32,768 维向量的三次功能已修慢版约 1.331–1.385 秒，参考版约 0.0061–0.0072 秒，限值 0.10 秒，两侧余量均超过 8 倍。24 条向量、2 个 query、1,024 维的 48 对完整结果提供独立功能对照；wide pair 也对照正确 cosine。结果仍与完整非单位向量的正确 cosine 对照，不能用 raw dot 冒充提速。原始 dot 与距离结果仍按 binary64 表示范围处理；本题不要求任意精确算术。

## Part 2 binary64 bank

局部文件格式用固定 header 声明维度、条数和 sidecar 字节数，接 row-major little-endian binary64 payload。直接比较 payload 与指定端序的 struct bytes，避免 save/load 同时使用错误端序却仍通过自洽 roundtrip。Metadata 单独用给定 JSON codec 转 UTF-8，entry 顺序对应每条向量。

读取先检查完整 payload 长度和 sidecar 长度/条数，再 unpack、组装 VectorRecord。不能转换 float32，-0.0 与 tiny values 都需要按字节保留。写前完成 shape/编码检查；两个文件没有原子事务或断电恢复保证。

## Part 3 packed Hamming 与两阶段检索

给定 packer 用 MSB-first。Hamming 对每对字节 XOR 后数 1；若维度不是 8 的倍数，末字节只留有效高位。直接 popcount dirty padding 会把不存在的维度算进去；维度整除 8 时则保留完整末字节。

粗排按 Hamming 和原 bank index，取 shortlist_m。只对这些候选调用修好的 dense metric，再用修好的 order_hits 排序，取 final_k。两阶段的数量、排序与 score 语义分开；dense 平局不能继承 coarse order，binary_rank 也不能被 final rank 覆盖。

这是本课 docs binary-first/full-precision rescore 及讲解 packbits/XOR/popcount 的标准库教学实现。原 Python/TS 主实现没有 packing 和两阶段 pipeline，本题没有宣称其已存在或验证真实 recall。

## Part 4 binary record encoding

两个同步函数分别返回完整 BVS1/dimension header 和完整 raw record。Header 的 dimension 是向量坐标数。record 先用声明 dimension 校验当前 row，再连接 `<I metadata_byte_count>`、给定 metadata bytes 与完整 packed sign code；长度数 UTF-8 bytes，坐标和 metadata 都保留原记录顺序。正确 JSON codec、sign packer 和严格形状 helper 已给定，不重新考 tail bits。

正确 GIVEN driver 负责先发 header 才拉 source，每次同步 callback 的完整 bytes 发出后才拉下一 record，并在正常、早停或 callback 异常时关闭 source。公开 async 入口也正确给定。空 source 仍有 header，transport 可任意拆分 bytes；这些断言检查完整管线，不要求候选重做 async cadence。

## Part 5 给定 multilayer graph

每层从 current 开始，把 current 与全部 neighbors 用正确 metric/index key 比较，只在完整 key 严格改善时移动。这样分数相同也只能朝更早的 bank index 走，不会在 plateau cycle 来回。

只使用给定方向的邻接边，不补反向边，也不扫描全层。没有邻居改善时停在 local optimum，不保证找到其它位置的全局最近点。

记录本层 path 后，把 best 带到下层。相同 node 在不同层有不同邻居，不能用 global visited 屏蔽。这里只检查给定邻居图，不构建 HNSW，也不承诺复杂度或近似检索质量。

## 这套题证明了什么，没证明什么

通过说明你能修复投影与 metric 流水线，保存 binary64 向量与 metadata，实现有效 bit 的 packed Hamming、候选池内 dense rerank、binary record 流和给定分层图的 greedy descent。它没有调用真实 embedding 模型、证明 Matryoshka 训练效果、测量真实召回率/压缩质量、实现完整 HNSW、向量数据库或 crash-atomic storage。60 分钟的难度与时间分配尚未经过真人计时校准。
