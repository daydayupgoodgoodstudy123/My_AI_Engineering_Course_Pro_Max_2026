# 面试官手册：Ratchet（14/54）

候选人计时期间不要看。候选人只有README、ratchet/和tests/。

## 开场（2分钟）

说明60分钟、逐关解锁、原样测试，请边做边讲。约5分钟卡住给一级提示。一个feedback需要改变哪个系统层、如何证明和何时复审，均由明确输入决定；不要求推断真实因果。

## 澄清问题的标准答案

只在问到时用英文回答。

| 关 | 问题 | 回答 |
|---|---|---|
| 1 | Is retry storm missing from the router? | No. The supplied router is correct, including retry and backlog fallback. |
| 1 | Can one incident create two controls? | Yes. Product and workbench impacts remain separate owned actions. |
| 1 | What starts the review lifetime? | The injected promotion date, not the earlier observation date. |
| 2 | Can raw text include CRLF or U+2028? | Yes. Preserve all text with real CSV file reader/writer and newline=''. |
| 2 | Does the artifact identify only the current control? | No. Its history includes every matching physical revision across both tracks. |
| 2 | Does an identical Action get a new revision? | Yes. Every append records another review observation in the global sequence. |
| 2 | Is CSV newline/type handling part of the TODO? | No. The supplied physical codec is already correct. |
| 3 | Does architecture change retire a control? | No. It requests review; retirement needs qualified evidence and approval. |
| 3 | Is the start of the recurrence window included? | Yes. A recurrence exactly there is still inside. |
| 3 | Do equal counts mean obstruction? | No. Legitimate blocks must be strictly more than prevented harm. |
| 4 | Which priority controls promotion? | The merged severity times merged frequency, at or above threshold. |
| 4 | Does a sent action change when more evidence arrives? | No. Keep its emitted snapshot; new impacts can still create independent actions. |
| 5 | C replaces B replaces A? | C suppresses both. Retiring C revives B; retiring C and B revives A. |
| 5 | Does retiring B erase its historical edge? | No. A verified C still covers A through the retained lineage. |

## 每关：要看什么、提示、追问

### Part 1 owned action（目标12分钟）

坑：
1. backlog→promote→_metadata把正确destination配到错误artifact/verification，上层action两层以下违约。两个字段成套，不能修一个丢另一个。
2. 一个incident的第二个track被截掉，产品边界和workbench不能只留一个。
3. review从旧observation日算，使刚建立的control少了review lifetime；从注入promotion日起算。
4. review_date逐日推进，6000个普通180天窗口反复构造日期；一次日历运算即可。

慢三次0.124/0.126/0.129秒，快1.630/1.620/1.579毫秒，限值0.014秒，双侧至少8倍；60/90/180普通窗口精确日期另有护栏。不使用数千年窗口。完整router、空白owner校验和同fingerprint累加从起始给对，不让候选人重修46/45的坑。

看什么：target、证据、track、review时间成套一致，不丢独立影响。

提示：“Which metadata row belongs to this target?”；“Which track disappeared?”；“When did this control's lifetime start?”

追问：为什么一个incident可能同时改变产品承诺和agent权限？control为何不能到期就自动删除？

### Part 2 控件修订历史（目标10分钟）

坑：
- revision按整个文件从1连续编号，不按artifact、control id、track或当前对象各自计数；重开继续原序号，已有空文件从1开始。
- 相同Action再次到达仍是新的review记录，不按相等值去重；同artifact的新版本不能抹掉旧证明。
- history只做exact artifact选择，跨所有product/workbench id与track保留原全局序号，不能以一个track覆盖另一个。
- 每次读取实际文件历史；一个已打开的Ledger也要看到另一个handle后来追加的记录。

read_rows/append_row是起始已正确的物理CSV codec：真实文件newline=''、quoted records、sources tuple与priority int均给定。CRLF/Unicode精确往返与codec错误写法是正确helper的护栏，候选人实现历史政策。

看什么：区分审查观察记录、控件身份、artifact历史和影响轨道，不把追加历史当成current-only快照。

提示：“Is this the next revision of the whole ledger, or just this artifact?”；“Does observing the same control again erase an earlier review?”

追问：多writer或中途crash时，当前单writer追加模型需要哪些额外保证？本题不承诺跨进程事务。

### Part 3 retirement证据（目标14分钟）

坑：
- 架构变化、无记录复发、误拦更多或due先要求review，不能因年龄直接retire。
- verified且覆盖的replacement、或已完整观察的quiet window，再加明确批准才能retire；证据资格helper本来正确。
- window起点含当天，control必须实际存续完整window；相等拦截计数不算“更多”。

不重做51的claim/receipt kind匹配。这里是给定事实下的review/retire政策，不是程序证明真实控件安全。

看什么：先列review理由，再检查是否存在足够retirement依据，不能把一个trigger当删除许可。

提示：“What observation requests a review, and what evidence permits retirement?”

追问：若低层invariant证明后来失效，应保留哪些fallback和原review证据？

### Part 4 多源反馈流（目标12分钟）

坑：
- 使用merged状态判断priority并materialize全部track，不能只用最后一份raw信号。
- emitted snapshot保留触发时所有来源，未来证据不回写已发送动作；继续监控别的cause。
- 同触发事件的全部action行先发完再拉下一份；取消不能预拉。

MergeBook、完整action身份首次gate和NDJSON编码真正给对，不把“只发一次”再当候选主算法。新增impact有自己的identity，不被旧workbench action吞掉。

看什么：归并、目标身份、通知快照和输出边界的分工。

提示：“Did this output use the accumulated evidence or only its last receipt?”

追问：已发动作的后续证据更新如何另行通知owner？本题只有首次owned-action事件，不虚构外部协议方法。

### Part 5 取代谱系（目标12分钟）

坑：
- eligible为verified且未retired；任一eligible沿历史边传递抑制全部祖先。
- 新control退休时只激活正确fallback，未验证replacement不能压掉已有control。
- 历史中间节点退休不切断覆盖链，product/workbench按不同impact返回；没有匹配也保留空结果。

graph helper迭代验证一般finite DAG、身份与cycle，1100链护栏不要求考生写递归验证器。边代表显式覆盖关系，完整传递政策是本题确定合同。

看什么：区分eligible、suppressed和effective，不能只看直接前驱或按奇偶层交替激活。

提示：“Which eligible control still covers this old ancestor?”

追问：退役后的恢复是否足够安全？真实系统还需保留哪条证明/兼容性/部署路径？

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 调试与效率 | 25 | 元数据、双轨、review lifetime |
| 精确持久化 | 15 | 全局revision、重复观察与双轨历史 |
| 退役判断 | 25 | trigger与证据/批准分离 |
| 在线边界 | 20 | 累积证据快照、全部action、取消 |
| 谱系与沟通 | 15 | 传递覆盖和fallback |

记录具体证据、提示次数与用时，未观察到写“未观察”。允许等价实现。
