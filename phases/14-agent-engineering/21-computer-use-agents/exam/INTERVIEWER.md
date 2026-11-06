# 面试官手册：ComputerUse（14/21）

候选人计时期间不要看。候选人手里只有 README、`computeruse/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 没有真实的模型和屏幕：`FakeDesktop` 是虚拟显示器的替身，动作序列和 `model` 函数由测试写好。主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 点进一个敏感的输入框（卡号、密码）要不要确认？ | "No. Focusing a field is harmless. Typing into it is what needs a yes." |
| 1 | 确认期间屏幕重画了，但按钮还在原处，要不要取消？ | "No. Run it. Abort only when the element under the point is not the one we asked about." |
| 1 | 中止的步骤要不要重试？ | "No. Record it as aborted and move on." |
| 2 | 截图能不能 base64 后直接放进 run 文件？ | "No. Screenshots live in objects/. The run file only names them." |
| 2 | 要不要压缩或者转格式？ | "No. Store the exact bytes you were given." |
| 2 | 没人引用的截图要不要清理？ | "Out of scope today." |
| 2 | 写文件要不要原子化？ | "Your call. Say what you chose. The test checks that a torn file gets repaired." |
| 3 | `*.example.com` 包不包括 `example.com` 本身？ | "No. List it separately if you want it." |
| 3 | 重定向怎么处理？ | "Out of scope. We check the URL the agent asks for, and the href of a link it clicks." |
| 3 | 端口要不要比？ | "No. Only the host counts." |
| 3 | 人拒绝以后，agent 过一会儿再试呢？ | "Not on that page. A no stands for the rest of the session." |
| 3 | 人同意过一次，同一个按钮再点还要问吗？ | "Yes. A yes covers one action." |
| 4 | 模型思考的时间算在哪一步？ | "In none of them. ms is the step itself, from the capture to the end of the action." |
| 4 | 需要确认的动作在无人值守时怎么办？ | "Hold it. Log it and don't run it." |
| 4 | 分类器自己抛异常呢？ | "Not in scope. Only the desktop fails in these tests." |
| 4 | error 那一行的 reason 要不要带异常类型名？ | "No. Just the message, str(exc)." |
| 4 | ms 是四舍五入还是向下取整？ | "Round down." |
| 5 | 有没有 z-index？ | "No. Paint order only: later siblings are on top." |
| 5 | 坐标换算怎么取整？ | "Take the centre of the screen span the screenshot pixel covers, then round down." |

## 每关：要看什么、提示、追问

### Part 1 修 agent 循环（目标 13 分钟）

一个测试里叠了 4 个缺陷和 1 个性能问题：

1. `run_agent` 在循环外只取了一次 `desktop.screen()`。`FakeDesktop` 每次界面变化都换一个新的 `Screen` 快照，所以点了链接以后，分类器还在用首页判断。报错的位置不在 `agent.py`：trace 里第 2 步是 `blocked: no element at (60, 75)`，第 3 步是 `nothing is focused`，这两句话都出自 `safety.py`，而那里没有 bug。
2. `SafetyClassifier.assess` 的 type 分支没有检查焦点所在的输入框是否敏感，往卡号框里打字不需要确认。docstring 写明了要确认。
3. 人工确认以后，`run_agent` 直接按坐标点击，没有再看一眼那个位置现在是不是刚才问过的元素。测试在确认期间弹出一个盖住按钮的 promo 弹窗，点击就落到了弹窗上；按钮消失的情况下，`desktop.click` 返回 None，`el.label` 报 AttributeError。打字的情况同理：确认期间焦点换了，就不能再打。
4. `Screen.element_at` 用的是闭区间 `x <= el.x + el.w`，共享一条边的两个元素会同时包含这条边上的像素，右边和下边外面那一个像素也算在元素里。docstring 写的是半开区间。
5. `element_at` 每次都线性扫描全部元素。76,800 个单元格、约 2,000 次命中测试，本机实测 1.2 到 3 秒（负载 5 到 24，10 核），限值 0.1 秒。参考答案按 32 像素分桶，约 2 毫秒；64 像素约 4 毫秒，128 像素约 10 毫秒，256 像素约 26 毫秒，都能过。512 像素的桶要 86 到 90 毫秒，贴着限值，机器忙的时候会偶尔超时，遇到了请候选人把桶调小。

护栏：
- 确认期间界面重画了一次（新的 `Screen` 对象，按钮位置不变），点击照常执行。用“屏幕对象变了就中止”来修第 3 条，会在这里挂掉。
- 确认以后重新按坐标取元素、点到什么算什么，会在 promo 弹窗那里挂掉。拿确认之前的那个 `screen` 去核对也一样，旧屏幕上按钮还在。
- 确认以后把动作再交给分类器判一遍、只要还允许就执行，点击的几种情况能过，打字那一步会挂：焦点换到了搜索框，往搜索框打字照样允许。只核对“有没有焦点”也是同样的结果。
- 第 2 条只给打字加确认。点进敏感输入框本身也要确认的话，测试数到 3 次提问（应该是 2 次：往卡号框打字一次，点购买一次）。
- 分桶以后仍然要返回最上层的元素，边界仍然是半开区间。桶里按绘制顺序正着找、只把元素放进左上角所在的桶，都会挂。

看什么：是不是先读 trace 的实际内容，再问“分类器看到的是哪一屏”；有没有顺着 `desktop.click` 去看它怎么换屏；每改一处就重跑。

提示：
- H1："The classifier says there is nothing at (60, 75). What does the screen at that moment look like?"
- H2："Where does run_agent get the screen it hands to assess?"
- H3：直接指出 `screen = desktop.screen()` 在循环外面。

追问：
- "Why does the classifier block every action when the DOM carries a marker, instead of just the typed text?"（截图和 DOM 都是不可信输入，只有用户的直接指令才算授权；页面里的指令可能诱导任何一种动作）
- "The confirmation takes 30 seconds. What else can change on the screen, and what should the agent do?"（弹窗、重排、跳转；按元素而不是按坐标确认，执行前再核对一次）
- "How would you hit test against a real screenshot with no element list?"（课里说 Claude 不用 accessibility API，只看像素；安全层要么拿到结构化的页面信息，要么自己做元素定位）

### Part 2 截图外部存储（目标 11 分钟）

坑：
- `put` 要先核对已经存在的同名文件，两头都要顾到。内容正确就直接返回，不能重写：测试把这个文件的 mtime 改成 2001 年，再存一次后检查 mtime 没变，每次都用临时文件加 `os.replace` 重写会在这里挂。内容不对就要换掉：测试预先放了一个崩溃留下的同名文件，长度正好，100 字节以后全是零（文件长度已经记下、数据还没写到盘上就断电，会留下这样的文件）。只看“文件存在”或者“长度对”就跳过，这个文件会一直留着，读的时候报 CorruptFrame。
- run 文件里只放步骤记录和摘要，不放图像数据。测试限制 run 文件小于 2,000 字节，而一张截图就有 16 KB。同一个 run_id 再存一次要整份替换，追加到旧记录后面会读回 6 条。
- 读的时候要校验哈希，而且 `get` 自己就要报错：文件不存在报 MissingFrame，不能让 FileNotFoundError 漏出去；字节被改过（长度不变）报 CorruptFrame。`load_run` 再包一层，消息里写明是第几步。`get` 不管、只在 `load_run` 里补救，测试直接调 `get` 时会挂。
- 摘要必须是截图字节本身的 SHA-256，文件路径是 `objects/<前两位>/<其余 62 位>`，目录里不能留下临时文件。对 hex 文本或 base64 求哈希，路径和测试算的不一样。
- 截图是二进制，按字节读写。传进来的本来就是 bytes，一般不会在这里出错；要是解码成文本再读，通用换行会把 PNG 签名 `\x89PNG\r\n\x1a\n` 里的 `\r\n` 和末尾单独的 `\r` 都变成 `\n`，哈希就对不上了。这个签名本来就是为了发现换行转换而设计的。

测试抓不到的：用 `write_text(frame.decode("latin-1"), encoding="latin-1")` 写对象，在 macOS 和 Linux 上不转换换行，能过；在 Windows 上每个 `\n` 都会写成 `\r\n`，对象的字节就和名字对不上了。可以顺着问为什么要按字节读写。

追问：
- "Two agents write the same screenshot at the same moment. What can go wrong?"（同名临时文件冲突；临时文件名加进程号或随机后缀，`os.replace` 是原子的，内容相同谁赢都一样）
- "Screenshots of a 200-step run are mostly the same. What else could you deduplicate?"（按区块或差分存；这里按整帧去重已经能省下相同的帧）
- "How does a trace span point at a screenshot?"（课里的 Defense pattern 4：内容放外部存储，span 里只放引用；这里的摘要就是那个引用）

### Part 3 跨页面的逐步安全服务（目标 12 分钟）

坑：
- 主机名要用 `urlsplit(url).hostname` 取，它会去掉端口和 userinfo，并转成小写。`https://shop.example.com@evil.test/pay` 的主机是 `evil.test`；按 URL 前缀或者 `netloc` 比较都会放过它或者误拒带端口的地址。
- `*.example-cdn.net` 要匹配 `.example-cdn.net` 这个后缀，不能只匹配 `example-cdn.net`，否则 `badexample-cdn.net` 和裸域名都会通过。
- 检查顺序在 docstring 里，只报第一个失败的规则。页面注入排第一，类型其次，再是目标、目的地、输入文本。测试里专门有同时违反两条的动作。
- 点击一个链接也是导航，要检查它的 href；一个敏感但指向外站的链接，在 destination 这一步就拦下，不能先去问人。
- 人拒绝过的元素，在同一页面（同一个 url 和 eid）上再出现，直接拦下，不再问。先问人、再查拒绝记录，返回的结果一样，可人被问了第二次，测试数提问次数。只按 eid 记会把另一个商品页上的同名按钮也拦掉；只按页面记会把同一页上的另一个购买按钮（Buy as a gift）也拦掉。
- 人同意只算这一次。把同意也记下来，第二次购买就不问了。
- `run_session` 每一步都要给模型看当前屏幕，并对同一屏做判断，只把 allow 的动作发给桌面。测试里人拒绝了购买，最后核对桌面收到的全部事件：被拒的点击、被拦的导航都不能发出去；允许的 navigate 要调 `desktop.navigate`，去 promo 页靠的就是它，漏掉的话最后一步还在商品页上判断。

可以接受的写法：用 `fnmatch.fnmatchcase(host, entry)` 匹配条目也能过，`*.` 后面要求有一个点，效果和后缀匹配一样。

追问：
- "The page redirects from an allowed host to another one. Where would you catch it?"（在每一次真正加载的 URL 上再查一次；本题不考）
- "A human denies the same purchase three times in a row on different pages. Now what?"（升级处理，停掉会话，交给人；拒绝记录就是证据）
- "Per-step safety adds latency. How would you measure whether it is worth it?"（课里的 Exercise 5：逐步计时，和失败、拦截的次数一起看）

### Part 4 逐步轨迹（目标 13 分钟）

坑：
- 输出格式由测试里的 logfmt 解析器决定：值里有空格、`=`、引号、反斜杠或控制字符就要加引号并转义；空值要写成 `""`。导航的 URL 是 `?q=red+shoes&page=2`，没有空格，只在有空格时才加引号，里面的 `=` 会把这一对拆坏。异常消息来自远端，带 `\r\n` 和制表符：`\n` 或 `\r` 不转义会把一行拆成两行，制表符原样写进引号里解析器不认。空值写成 `element=` 解析不了。
- 被拦下的动作也要有一行，`reason` 写分类器的原因。需要确认的动作在无人值守时写 `verdict=held`，不执行。
- 每一步的行要在取下一个动作之前送出。测试会数已经从模型那里取了几个动作。先把动作全读出来，会在这里挂。
- `ms` 是这一步自己花的时间：从截屏开始到动作结束，按注入的纳秒时钟计算，整数毫秒。测试里的模型每次要“想”5 秒，从上一行算起会把这 5 秒算进去；从截屏之后才开始算，被拦下的步骤会变成 0。四舍五入还是向下取整，这里的数据分不出来（150.4 毫秒），两种都能过。
- 执行动作时抛异常，这一步写 `verdict=error`，`reason` 是 `str(exc)`，接着写 `run=failed failed_step=<n>`，然后结束，不再取下一个动作。让异常直接冒出去，最后一行就没了。
- 截图要存进 Part 2 的 store，`shot` 是摘要的前 12 位。远端每张截图上都有时钟，没有两张一样，所以被拦下和 held 的步骤的截图也要存；只给执行了的动作存，`store.get` 会报 MissingFrame。排查第 180 步时，最需要的往往就是这些截图。
- 不需要转义的值写成裸值：最后一条断言逐字比对 `run=ok steps=0`，全部加引号会挂。用 `json.dumps` 加引号的话，默认会把 `café` 写成 `caf\u00e9`，解析器不认这个转义，对不上；`ensure_ascii=False` 的 `json.dumps` 对这里的值和 docstring 的转义一致，可以接受。

追问：
- "A 200-click run fails at click 180. What do you look at first?"（第 180 行和它的截图；有了逐步轨迹才查得了）
- "The reader of this stream disconnects. What happens to the run?"（生成器被关闭，循环停在 yield 处；需要的话在 finally 里清理）
- "Why not log the full screenshot digest?"（前缀够查，行短；冲突的概率很低，需要时再用完整摘要）

### Part 5 嵌套界面树的命中测试（目标 11 分钟）

坑：
- 坐标换算：截图像素覆盖一段屏幕像素，取这段的中点再向下取整，即 `(2x + 1) * W // (2w)`。`round(x * W / w)` 会遇到银行家舍入（4.5 舍成 4），`x * W // w` 取的是左上角。
- 后绘制的兄弟节点在上面，哪怕前一个兄弟在那里有更深的子节点。把所有命中都找出来再取最深的，会把对话框下面的链接选出来。
- 不裁剪的父节点允许子节点伸出去（工具栏按钮上的角标）。只在“点在节点框里”时才往下找，会漏掉它。
- 裁剪会层层叠加：侧边栏和列表都裁剪，列表的框伸出了侧边栏上沿，伸出去的那几行不能被点到。从上往下递归、每一层先看点在不在当前的裁剪框里，交集自然就有了；把树展平成绘制顺序、每个节点只记最近一层裁剪框（列表自己的框），伸出侧边栏的行就能被点到。
- 滚动偏移逐层累加：侧边栏和列表各滚了一段，两段都要减。滚动移动的是子节点，不是节点自己的框；裁剪框也是节点自己的框，不随滚动移动。
- 不可见的节点和它的整棵子树既不接收点击，也不挡住下面的东西。
- 盒子是半开区间，右边和下边不属于它。

可以接受的写法：`to_screen` 用浮点算中点再 `int()`，这里的结果一样，参考答案用整数运算是为了避开浮点误差。把树展平、取绘制顺序里最后一个命中的节点也对，只要裁剪框取的是所有裁剪祖先的交集。

追问：
- "Claude counts pixels from reference points. Why do coordinates still need scaling?"（模型看到的截图分辨率和真实屏幕不同；课里说模型产出的是与分辨率无关的坐标，落到屏幕上还要换算）
- "The tree has 50,000 nodes. How do you make this fast?"（按子树包围盒剪枝，或者像 Part 1 那样把展平后的元素分桶）
- "A CSS transform rotates a panel. What breaks?"（盒子不再是轴对齐矩形，需要把点逆变换到节点的局部坐标）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 trace 和 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出不可信输入、确认的范围、存储一致性、可观测性 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
