# 参考答案讲解：Ratchet（14/54）

计时后再看。参考在ratchet/，`python3 -m pytest --solution --all-parts`应5 passed。

## Part 1 成套owned action

按(track,destination)取同一元数据行的artifact和verification，保留每个显式impact。review从注入的promoted_on起算，正确归并、router和owner资格不改。日期一次加timedelta，不逐日循环；6000个普通180天窗口慢0.124–0.129秒，快1.579–1.630毫秒，限值0.014秒，普通60/90天日期同样保留。

## Part 2 全局修订与完整历史

物理CSV由正确给定的read_rows/append_row处理，真实文件newline=''、JSON sources tuple和priority int重建都不需要候选人重写；CRLF/Unicode精确往返是codec护栏。

Ledger每次读取现有物理记录，以整份entries长度加一选新revision。相同Action再append也有新序号，不能按artifact、id、track或值相等合并。entries完整返回所有记录；history只按artifact精确筛选，保留旧全局revision、重复Action，以及同artifact不同product/workbench控件。读取时重开文件，所以已有Ledger也看到另一个handle新追加的记录。

## Part 3 先review再有依据retire

正确helper先给证据资格。算法记录架构变化、replacement、quiet完整存续窗、误拦更多与due理由。只有批准加有效replacement或完整观察的quiet window才retire；否则有理由review，无理由keep。起点recurrence仍在window内，blocked==prevented不算更多。

## Part 4 信号到owned-action事件

正确MergeBook返回累计Signal，用其priority和全部impacts生成Action，再给正确gate按完整身份claim。逐个立刻yield完整snapshot字符串；不因一个cause已提升而停止其他cause，未来归并不回写过去的packet。

## Part 5 传递抑制

先用迭代schema helper检查lineage。所有eligible控制的predecessor加入待处理栈，沿历史边求抑制并集；effective=eligible-suppressed。即使中间节点退休，仍继续沿其历史边。请求的fingerprint/track分别返回排序id，没有control也保留空tuple。C退休才回到B，不把A也同时复活。

## 这套题证明了什么，没证明什么

通过说明能把确定反馈转成有owner/证明/review的动作，保存历史、依证据复审，在线保留多源与双轨影响，并求给定覆盖关系下的fallback。它不证明真实因果、invariant真实性、部署兼容或自动删除安全；真实退役仍需证据和责任人判断。
