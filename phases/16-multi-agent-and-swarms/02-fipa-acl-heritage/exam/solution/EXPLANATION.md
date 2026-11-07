# SpeechAct 参考讲解

## Part 1

tools/call保持request，resources/read保持query-ref和URI language。正确consumer按声明意图找reply obligation或按language读取raw URI；不访问URI。render_acl用给定quoted primitive处理每个字段，encode_acl输出完整UTF8 bytes；接收方parse_envelope实际消费并恢复完整message。逐字符immutable bytes累积会复制增长prefix；完整text编码保留完全相同wire。相同完整压力fixture已连续实测3慢3快，两侧余量11.93×/37.40×，六次全五关通过；首探索组的超慢数据保留，只对本地fixture作结论。

## Part 2

candidate构造全部envelope字段，只在optional值为None时省略；content使用给定typed tag。给定append frame/I/O负责真实UTF8 byte length和关闭；重开逐record恢复原message，保留append顺序、原标签和typed payload。binary64/int codec是GIVEN护栏，不需要重造数值表示。identity含前后空白也是原文；typed empty根值须经tag恢复，不能按truthiness改写。同一handle的read仍要重新读已有journal，不能缓存过期rows。没有事务/并发/损坏修复承诺。

## Part 3

recognize_conversations按完整(protocol,conversation_id)找到局部state，request/subscription调用各自advance。前者核原requester/responder与声明stage，后者核subscriber/publisher、notification计数及named cancel；最终按首次出现顺序报告剩余obligation。content即使有ok:false也不能重写inform的speech act。terminal拒绝后续act，reply双方都要匹配，active subscription也不接受重复subscribe。这个toy automaton明确没有多轮同key复用或in-reply-to，不能当完整FIPA实现。

## Part 4

ACLFramer保留parts/depth/quoted/escaped。quote内的括号只是数据，反斜杠只影响紧邻字符；状态跨feed保存。depth回零输出独立完整envelope，finish拒绝未闭合。只忽略记录间whitespace；其他非opening字符拒绝。正确GIVEN driver负责UTF8、async发布与关闭，测试中的parser决定有限wire格式。

## Part 5

给定TokenCursor只做词法。递归read遇opening list逐child读取到相应closing，bare token构成Atom、quoted token构成Quoted；整个输入只允许一个root。render按节点类型递归并保持child顺序，empty list与Quoted("")输出不同语法。重复siblings保留其次数，numeric-looking Atom保留原字符串，不做数值归一化。无eval、ontology推理或SL真值判断。

## 这套题证明了什么，没证明什么

核对局部intent/language、完整codec与journal、声明义务状态、ACL成帧和typed内容树。原source只有renderer和打印demo，decoder、journal、automata和syntax tree是诚实披露的教学适配。没有真实工具/LLM/网络、URI访问、完整FIPA/SL/MCP/A2A兼容性、模型质量或真人60分钟难度证据。
