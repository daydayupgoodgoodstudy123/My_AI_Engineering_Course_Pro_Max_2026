# 参考实现说明

这套本地服务将 source 混合 simulator 拆成事实收集、持久化、精确 economics、CSV事件和 Section布局。它不连接真实 provider；所有价格/TTL/minimum 都是输入 fixture，不验证来源的时效性厂商宣传。

## Part 1

decode_request 使用正确 primitive reader 将 prefix_tokens 投影为整数。原字段是字符串时，正确 usage_counts 在 producer 外两次调用处相加报 TypeError；应修生产者而非把 consumer 改成字符串拼接。Collector 保留每个实际写入对象，finish 不只看最终 current。lookup 使用 `(profile_id, exact prefix_key)` 字典，读取不刷新写入时间；current 与所有 observations/objects 各司其职。完整压力路径包含所有 typed解码、生命周期处理、完整结果和对比，没有截断输出。

## Part 2

Given codec 完整编码/解码 PriceProfile、RunHeader、Observation、Lifetime，保留价格原词面与整数微秒。候选追加 typed record，再重放全部顺序，将 observations 和 lifetime 按 run_id 分组，校验 profile/run 不可变声明及引用。每个 run 按 header 的 profile_ids 绑定价格。不能去掉 READ/UNCACHED，不能把相同 prefix 的历史 write 合并；不计算任何费用。

## Part 3

prefix 输入费为 tokens/1000×对应 WRITE/READ/UNCACHED rate；suffix 一直用 base。每个独立 Lifetime 的 storage 是 prefix_tokens×(observed_end_us−created_us)/(1000×3600×1000000)×storage_rate。无提前舍入，Fraction 接收原字符串；baseline 为全部 prefix+suffix 按base，不包含cache storage。savings=(baseline−total)/baseline，baseline为0时为0。每个profile有独立明细。

Inverse 只对一个已声明写入窗口求 `W+nR+S < (n+1)B`。W+S<B 时 n=0；否则 B−R≤0 时 None；正改善时 `floor((W+S−B)/(B−R))+1`，即使等号边界也再前进一次。费用数学全部属于本关，P1没有给出一个定价helper。

## Part 4

event_driver 真正提供异步逐项拉取、当前 record身份、CSV与close；candidate project_event 只消费完成的 observation 和本次新建对象，调用修好的 P3，累计金额与角色计数。TIME来自 timestamp_us，READ 不新增 storage。final_row 给空流显式零合计。CSV成本给定 exact_text 为整数或分数，有理数可精确往返，不谎称任意分数有有限decimal展开。该流在已知报告horizon内重放，创建事件带其完整已观察窗口，不是实时预测账单。

## Part 5

先按原始 preorder 展开所有叶子，继承 stable=False，完整保留各variant的tokens与fullpaths。求真实 exact LCP；选首个 volatile leaf 之前、不超过LCP的最大正完整leaf末尾。不得截半个section、跳过动态字段拼接后缀、排序tools或规范化Unicode。空/零token layout无正断点，single observation使用全部自身前缀直至volatile。空 leaf 保留在完整路径中；选择断点时既要求累计位置为正，也要求当前 leaf 的实际渲染 token tuple 非空。空 leaf 本身不阻断后续稳定内容。全部 variants 都参与 LCP，leaf 末尾按实际 variant 长度而非模板长度累加。正确shape/cycle/variantguard是给定依赖。

## 来源与教学替代

source docs20–59/Step5/Exercises2–3提供prefix、经济学、stream观察与布局概念；main58–119是混合simulator。source只在最后cache.values对完整TTL计storage，本题显式改成保留所有真实写入且按独立观察horizon截断；不是声称源码已实现它。source docs“至少两次读取”与其1 write+1 read平均0.675倍冲突，本题按严格不等式计算，不复述该口头断言。Section树、typed journal和CSV replay都是本地教学输入/工程扩展，不是厂商wire protocol。精确前缀 key 使用完整稳定文本；性能回归是插入的brownfield实现，原source本身使用dict。短coderpad LRU/TTL核不作为本题候选算法。

本机性能证据：完整公开 collect_traffic 接收2,500条已解析请求、80条约16K字符的真实exact稳定前缀，包含typed投影/正确生命周期/全部2,500观察和80对象寿命/全字段消费；连续三慢1.303471/1.488525/1.447905秒，三快0.008865/0.008538/0.012463秒，限值0.1秒，最差双侧13.035×/8.024×，单慢最大1.489秒。稳定前缀文本本身是索引与所有记录保留的业务输入；不计JSON字节解析、真实provider或费用计算，不声称生产缓存性能。完整copy与实际日志见SCOPE包外证据。
