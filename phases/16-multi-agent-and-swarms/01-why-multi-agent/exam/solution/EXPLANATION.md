# SplitCase 参考讲解

## Part 1

specialist_input按recipient取messages，private notes按owner过滤。正确make_view保留原顺序，required_fact_value按声明key读取，所以误投递会在正确消费者自然KeyError。sum_branch_usage累加每个独立call而非保留末branch。record_call_usage保留完整request，用Python len(system)+len(user)的声明估计，不制造仅为计长度的临时拼接串。同一完整压力请求已在六个独立完整副本中连续实测3慢3快，两侧余量23.53×/22.90×，六次全五关通过；只证明这个本地fixture的实现差异。

## Part 2

Snapshot包含原task、FixedDesign、reported usage和float metadata。asdict只转结构，不把int变float；JSON保留原文本与list顺序，正确restore重新形成typed records。相同recipient或timestamp不代表同一条消息，首尾空白与空正文也不能trim或丢弃。缺失usage None和0无需归一。存完整snapshot，不能只存渲染summary。它是本地格式，无事务/崩溃承诺。

## Part 3

prepare_design真实复用P1输入投影与usage。role_peak_context按每role max(input+output)，总用量仍按独立calls相加。boundary_fact_losses只核显式required id是否forward，保留boundary和role。compare_fixed_design先报告两侧用量/peaks/超限/loss，再按声明的可行性和token规则得prefer_multi；不优化数量，不把低cost变事实正确性。

## Part 4

同步stage_row保留当前stage身份，取自己的input/output/status，并经修好的P3单boundary helper得到required omissions。JSON字符串只是CSV字段，wire由DictReader定义。correct driver负责一次header、逐stage发布和关闭，candidate不实现async调度。

## Part 5

递归每branch使用自己的shared tuple和notes tuple，再由P1 helper投影到leaf role。full路径标识同名leaf，返回child顺序的可见和缺失id，不能按局部leaf名全局去重。空scope包含零个leaf，所以返回零行。跨branch不能复用已污染祖先容器。事实id由fixture声明，不从自然语言推断。

## 这套题证明了什么，没证明什么

它核对显式消息/私有输入、完整JSON设计、fixed context/loss/use ledger、阶段数据和nested scopes。没有真实LLM、独立采样、语义fact验证、agent数量最优化、Amdahl计算、真实tokenizer/价格/并行速度收益或人类60分钟难度证据。
