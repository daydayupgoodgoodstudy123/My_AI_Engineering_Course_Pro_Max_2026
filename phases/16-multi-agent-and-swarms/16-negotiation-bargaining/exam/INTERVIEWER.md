# 面试官手册：BargainKit（16/16）

候选人计时期间不要看。候选人使用 README、`bargainkit/` 和 `tests/`。以当前 typed records、docstring和测试为合同；这是原创练习评分，不是公司或官方认证标准。

## 开场（2分钟）

说明总时长60分钟，编码58分钟：五关分别12、11、15、10、10分钟。请候选人边做边解释，随时澄清，可以查 Python 官方文档。逐关解除skip，之前的测试继续保留。不要只用完成关数判断能力，要记录具体行为和依据。

主持人记录解锁时间、首个完整结果、运行次数、问题与提示。卡住约4–5分钟后从H1开始，一次给一级，不代写代码。独立完成与提示后完成分别记录。60分钟分配尚无真人校准。

这是本地确定性适配。来源有standing-price清算与inclusive边界；这两处缺陷是本题教学回归。exact tick encoding、私有续接、公开叙述、NDJSON和nested utility audit不属于来源完整运行时。来源固定比例让步不是Zeuthen/Rubinstein，Contract Net demo也没有真实消息传输。

## 澄清问题的标准答案

只在问到时回答，用英文说。

| 关 | 问题 | 标准回答 |
|---|---|---|
| 1 | 交叉时用谁的价格成交？ | "Use the opposite standing quote referenced by the settlement, for both an incoming bid and an incoming ask." |
| 1 | reservation端点可以成交吗？ | "Yes. Both bounds are inclusive, including a singleton feasible interval." |
| 1 | price为0和off-grid如何处理？ | "Zero is a legal price. The tick is strictly positive. Return the exact integer count and reject any nonzero remainder." |
| 1 | narrator可以透露reserve或改价格吗？ | "No. Public narration uses approved quote fields only. The deterministic numeric quote is authoritative." |
| 2 | 保存的是delta还是完整状态？ | "Append a complete checkpoint. Each UID reopens its own latest private continuation with its linked ordered public offers, including repeats." |
| 2 | 公私边界和exact codec要自己写吗？ | "No. DualJournal, exact typed codecs and public-channel routing are complete Given. You own the checkpoint fields and their associations." |
| 2 | 两份JSONL保证崩溃原子性和保密吗？ | "No. The contract covers normal-process append, close and reopen. It does not establish filesystem secrecy or an atomic two-file commit." |
| 3 | policy能看对方保留价吗？ | "No. The supplied binder exposes the acting party's own private input and public quotes only." |
| 3 | concession的数值类型与保存合同是什么？ | "Accept an exact Fraction or finite Decimal in (0,1]. Preserve its exact numeric value through the supplied codec; the original Python type and Decimal scale are not required. Quote tick scale is separate." |
| 3 | 无counter或counter已更有利怎么办？ | "Keep the own base offer. Do not reverse direction. A positive feasible gap gets at least one tick of progress, without crossing the own reservation." |
| 3 | max_rounds是重开后额外轮数吗？ | "No. It is a total full-round ceiling. A seller turn completes one round, and the saved next_side determines the resumed turn." |
| 3 | 无ZOPA或已closed怎么办？ | "An empty feasible interval returns no-zopa without an offer. A closed checkpoint produces no new offers; a reached round ceiling returns exhausted." |
| 4 | 数字应从叙述解析吗？ | "No. Project the typed numeric quote and its exact ticks. Resolve narration by the same quote UID and revision using the supplied catalog." |
| 4 | classifier、terminal和stream清理呢？ | "They are complete Given. You construct the nine actual event fields; terminal observations may be replayed, while a closed mechanism produces no new offer." |
| 5 | children各自可行是否足够？ | "No. Every layer also needs its own required issue coverage and every party's joint minimum across its own and descendant terms." |
| 5 | cash contribution要乘quantity吗？ | "Use unit_value times quantity plus cash_weight times the declared term price. Price is not automatically a per-unit price." |
| 5 | joint shortfall应该指向哪个leaf？ | "It identifies the current group path and private party, with no invented unique leaf cause. The supplied public diagnostic exposes approved structural fields only." |
| 全部 | 是否证明真实谈判效果或协议安全？ | "No. This is a finite local deterministic adapter with no real LLM, market, transport or equilibrium proof. Local timing does not establish a universal wallclock bound." |

## 每关：主要坑、观察、提示、追问

### Part 1 supplied-offer review（12分钟，20分）

四层按实际调用暴露：

1. `try_settlement` 保留standing UID却使用incoming price。正确consumer经过 `OfferDesk.evaluate_supplied → settlement_receipt → require_quote_price`，在producer之外两次调用处自然报ValueError。应修成交价，不能改receipt检查或重贴UID掩盖不一致。
2. 可行区间两端inclusive。strict比较会拒绝buyer_limit与seller_limit相同的一点ZOPA。
3. `public_offer_view` 的叙述把own reservation拼进公开文本。只用approved quote字段形成固定模板；这是候选人负责的公开／私有边界。
4. `count_price_ticks` 逐tick相减，编码真实金额的网格单位。用整数商余数保持exact单位数量和off-grid拒绝，结果必须继续进入public price_ticks与settlement_ticks；不能取整放过余数或写死常数。

观察：是否读traceback并回查生产者；是否区分incoming和standing证据；是否保留双方真实surplus；是否在完整输出正确后分析循环随数值单位数增长。完整Given提供exact atoms、合法角色／standing intake、consumer、OfferDesk与独立expected。P1不生成下一口报价，也不决定P3让步。

提示：

- H1："Which value no longer agrees with the quote identity referenced by this receipt?"
- H2："Trace standing price, inclusive bounds, public narration and actual integer grid counts separately."
- H3："Clear at the standing quote, keep both endpoints, build narration from quote fields, and compute exact quotient and remainder instead of subtracting every tick."

追问：

- "Why not change the settlement UID to the incoming quote?"（改变了协议清算对象，未修standing-price合同。）
- "Why reject a nonzero remainder instead of rounding?"（报价不在声明grid，不能由展示编码器悄悄改价。）
- "Does removing reserve text secure the whole system?"（只满足这一公开模板的边界，没有文件或对抗安全证明。）

### Part 2 dual JSONL continuation（11分钟，20分）

主要坑：

- 需要完整state：negotiation／issue／tick、round、revision、next_side、closed和settlement；不能重开后从第0轮或buyer重新开始。
- buyer_quote和seller_quote分别是自己的standing slot，buyer/seller策略各自保留party、side、reservation、opening与concession；身份和角色不能串位。
- 每个checkpoint UID读取自己的最新完整snapshot。public offers保留声明顺序和重复观察，并与私有续接关联；另一UID不受本次更新影响。

观察：是否先列checkpoint字段和所属记录，再接 `DualJournal`；是否用新archive实例close/reopen检查完整equality。exact Decimal/Fraction/None和typed quote／settlement／public codec、逻辑通道、append与latest-record读取均有完整Given。public边界、精度和0/None是依赖集成护栏，不重复作为候选人的主算法。

提示：

- H1："What would the runner need in order to continue this half round exactly?"
- H2："Keep both standing sides, both private strategies, phase, terminal settlement and ordered public observations distinct."
- H3："Build the full private checkpoint document, pass typed offers to DualJournal, then reconstruct that UID's latest state and public history with the supplied codecs."

追问：

- "Why is an append log still loading a full snapshot?"（每条保存完整状态，按UID取最新；并非逐delta重放。）
- "What extra design would a crash between the two appends require?"（事务／commit marker等需另定合同；当前normal-process行为不承诺它。）

### Part 3 directed concession与bounded resume（15分钟，25分）

三个真实TODO：

1. buyer向更高standing ask靠近，gap为counter-base；seller向更低standing bid靠近，gap为base-counter。将Fraction或有限Decimal concession转为exact Fraction后缩放；无counter或counter已更有利时保留base。
2. 对正向让步量按tick向下量化，仍可让步时至少一tick；buyer不能超过own reservation，seller不能低于own reservation。基础arithmetic和tick_price完整Given，但有向gap、比例和量化决策不是Given solver。
3. `run_bargain` 从真实重开的phase交替运行，用修好的P1生成公开报价和standing settlement。seller turn完成一轮；max_rounds是总full-round上限。deal立即停止，no-zopa不造offer，exhausted明确，closed resume不再出价。

测试真实走P1 supplied opening→P2存储并重开half-round→P3继续。完整role binder只给policy本方capsule；runner持有双方状态不等于policy能读取对方reserve。

观察：是否先说清单位和方向；是否把价格转units与“决定让多少”分开；是否保留next_side、revision、round和public history；是否能解释一轮与一turn。不要只凭三个stub名字评分，要看gap／量化与runner的实际实现。

提示：

- H1："Which direction is a concession for each side, and what information may that policy use?"
- H2："Scale the positive directed gap, quantize in ticks, clamp the own limit, then resume the saved phase."
- H3："Floor gap times concession divided by tick, require one feasible tick, and update revision each turn but round only after a seller turn; stop as soon as P1 clears a deal."

追问：

- "Why is deterministic concession not a Zeuthen equilibrium solver?"（固定比例不比较Zeuthen冲突风险，也无均衡求解。）
- "Does a higher deal rate imply better buyer payoff?"（还需surplus与分配，不能只看成交率。）
- "Why can't max_rounds be added to saved.round?"（会把总预算变成每次重开扩容，违反总full-round上限。）

### Part 4 public numeric／narrative NDJSON（10分钟，15分）

主要坑：

- 九字段来自本条事件：negotiation_id、round、side、kind、price、offer_uid、revision、price_ticks、narration。身份、phase和kind不能从上一条或固定side代入。
- price来自typed quote，tick数来自真实编码。叙述中的“999”没有定价权，0.00也保留原数字文本；no-deal没有虚构quote字段。
- 同一offer UID的不同revision要取匹配叙述。accept使用Given选择的standing quote及其revision，不借用最后incoming文本。

观察：是否基于实际P3结果投影own fields；numeric与narration是否各自绑定同一quote/revision。classifier、public boundary、NarrationCatalog、NDJSON framing、terminal suppression和async close全部完整Given，不考第二套privacy过滤或cadence算法。

提示：

- H1："Which typed event and quote own each field in this row?"
- H2："Keep numeric price separate from descriptive text, and look up the exact quote revision."
- H3："Construct all nine fields from this event, use price_field and units for numeric evidence, and use the supplied catalog for the matching narration; no-deal has no quote values."

追问：

- "Why can an acceptance price differ from the final incoming offer?"（成交在对方standing quote。）
- "Why retain narration revision if the UID is unchanged?"（同UID可有不同公开文本／数字版本，要准确关联。）

### Part 5 nested all-party feasibility（10分钟，20分）

主要坑：

- 每层保留own terms加ordered child terms、该层minimum_utilities，以及所有child audits。children可行不能替代parent自己的约束；child失败也不能被parent抹掉。
- quantity区间inclusive，required issues必须在整层实际terms中全部覆盖。out-of-range quantity是合法待审计输入，仍要算完整utilities，不能当成解析错误提前丢掉报告。
- 按party对全部terms累计 `unit_value × quantity + cash_weight × price`，再分别与该层完整minimum vector比较；所有party都必须满足。不能只查buyer、逐term独立过门槛、做多数票，或给price自动多乘quantity。
- first blocker按own首个quantity问题、首个失败child、首个缺issue、首个joint minimum短缺确定。quantity有term/path，missing issue把issue UID放term_uid；joint shortfall只有当前group path与party，没有唯一leaf原因。

观察：是否真实消费前关最终settlement price进入term；是否在失败时仍保留完整term和utility accounting；是否区分私有audit与Given public_blocker。完整catalog提供global UID／issue／party binding、finite unique tree、finite系数和全party minimum vector校验、typed intake与公开诊断；candidate负责递归评估和joint aggregation，不负责通用名称／循环或第三次secret filtering。

提示：

- H1："Can both children pass while the parent still fails a private minimum?"
- H2："Collect all terms for this layer, check coverage and quantity, then sum each party's complete utility before comparing minima."
- H3："Keep ordered child audits; prioritize own quantity, child failure, missing issue, then joint utility. A joint shortfall belongs to the group and party, not an invented single leaf."

追问：

- "Why isn't this Pareto optimization?"（只是核对给定proposal是否满足全部声明约束，没有搜索最优解。）
- "Why does the seller-only guard matter?"（某一party通过不代表全部party接受。）
- "What can the public blocker reveal?"（Given只发布path、term_uid、category；不发布utilities、threshold或party隐私。）

## 记录与评分（100分）

每项填写实际代码、行为或断言证据；未观察到写“未观察”。提示、沟通和用时另记，不从参考代码推定候选人已完成。

| 关 | 评分项 | 分值 | 实得／证据 |
|---|---|---:|---|
| 1 | standing身份／成交价与双方surplus一致 | 6 | |
| 1 | inclusive reservation端点 | 3 | |
| 1 | approved public narration且保留实际报价 | 5 | |
| 1 | exact tick商余数／off-grid与完整输出 | 6 | |
| 2 | 完整state、phase与terminal settlement | 7 | |
| 2 | 两方standing slots与独立private strategies | 7 | |
| 2 | own UID最新snapshot和ordered public history | 4 | |
| 2 | Given exact codec／DualJournal正确集成 | 2 | |
| 3 | 两侧自己的有向gap与Fraction concession | 8 | |
| 3 | tick量化、最少可行进展与reservation clamp | 7 | |
| 3 | phase续接、交替／round预算与terminal停止 | 8 | |
| 3 | 真实P1／P2 checkpoint整合 | 2 | |
| 4 | actual negotiation／round／side／kind | 5 | |
| 4 | own numeric quote／UID／tick counts | 5 | |
| 4 | matching narration revision与no-deal字段 | 5 | |
| 5 | ordered own／child terms、minimum vector与完整层级报告 | 5 | |
| 5 | quantity及完整required issue coverage | 4 | |
| 5 | 所有party的joint utility与minimum检查 | 7 | |
| 5 | first blocker顺序／结构归因及失败时完整accounting | 4 | |
| 合计 | Part 1/2/3/4/5 = 20/20/25/15/20 | 100 | |

## 当前验证边界

静态清点48PY、五测试、39assert、1raises、五锁、26个登记错误写法。当前原样参考五关与完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。

性能为128条合成本地真实requests，完整OfferDesk批次和whole BatchReview equality在计时内，fixture／独立expected在外；0.04秒限值的当前完整性能组通过。所有tick数真正进入receipt或公开数字，不表示实际市场、供应商计费或网络时延。P1 supplied-price encoding不提供P3决策；P4classifier／channel与P5public blocker均是完整Given，不重复计为候选人privacy实现。60分钟真人用时未校准。

本机独占完整3slow3fast测得slow为0.479447／0.443121／0.442912秒，fast为0.00451442／0.00450783／0.00431154秒；限值0.04秒，双侧余量11.0728／8.8605，最慢业务0.479447秒。原样参考五关通过，subprocess wall为0.21215秒。六份完整五关测量版本保留全部业务输出guard，仅把timing断言改为真实elapsed打印；slow另采用真实逐tick相减，不能称slow通过原限值。测得余量依赖本机环境，不是任意墙钟上界或SLA。
