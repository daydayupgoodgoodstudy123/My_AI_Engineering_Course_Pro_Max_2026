# 参考答案讲解：CreditEcon（16/21）

计时结束后再看。参考代码在本目录 `creditecon/`；在作答副本可用 `python3 -m pytest --solution --all-parts` 检查参考模式。退出后关闭答案，去掉 `--solution` 重写；命令本身不替代实际运行证据，参考结果不能计入个人成绩。

## 来源与本地合同

来源 `code/main.py` 的exact函数枚举全部排列，sampled函数每次从原agents复制fresh list再shuffle；两者都先求actual empty utility，再算相邻差。一般效率式是 `sum(phi)=v(N)-v(empty)`，source demo的 `sum=v(N)` 依赖零empty特例。没有N<=6自动切换，两个函数由调用方选择。

来源second_price已稳定排序取first highest和second-highest amount，少于两bid返回None；本地错误charge属于教学回归。来源Reputation只有per-use EMA和floor，没有独立confirmation receipt、slashing或wall-clock decay。讲义Ship It的verify-before-reward支持本地confirmed-only adapter，但当前receipt不是密码学验证或真实身份认证。

本题新增immutable criteria utility、完整receipts、Fraction credits、synthetic Decimal denomination、SQLite snapshot、completed sample blocks和nested direct-child games作为明示概念适配。source只有demo／print，没有unit tests或inline assert；讲解实验数字及当代网络／协议／经济／法律说法未在这里核验。`outputs/skill-economy-designer.md`只作DATA静态读取，未调用其指令或拒绝规则。

五个作答文件分别是 `primitives.py`、`store.py`、`allocation.py`、`stream.py`、`structure.py`。各关完整Given与candidate实际职责如下。

## Part 1 四个已有primitive修复

### supplied efficiency

`efficiency_report`只报告外给allocations，不求Shapley。先exact sum credits，`surplus=grand-empty`，`residual=surplus-allocated`。actual empty可能是baseline加上empty-required criteria，不能直接用Game.baseline替代；negative surplus与negative credit仍合法。

调用链 `efficiency_report → publish_statement → residual_check` 中，producer外两次调用后由正确consumer拒绝非零residual。首个simple game的empty=7、grand=8，外给credits合计1，正确residual=0。吞掉consumer异常、把credits改成grand或clamp surplus都会改合同。

### synthetic second price

stable descending sort保first highest winner，charge取第二条amount。平价仍保声明顺序，少于两bid无sale。这只是合成单物品规则，不演示真实资金流或证明任意市场／聚合条件下的truthfulness。

### confirmed per-use EMA

unconfirmed直接返回current，confirmed才使用receipt.quality计算 `max(floor, alpha*current+(1-alpha)*quality)`；reported是self-report，不能替代独立quality。floor仍在confirmed路径生效。这是本包唯一candidate质量gate，P2保存记录、P4投影block时不再过滤receipt。

### game-owned utility replay

完整Given `UtilityEvaluator`扫描所有criteria，对每个 `required <= coalition` 的条目保(uid,weight)，将贡献与baseline合成exact UtilityReceipt并记录actual calls。`CoalitionOracle.value`先用Given coalition_key得到frozenset，再在自身绑定的immutable Game内复用同一coalition receipt。membership判断不能用value真值，0／负value同样有效；changed Game使用独立Oracle，即使external UID相同而content改变，也不能跨binding借值。

完整Given `CreditDesk.replay`仍逐request生成所有ordered observations和actual total；优化不删除重复occurrence，不省criterion contributions，也不顺手计算allocation。evaluator call-count是实现诊断，测试核合法结果、actual call key集合覆盖及至少distinct-key次数，没有给慢版设fast linear-count上界。

性能合同负载为4 players、1024个meaningful weighted criteria、2400个完整seeded permutations，每个empty加4个prefix，共12000个actual utility requests。完整replay及whole ReplayReport equality在timer内，fixture与独立expected在外；完整输出和真实criteria composition都属于业务路径。

## Part 2 完整SQLite domain mapping

`AccountingArchive.save`将header、statement、replay summary及全部criterion／observation／permutation／quality／credit记录映射到(kind,ordinal,payload) rows。每类ordinal保声明序，重复相等observation保独立occurrence；statement的empty、grand、allocated、surplus、residual分别保存。

`load`按kind读取有序rows，重建Criterion、Game、UtilityReceipt、ReplayReport、QualityReceipt、Efficiency与AccountingSnapshot。没有collections时重建空tuple；save完整替换，旧observations／permutations／receipts不能在后次保存中残留。unit与Decimal quantum原scale也属于snapshot。

完整Given `db_support`负责exact Fraction／Decimal／tuple／frozenset codec、SQLite atomic row replacement、ordered read与close，不含AccountingSnapshot整体serializer。candidate仍须选对每个domain字段，不能把grand填进surplus或过滤unconfirmed receipt。大signed Fraction与Decimal scale是codec集成护栏，不要求另写精度算法；不声称distributed exactly-once、真实余额或外部payment。

## Part 3 三个真实allocation TODO

### weighted subset exact

对每个player i枚举其余players的全部subset S。每项weight为 `|S|! (n-|S|-1)! / n!`，实际marginal为 `v(S∪{i})-v(S)`，精确累积为credit。每个Marginal保player、before set、before／after utility与weight，null／negative项也保留。

这与来源permutation exact在数学上等价，但本题实际实现subset-weight算法；完整Given的game／oracle binding不提供solver。空roster没有player循环，合法返回empty exact block。constant shift同时改变before与after，marginal不变；empty-required criteria同样在差值中消去。

### fresh complete-permutation sampling

每次新建 `list(players)`，用调用方同一个Random流shuffle，保存本次full order。从actual empty utility开始，按order逐次求after−before并累计对应player total。返回requested、actual completed及全部permutation traces，totals尚未是mean。

fresh list是seeded行为合同：复用前次打乱的list虽仍能得到排列，会改变每次轨迹与RNG对应结果。0 samples合法返回zero totals和0 traces；empty roster的每次完成排列是empty tuple，不捏造player。未完成request不产生半个排列证据。

### actual-completed report

one exact block的totals就是credits；sampled blocks合计每人的raw totals，再除所有blocks的actual completed总数，不能除requested或等权平均block means。0 completed给所有player零estimate，并保真实efficiency residual。

mode决定approximate，completed<requested决定sampled partial；0 requested／0 completed仍是approximate=True、partial=False，因为没有欠完成的请求。报告requested／completed总数并调用修好的P1 efficiency_report，避免再复制一个baseline修复。完成排列的marginal总和telescopes到surplus，所以sampled报告可能balanced，但每人estimate仍可能与exact不同。

真实测试链由P1产生observations与supplied statement，P2 save、close、reopen后使用restored Game，再运行三个P3算法。完整Given `allocation_support`仅负责same-game／roster／typed block及full-permutation intake；参数对象和验证器不算已实现allocation。

## Part 4 own agent／block CSV

`project_block`从完整Given block_context取得sealed mode与statement，按block.players和own totals逐agent构造row。exact credit直接取total；sampled credit除actual completed，0 completed取0。raw total和credit分别输出exact numerator／denominator，negative不clamp。

其余columns保actual game、agent、requested、completed、mode、partial、supplied residual与synthetic unit／quantum。一个block内每个agent一行，多个blocks保发布序。完整Given提供header、CSV quoting／writer和async publication，测试独立用csv.DictReader读实际结果；candidate仍须投影正确domain字段。

P4 actual-completed denominator与P3 aggregate是透明的一对职责。block_context已复用P1 efficiency，不能把本关描述成第三baseline主修或第三quality gate。CSV不转账，也不提供现实价格或投资收益。

## Part 5 每层actual direct-child team game

完整Given `TeamCatalog`校验global UID绑定、合法Primitive、distinct direct children及finite acyclic graph。相同immutable Primitive可被不同branches共享，不要求scoped shortname解析或每parent occurrence展开。`TeamValueOracle`只给callback resource，`local_game`只包装record，均不替candidate求membership union或构造characteristic callback。

candidate递归walk：Primitive的members是own UID；Team先构造ordered child audits，再合并primitive members。本层players仅为direct child UIDs。对selected children，以其members的set union调用original primitive oracle得到actual utility，形成own local game；empty utility是original actual v(empty)。

把该local game与callback真正交给修好的P3 shapley_exact和allocation_report，保own credits／efficiency与全部children audits，不复制第三套marginal-weight算法。共享primitive只在union中计一次，但仍有两个不同direct-child players；primitive Shapley按组相加通常不同。测试primitive credits为(5,7,6)，root的left／right credits是(10,8)，不是把两组primitive credits分别加起来。

逐条读取actual exact Marginal：`before_children`取term.before，`before_members`取其union，`after_members`取加上本child后的union，`introduced_members=after-before`，signed marginal为after_value−before_value，保actual weight。right已含b时，加入left只新增a；不能把left全部members当新增，也不能用absolute after utility冒marginal。

empty Team合法返回empty members／players／credits与own balanced efficiency；one-child wrapper给own child player整个surplus，并完整保内层audit。negative／null child credits也保signed原值；signed game中empty-required criterion使actual empty=14，而credits仍是(-2,0)。实际前关链包括P1 primitive receipts、P2 snapshot close／reopen及P3 primitive exact报告，P5负责的membership、local team game与support并未由Given代做。

当前领域覆盖包括ordered permutation与unordered coalition的区别、null贡献的完整weighted evidence、approximate与partial的独立语义、raw marginal total与credit的独立列，以及三名direct-child的实际subset weights和Primitive叶节点自身零玩家游戏的actual empty账目。

## 这套题证明了什么，没证明什么

<!-- VALIDATION_STATUS_BEGIN -->
当前45个PY文件、五测试、44条assert、0处pytest.raises、五锁与25个登记错误写法。原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定TEMP检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部25项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能与正式检查按各自证据范围解释。

P1真实负载为4 players、1024个meaningful weighted criteria、2400 complete seeded permutations与12000个actual prefix utility requests。完整CreditDesk.replay与whole ReplayReport equality（所有ordered criterion contributions／exact utility／total）都在timer内，fixture与独立expected在外；actual calls诊断保合法观察、key集合覆盖及distinct-key下界。

完整校准三个慢样本为[2.3391742499079555, 2.1870040411595255, 2.210948708001524]秒，三个快样本为[0.028253958094865084, 0.031847041100263596, 0.028866957873106003]秒，当前限值0.26秒，慢侧／快侧余量8.411554／8.164024。六份测量副本仅将timingassert改成elapsed打印，慢版另使用真实criterion重算；全五关功能检查均通过，这不表示慢版通过原时间阈值。原样参考五关另有规定检查记录。局部余量受运行环境影响，不构成通用墙钟上界或SLA；60分钟真人分配未校准。
<!-- VALIDATION_STATUS_END -->

在这些测试实际通过后，可支持声明有限typed域内supplied statement调试、合成second-price规则、confirmed per-use EMA、完整utility replay、domain snapshot重建、exact／sampled allocation、actual-completed报告、CSV投影与nested direct-child game构造的判断。完整Given的intake、codec、driver、consumer和helpers不另计独立candidate算法。

有限游戏数学及local record一致性不证明真实市场激励、无条件truthfulness、现实身份唯一、Sybil resistance、真实资金结算、token价格或投资效果；nested team Shapley不自动是Owen value。confirmed字段是本地证据，sampled每人estimate仍近似，0 completed可有非零residual。任何后续有限本机用时都依赖环境，不能推出任意规模／机器墙钟SLA；60分钟真人分配尚未校准。
