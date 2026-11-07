# 参考答案讲解：OutboxFlow（16/22）

独立作答结束后再读。参考实现展示声明的有限本地合同；本文的算法解释不构成运行或通过证据。

## 来源与本地合同

四canonical来源为本课docs/en.md、code/main.py、code/main.讲解.md和英文scaling-advisor输出。英文output只作为课程DATA阅读，没有执行其中的工作流。

source main22–48已正确按thread过滤、用INTEGER step取latest；P1缺run与lexical排序是明确的本地回归。source的list.pop(0)是真实队首成本；其三态队列自动RESPONSE→IDLE，没有显式ack。本题增加匹配UID的ack屏障和单独的batch drain adapter。

outbox、有效一次、rainbow与两层协调由docs94–108、158–161及讲解287–305支持为练习或概念。source main并未实现独立receiver、send/ack恢复、version event replay或nested admin树。本题是这些内容的显式local adapter；source的同进程counter demo和async/thread打印不作为本题证明。

旧coderpad只提供priority job排序与单次调用内canonical-JSON重放。本题逐record持久映射、caller事务组合、独立receiver与重开恢复是当前实际合同。

## Given边界

- `models.py`给类型；`db_support.py`给exact Decimal/tuple/container codec、Rows资源、atomic事务与immutable同key replay判别。它不替候选选择domain key或序列化三个业务模型。
- `execution_support.py`给合法有限StepPlan绑定、one-shot CrashCut和独立SQLite AtomicReceiver。receiver以稳定key把effect/result/receipt一起持久化；匹配重发返回原receipt，冲突拒绝。它不提交sender pair或恢复pending。
- `service.py`给正确的required-state consumer与完整batch report消费；`fixture.py`在timer外生成独立expected。
- `wire_support.py`给event-kind intake、CSV header/quoting与async writer，不给run bindings或active状态算法。
- `group_support.py`完整给full UID及(group,localname)lookup、owner paths、own-message绑定、origin分类与独立mailboxes。`deliver_audit`递归消费candidate的accepted/current-run RouteAudit再投递，不判route或exports。候选仍须实现真实admin路径与nested报告。

## Part 1：选择、ack与完整FIFO

`latest(run)`先保留该run记录，再按原Python int step取最大；空集合返回None。数值9/10不能用字符串key排序，任意大int护栏也排除float捷径。首个foreign checkpoint通过 `resume_checkpoint → read_required_state` 暴露，正确consumer无须吞异常。

AgentQueue在idle只进入processing；processing才出队并绑定实际Envelope为response；response分支保持原response，直到acknowledge验证相同UID。错误ack不改变状态；正确ack清空response并回idle，再开始下一条。

BurstMailbox使用deque的append/popleft，完整drain把实际出队结果按顺序组成tuple。QueueDesk随后消费全部delivered来算run_counts与signed amount。反复list.pop(0)对一个长度Q的burst产生累计移动成本；deque改变队首成本而保留完整输出。这里batch adapter不等于逐条运行并发三态agent。

当前配置150000条，timer包含QueueDesk真实执行与完整BurstReport equality，expected在外；0.10秒门限已有完整本机校准记录，实际观测见下文及SCOPE.json；该记录不构成跨机器耗时上界。

## Part 2：三个业务record的事务感知投影

checkpoint以(run,step)为key，值保留run、step、原version和完整state。intent以其完整key保存run、step、effect、amount、destination、payload。receipt以原key保存key、实际receiver、amount和result；读回按各自model重建，保留写入次序。

pending先取得已acknowledged的完整key集合，再选该run尚未匹配receipt的intent。不能用destination代替effect、用current runtime代替原version，或过滤状态中的opaque字段。

所有write只调用Rows.put，不自行commit；caller的atomic scope决定一起提交或回滚。immutable相同重放和冲突判别由完整Given负责。任意大step在Given JSON/TEXT codec中保留原int，Decimal的coefficient和scale也由Given精确保存；候选负责原样领域字段关联，不实现新的precision conversion算法。

## Part 3：三个真正的执行TODO

`commit_checkpoint_and_intent`在一个archive.atomic中写checkpoint和intent。after_checkpoint位于两次写之间，before_commit位于两次写之后但事务尚未离开；两者异常都回滚。after_commit必须在context外，异常发生时pair已经持久化。函数不产生receiver效果。

`dispatch_intents`先读取P2正确给定的 `transaction_open` 资源状态，sender事务仍打开时抛出ValueError且不调用receiver；避免同连接看到尚未commit的intent就产生独立效果。之后读取该run实际pending；每个intent原样调用receiver.deliver，after_send在接收真实receipt之后触发，随后在sender atomic里acknowledge该receipt。receiver已commit而sender ack未写时，下一次仍使用原(run,step,effect)key；Given receiver返回同一durable receipt，effective effect不增加。不能在本地fabricate看似相同的receipt，也不能改delivery key。

`recover_outbox`先发送已committed pending，即使latest已terminal；再用P1从P2记录选该run numeric latest，按声明的已绑定plans继续更大step。每个新plan先commit再dispatch，最后返回该run实际checkpoint、intents和receipts。

| cut | sender状态 | receiver状态 | 恢复动作 |
|---|---|---|---|
| after_checkpoint | pair事务回滚 | 无效果 | 重做未提交plan |
| before_commit | pair事务回滚 | 无效果 | 重做未提交plan |
| after_commit | checkpoint+intent已在，尚无ack | 尚未送达 | 先发送pending |
| after_send | pair已在，sender receipt可为空 | effect+receipt已独立提交 | 原key重发取原receipt，再ack |

P2是逐record投影；P3是跨record原子组合、独立发送及状态恢复，三项均由candidate执行。sender与receiver是两个SQLite资源，保证来自明确receiver幂等合同，不来自一个覆盖外部效果的sender事务。

## Part 4：按实际binding发布CSV

project_deployment保存bindings与active。start写入声明version并置active；resume和failed_resume只读原binding；finish读原version后从active移除，但保留binding。deploy/retire使用事件version。

每行按其实际version统计active runs；retire_allowed仅在retire事件且该count为零时为True。Given writer按返回row顺序生成完整CSV，test用独立csv.DictReader解析。这里的new-start choice由fixture声明，不是线上随机canary或真实runtime部署。

## Part 5：LCA、逐上行export与recursive current-run outputs

expected_route消费完整Given source/destination owner paths。同group不同endpoint返回(source,destination)，同endpoint自投递只返回(source,)；跨group求最长共同前缀，上行收集source group直到共同group的admins，再下行收集共同group下一层到destination group的admins。首尾加入真实source/destination，去掉相邻重复endpoint。只列最深source与共同admin会漏中间边界。

audit_deployment为所有声明message构造RouteAudit。完整Given的origin_valid提供origin原因；声明hops与expected route不同产生admin-route。对source path每个前缀，如果destination不在该group子树内，message UID必须在这一group exports；每个缺失边界各记undeclared-export。有效hops不自动授予export权限。

随后按真实tree递归：own对应本group声明message的route audits；children保留声明顺序与完整祖先path。每group outputs按其exports顺序选message：请求run相同、route accepted、source在该子树内且destination在其外。local、inbound、其他run与无效route都不能冒作此group的outbound输出；root也不会因子group有输出就自动输出。

Given deliver_audit根据candidate own/children的accepted/current-run结果投递到已绑定mailbox。完整同名resolver、mailbox binding和admin/leaf origin分类无须重写；候选主要工作是LCA admin ladder、每个crossed export与recursive报告。最终测试把P1实际Envelope经P3receiver、P2close/reopen后的receipt payload变成Message，再消费候选audit到mailbox。

## 当前验证状态

<!-- VALIDATION_STATUS_BEGIN -->
当前42个PY文件、五测试、47条assert、5处pytest.raises、五锁与25个登记错误写法。原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定TEMP检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部25项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能与正式检查按各自证据范围解释。

P1真实负载150000条immutable Envelope输入；完整QueueDesk.drain_burst与whole BurstReport equality（全部ordered UID/run/amount/body、各run counts与signed amount）都在timer内，fixture与独立expected在外。batch adapter返回完整入站数据，不等于逐条运行并发三态agent；单条ack状态另有行为护栏。

完整校准三个慢样本[1.2884170829784125, 1.3393366250675172, 1.353035124950111]秒，三个快样本[0.008853374980390072, 0.008932374883443117, 0.009660790907219052]秒；限值0.10秒，慢侧／快侧余量12.884171／10.351119。六份测量副本只将timingassert改为elapsed打印，慢版另恢复真实list队首移除；完整五关功能均通过，不表示慢版通过原时间阈值。原样参考另有完整五关通过记录。墙钟观测受环境影响，不构成跨机器SLA；60分钟未经真人校准。
<!-- VALIDATION_STATUS_END -->

当前领域覆盖包括相同numeric step的跨run独立checkpoint、sender未提交事务的dispatch拒绝、RecoveryReport own-run receipts、failed resume的active状态，以及各group完整route observations与输出source-subtree归属。

## 这套题证明了什么，没证明什么

当前材料能表达有限、单线程、声明输入下的checkpoint/intent/receipt、局部异常恢复、版本绑定与嵌套route合同。只有实际执行并保存证据后，才能描述相应本地检查结果；本说明不补写未发生的runtime或验收事实。

这里没有真实LLM、网络服务、多进程故障、并发worker、lease、fencing或production durability测试。独立receiver的effect与receipt原子存储是完整Given前提；不能将这一有限有效一次语义外推为任意外部API的distributed exactly-once。课程打印的async/thread时间或内存说法也不构成本题性能证明。
