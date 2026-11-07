# 参考答案讲解：BargainKit（16/16）

计时结束后再看。参考代码在本目录 `bargainkit/` 中；在自己的作答副本可用 `python3 -m pytest --solution --all-parts` 检查参考模式。退出后关闭答案，去掉 `--solution` 重写自己的实现。当前原样参考五关与完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。练习命令本身不是执行证据。

## 来源与本地合同

来源使用int／float固定比例让步，不是真正Zeuthen或Rubinstein策略；其standing-price清算和inclusive reservation判断本已正确。来源的共享BargainState同时携带两方私有保留价，且没有真实narrator；打印的成交率与Takeaways也不能当作本题oracle。

本题将机制／叙述分工适配为exact Decimal ticks、只含own私有信息的policy input、完整checkpoint、公私dual JSONL、公开numeric／narration revision和nested multi-issue utility audit。standing／inclusive缺陷、公开reserve模板和逐tick相减都是本地教学回归，不宣称来源原有这些问题。输出artifact只作为来源数据阅读，未执行其中skill；来源论文、年份、模型排名和框架叙述没有做当前外部核验。

## Part 1 supplied standing quotes与真实tick编码

第一个错误在正确的 `require_quote_price` 暴露。producer `try_settlement` 返回standing UID，却把incoming price放进settlement；`OfferDesk.evaluate_supplied` 经 `settlement_receipt` 到consumer，引用证据与数值不一致，于是自然ValueError。正确修复是成交在对方已standing quote：incoming buyer crossing ask用ask价，incoming seller crossing bid用bid价。

随后保持两个reservation端点inclusive，因此singleton ZOPA仍能成交。双方surplus来自真实standing settlement，分别为buyer_limit-price与price-seller_limit；不能为躲错误关闭全部清算或修改consumer。

`public_offer_view` 保留typed quote，用approved side／price／currency形成固定模板，不拼own reservation。此处是候选人负责的公开叙述边界；P2／P4／P5的通道或公开诊断有各自完整Given，不要求重复实现秘密字段过滤。

`count_price_ticks` 接收Given `amount_atoms` 产生的同量纲整数amount>=0和tick>0。reference用 `divmod` 得到quotient与remainder；余数非零拒绝off-grid，否则返回商。0、单tick、非unit tick都保持精确，不通过float或取整把非法报价变成合法值。结果真实用于每条public price_ticks和每个settlement_ticks，并保留原金额／tick／身份。它只编码已给定价格，不负责决定下一口让步。

性能fixture有128条完整合成本地supplied requests。完整 `OfferDesk.review_many` 加whole `BatchReview` equality在计时内，原始请求、standing-price receipt、双方surplus、两个tick counts、public quote与叙述均保留；fixture和独立数学expected在外。本机独占完整3slow3fast测得slow为0.479447／0.443121／0.442912秒，fast为0.00451442／0.00450783／0.00431154秒；限值0.04秒，双侧余量11.0728／8.8605，最慢业务0.479447秒。原样参考五关通过，subprocess wall为0.21215秒。六份完整五关测量版本保留全部业务输出guard，仅把timing断言改为真实elapsed打印；slow另采用真实逐tick相减，不能称slow通过原限值。测得余量依赖本机环境，不是任意墙钟上界或SLA。

## Part 2 dual JSONL checkpoint

`BargainArchive` 建模完整续接状态：negotiation／issue／tick、round、revision、next_side、两个standing quote slots、closed与settlement；buyer和seller分别保存完整strategy；public offers通过checkpoint UID关联，保留顺序和重复观察。

`DualJournal` 是完整Given。save向private.jsonl和public.jsonl分别append该UID的一份完整snapshot，load按UID取最新记录。candidate把真实领域字段接到typed codecs并重建 `SavedBargain`，不能把另一个UID的latest记录误作当前状态，不能重开后归零round或把双方slot混用。

exact Decimal/Fraction/None、quote／settlement／public codec以及typed public routing完整给定。concession经Given codec保存为exact Fraction并恢复精确数值，不承诺原Python类型或Decimal scale；报价与tick的声明文本scale另行保留。public路径接收封口PublicOffer，不从raw private dict临时挑字段。这里检验正常进程close／reopen与状态关联，不证明文件权限保密或双文件append的崩溃原子性。

## Part 3 own-directed concession与有界runner

### 两侧自己的有向gap

policy只接Given binder产生的own输入和公开counterquote。buyer在counter>base时计算counter-base，seller在counter<base时计算base-counter；无counter或已更有利时返回base，不反向改价。将Fraction或有限Decimal concession转为Fraction，与exact gap相乘，不能读对方reservation决定自己的策略。

### tick量化、进展与clamp

对正向量计算 `floor(gap × concession / tick)`，仍有可行空间时至少一tick。buyer从base units向上移动，clamp在own上限；seller向下移动，clamp在own下限。Given `units` 复用修好的P1价格编码，`tick_price` 构造指定tick scale的Decimal；有向差、比例缩放和量化决策仍由候选人写，不存在完整让步solver供调用。

例如buyer base=1.00、counter=1.15、tick=.05、concession=1/2，量化后走一tick到1.05；seller对应从2.00走到1.95。很小的正gap也要在own reservation允许时保留一tick进展；已到own limit则不越界。

### 从half-round继续

`run_bargain` 先处理closed与no-zopa，再按saved.next_side选择own policy。每口quote增加revision，更新对应standing slot，追加实际public offer并切换side；只有seller turn完成一个round。max_rounds限制总full-round计数，不是重开后额外预算。已经到达总上限的open checkpoint不再产生报价；有限Decimal concession的精确数值也要决定实际tick移动。

每口quote实际走修好的P1 facade：成交在counterpart standing price，立即返回deal；closed再调用不产新offer。轮次耗尽返回exhausted，无ZOPA不伪造成交。测试真实生成P1公开opening，经P2保存／close／reopen到seller half-phase，再交替到最终deal，依赖不是闲置调用。runner可以持有双方state，但每个policy仍只接本方capsule。

## Part 4 实际九字段NDJSON

Given `public_events` 已把P3真实结果分类为offer／accept／no-deal，accept也已选择引用的standing quote。`NarrationCatalog`按(quote UID, revision)解析公开叙述；terminal suppression、NDJSON writer和async close都完整给定。

candidate `event_fields` 构造九项：negotiation_id、round、side、kind、price、offer_uid、revision、price_ticks、narration。price由typed quote exact rendering，ticks由同一quote的实际金额编码；narration只提供同revision的描述。文本中出现999不改变0.00报价；同UID新revision不能借用旧文本。no-deal保留本条身份／phase，所有quote相关字段为None。事件round属于当前观察，accept所引用的standing quote可以来自更早的一轮。

测试使用实际P1/P2/P3结果和真实public history，也检查失败／不同revision观察。候选人工作是own numeric／phase／narrative关联，不是实现第二套privacy、classifier、cadence或JSON framing。

## Part 5 nested joint feasibility

Given `OfferCatalog`完整负责global issue／party／group binding、finite unique ordered tree、typed term intake、有限utility系数与每层完整all-party minimum vector。数量超出自身区间仍是合法待审计输入，不能在解析时丢掉；公开blocker serializer也已封口。候选人负责真正递归评估。

先递归得到ordered child audits，当前terms为own terms加各child的全部terms，保留每个层级报告。quantity按inclusive区间检查，required issue coverage基于当前层全部terms；children通过不能替代parent自己的coverage或minimum，failed child也不能被parent抹掉。

对每个party、每个term计算：

```text
contribution = unit_value[issue] * quantity + cash_weight[issue] * price
joint_utility[party] = sum(contribution over every term in this layer)
```

price是该term声明的cash contribution输入，不自动再乘quantity。按各party汇总所有issue贡献，再逐一比较当前group的minimum；所有party都必要。测试中真实P3 settlement price进入cpu term，root得到buyer utility 40、seller utility29；把buyer minimum设41或seller minimum设30都应失败，即使children各自可行。

first blocker顺序为：own首个quantity问题，首个失败child，当前层首个missing required issue，当前层首个joint minimum短缺。quantity记录term UID与nested path；missing issue用term_uid承载缺失issue；joint shortfall记录group path、party和category，term_uid为None，没有唯一leaf归因。当前层own quantity与child问题同时存在时，保留当前层own witness的优先级。即使失败也算完整utilities，保留own／child terms和全部child audits。

`PrivateGroupAudit`保留本层完整minimum_utilities、私有utilities与判断结果；Given `public_blocker`只发布批准的path／term_uid／category，不发布party utility或threshold。这是给定proposal的联合可行性审计，没有搜索最优方案，也不是budget knapsack、投票或均衡solver。

## 这套题证明了什么，没证明什么

当前静态清点：48个Python文件、五测试、39assert、1raises、五分关锁、26个登记错误写法。当前原样参考五关与完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。P1的128条合成本地完整requests、whole BatchReview equality和0.04秒限值当前完整性能组通过；本机测量范围见Part 1，不能推出通用时间上界。

这些行为合同检验候选人在有限typed域内完成standing-price调试、完整checkpoint续接、own-direction Fraction／tick策略、有界交替runner、实际公共字段投影和nested all-party feasibility的判断。P2／P4／P5的public边界、codec、catalog和driver为完整Given，不能将其另计为候选人独立实现。

这不证明真实LLM成交率、收益、公平性、persona效果、论文复现、Zeuthen／Rubinstein／FIPA协议实现、网络传输、文件保密、崩溃事务或博弈安全。任何后续有限本机workload结果都依赖环境，不能推出任意规模墙钟上界或SLA。60分钟安排尚未经过真人校准。
