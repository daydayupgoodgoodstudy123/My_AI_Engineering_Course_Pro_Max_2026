# SpeechAct 面试官手册（16/02）

计时期间不给候选人看。开场2分钟，五关12/11/15/10/10，共60；没有真人校准。卡住约5分钟时一次只给一级提示，记录英文提示和实际行为。

## 澄清合同

|关|问题|英文回答|
|---|---|---|
|1|这里真请求工具或URI吗？|"No. These are supplied local fixtures. A URI stays an opaque reference."|
|1|要实现FIPA/SL标准吗？|"No. Each envelope field is a JSON-quoted string. The finite parser and payload tags are supplied."|
|2|空optional等于没有吗？|"No. None is absent and an empty string is present data. Preserve the original labels."|
|3|同一conversation能重开请求吗？|"No. One interaction belongs to each exact protocol and conversation-id pair."|
|3|不agree就inform合法吗？|"Yes in this local request automaton. Failure requires agreed; refuse requires pending."|
|4|UTF8和async要自己写吗？|"No. Implement text-domain framing. Decoding, publication and closure are supplied."|
|5|83是不是数字？|"It is an Atom with the exact text 83. Quoted text and lists are different node types."|

## Part 1 意图、语言与wire

四层：tools/call被误投影为inform，正确reply_obligation没有为它建立reply entry，经SpeechService.require_tool_reply自然KeyError；raw URI被标成JSON，经forward_resource_read→consume_language_payload→json.loads自然JSONDecodeError；renderer直接拼引号，正确receiver parser在producer外拒绝字段；完整rendered ACL逐字符累积immutable bytes造成真实prefix复制成本。

首两层都是源内performative/language字段，不吞consumer错误、不伪造obligation或访问URI。quoted renderer保留全部metadata与正文；empty-content/present-empty字段由正确helper给定且是防过修护栏。性能只测完整SpeechService.roundtrip，包含renderer、完整UTF8输出、正确接收方parse和完整消息/byte输出断言。10000段人工content压力fixture的完整连续3slow3fast实测：slow1.216073/1.212533/1.193201秒，fast0.002449/0.002674/0.002451秒，limit0.1秒，两侧余量11.93×/37.40×。六个完整副本各全五关通过，最长wall1.407秒；超慢的首探索组保留在题包外维护证据。H1 "Which action does this envelope express?" H2 "How does the receiver read the declared language?" H3 指向intent、quoted fields与完整wire。

## Part 2 完整追加journal

主要看可选metadata的存在性、原conversation label与完整envelope/content记录、追加顺序。None不写入可选字段，空字符串必须写；001和1不归并。language是原label，journal不因它改变opaque payload。正确tag codec保留int/binary64/typed empty，正确binary frame/I/O给定，精度与UTF8 byte length是整合护栏。candidate仍需构造完整领域record并重开恢复，不是存展示文本或每次覆盖。identity前后空白不可trim；typed empty根值不可用truthiness改成展示文本；同一journal handle再次read应看见后续append。无任意损坏恢复/并发/crash-atomic承诺。H1 "Which optional value was actually present?" H2 "Did this append preserve earlier messages?" H3 指向完整record。

## Part 3 局部义务自动机

主要看按(protocol,conversation_id)隔离会话并绑定原交互双方；request的pending/agreed/refused/done/failed阶段、与payload形状无关的performative；subscription在inform后仍active、只由其subscriber的named cancel结束。request允许pending直接inform，failure只能agreed，refuse只能pending；terminal后不再接新act；reply的receiver也必须是原requester，active subscribe不能以重复opening无声重开。这是明确toy合同，不声称完整FIPA语义或源码已含该自动机。P1单条翻译/消费和P2重开只作为依赖，三个advance/recognize函数全部独立TODO。H1 "Which interaction owns this act?" H2 "What obligation remains after agreement or notification?" H3 指向key、stage与participants。

## Part 4 ACL成帧

主要看quoted parentheses不是closing delimiter、escape/quote状态跨feed保存、真正闭合时返回每个独立envelope以及EOF未闭合拒绝。GIVEN async driver负责逐chunk拉取、完成记录发布和source关闭；GIVEN incremental UTF8 decoder负责码点切块，不能把这些算candidate通用collect-all或UTF8主坑。测试用正确local parse_envelope消费输出，限定wire语法；记录间只能出现whitespace，非opening字符不能静默丢弃。H1 "Was this closing parenthesis quoted?" H2 "Which escape state survives the chunk boundary?" H3 指向domain framer。

## Part 5 typed内容树

主要看list嵌套/child顺序、Atom与Quoted区分、empty list与empty quoted text区分及单root完整性、重复siblings与numeric-looking Atom原文。正确lexer和quoted primitive给定，candidate写真正递归parse/render，不做eval或SL逻辑解释。外层ACL只是携带内容字符串，不因内容括号改变performative；真实复用P1/P2/P3。H1 "Which node type did the quotes establish?" H2 "Does this list contain zero children or one empty string?" H3 指向typed tree。

## 评分记录

五关各8分推进、调试20、代码15、沟通15、工程判断10，仅是原创练习评分。具体记录断言、提示、未观察事项；不能从本地结果推断真实协议兼容性或multi-agent质量。
