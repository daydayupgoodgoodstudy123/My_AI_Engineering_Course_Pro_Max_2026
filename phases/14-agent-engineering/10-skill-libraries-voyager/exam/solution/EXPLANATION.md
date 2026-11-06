# 参考答案讲解：Voyager（14/10）

计时结束后再看。参考实现在同目录的 `voyager/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修技能库

**第一个现象**：按标签 `gather` 搜索时 gather_sticks 不见了，原因却不在 `search`。打印 `lib.get("gather_sticks").tags` 会看到 `('g', 'a', 't', 'h', 'e', 'r')`：`register` 里的 `tuple(tags)` 把字符串拆成了字母。docstring 说 tags 可以是一个标签，所以字符串要包成一元组：`(tags,) if isinstance(tags, str) else tuple(tags)`。

**第二个现象**：钉在 `mine_ore@1` 的 starter_kit 失败了，`failed` 写的是 `mine_ore@1`，堆栈却指向 `<skill mine_ore v2>` 那一行源码。顺着往上找：`execute` 跑的是 `_plan` 给的技能，`_plan` 用 `get("mine_ore", 1)` 取版本，`get` 用 `dataclasses.replace` 从当前对象拼出一个“v1”，只换了代码和版本号，`fn`、依赖、描述还是 v2 的。根因在 `register`：同名时它原地改写旧对象，旧的 `fn` 就丢了，`_history` 里只剩代码字符串。这是课里的 composed-skill drift：父技能钉在 v1，跑的却是 v2。

修法是让每个版本都是一个独立、不再修改的 `Skill`：`register` 每次新建一个对象，追加到 `self._versions[name]`，`get(name, v)` 直接取第 v 个。参考实现把 `Skill` 设成了 frozen，原地修改直接报错。修好以后要顺手确认 `search` 只看每个技能的最新版本，否则同一个技能的 v1、v2 会一起出现。

**第三个现象**：失败的运行把世界改脏了。`execute` 在循环前 `copy.deepcopy(world)`，失败时 `world.clear(); world.update(before)`。三个细节：

- 必须是深拷贝。技能改的是 `world["resources"]` 这个嵌套 dict，浅拷贝的快照和世界共用它。
- 必须原地还原。在函数里写 `world = before` 只改了局部变量，调用方手里的 dict 没变。
- 先 `clear` 再 `update`。失败前 place_table 加了 `has_table` 这个新键，只 `update` 删不掉它。

log 不回滚：它记录的是失败前跑完了什么，Part 4 的改进循环要靠它和堆栈。

**第四个现象**：计时断言。5 万个技能的库里按标签检索 30 次，要 1.3 秒左右，限值 0.03 秒。`search` 先给全库每个技能算 Jaccard，最后才按标签筛：带 kit007 的只有 50 个，却打了 5 万次分。类的 docstring 写着 register 要维护一份“标签→技能名”的索引，起始代码只存了描述的分词。修法分两处：

```python
# register：先从上一版的标签下摘掉，再挂到这一版的标签下
if version > 1:
    for tag in self._versions[name][-1].tags:
        self._tagged[tag].discard(name)
for tag in tags:
    self._tagged.setdefault(tag, set()).add(name)

# search：有标签时只给索引里的名字打分
names = self._versions if tag_filter is None else self._tagged.get(tag_filter, ())
```

修好以后约 1 毫秒。这就是课里 retrieval quality 那一条：库过了几百个技能，按描述相似度检索就靠不住了，要先用标签和硬约束把范围缩小，再去排序。只把标签判断挪到打分前面（课里代码就是这个顺序）不够，每次检索还是要把 5 万个技能过一遍，约 0.1–0.2 秒。

几个细节：

- 索引跟着最新版本走。精炼时去掉的标签要摘掉，新加的要挂上。测试把 mine_iron_tools_7007 从 kit007 挪到了 kit999。
- 索引里存名字，检索时再取最新版本。存 Skill 对象的话，标签没变的技能精炼以后还会返回旧版本；用列表、每次注册都追加，会出重复。
- 没有技能带的标签返回空列表，所以用 `.get(tag_filter, ())`。直接 `self._tagged["g"]` 会报 KeyError。
- 集合的遍历顺序不固定，并列按名字排全靠排序键 `(-score, name)`。kit007 里有 11 个技能并列 1/3 分。
- 先编译、再改索引。代码编译不过时 register 直接报错，索引不受影响。
- 分词放在 register 里，起始代码已经这样做了，所以检索时不用每次重新切分描述。精炼时要换成新描述的分词，测试会搜 v2 才有的 "two at a time"。

**`_plan` 的护栏**：`_plan` 没有预埋缺陷。它就是课里 `topo_order` 那样带已访问集合的遍历，只是写成了递归，兄弟依赖按书写顺序访问。测试保留了它的几道护栏，防止修别处时顺手改坏：

- 每条依赖都重算整棵闭包、不记忆化：梯子图上每个技能依赖下一层的两个技能，18 层要调用约 79 万次，约 0.8 秒，限值 0.05 秒。参考实现约 0.02 毫秒。
- 已访问要按（名字，版本）记，不能按名字记：stock_up 同时需要 gather_sticks v1 和 v2，按名字记会吞掉 v2。
- 课里那种显式栈的后序遍历会把兄弟依赖的顺序反过来。
- `done` 每次调用 `_plan` 都新建，不要把计划缓存在库上跨调用复用：裸名字指的是执行那一刻的最新版，测试先跑一次 starter_kit 再精炼 gather_sticks，缓存的旧计划会接着跑 v1。草稿的版本号都是 0，跨调用缓存到 Part 4 还会让不同的草稿共用一份计划。

**钉住版本的护栏**：只有写成 `name@v` 的引用是钉住的。把依赖全冻结在 v1，或者注册时把裸名字换成当时的版本号，gather_sticks 就停在 v1，还是在制造课里说的那种漂移，只是方向反了。

## Part 2 内容寻址存储

布局在 docstring 里：`objects/<sha256>` 放代码，`manifest.json` 按名字列出每个版本的哈希、描述、标签和依赖。参考实现：

- `save`：对每个版本算 `sha256(code.encode("utf-8"))`，对象不存在才写（先写临时文件再 `os.replace`），清单整份重写。
- `load`：读清单，对每个版本 `read_bytes()`，重新算哈希和文件名比对，再 `decode("utf-8")`、`compile_skill`，tags 和 depends_on 转回 tuple。

容易漏的几点：

- **字节进字节出**。文本模式默认开着通用换行，`\r\n` 读进来变成 `\n`。行尾空格、制表符、文件末尾没有换行，都要原样保留。
- **哈希只算代码**。把版本号、描述一起哈希，mine_ore v1 和 v3（回退到同一份代码）就不能共用对象了。反过来，对象去重不等于版本去重：v3 照样要在清单里。
- **读的时候校验**。名字就是内容的哈希，读回来对不上就说明文件坏了或被改过。测试把一个 5 换成 7，长度不变，只有真的算哈希才查得出来。缺文件和坏文件都报 StoreError，并点名 `mine_ore@2`，这样运维知道是哪个技能坏了。
- **再保存一次**。已有对象不重写，`open(path, "xb")` 不先判断会撞上 FileExistsError。清单是整份替换：第二次保存的库里已经没有 craft_pickaxe，读回来也不能有，追加、按名字合并、按版本合并都会把它留下。对象不删，craft_pickaxe 的代码对象照样留在 `objects/` 里；清理没人引用的对象是另一件事。

参考实现还检查清单里的哈希是不是 64 位十六进制，防止清单把路径指到 `objects/` 外面去。

## Part 3 课程提议

对每个候选任务做一次带“已访问”集合的遍历：

```python
missing, todo = set(), [task]
while todo:
    skill = todo.pop()
    if skill in have or skill in missing:
        continue
    missing.add(skill)
    if skill in recipes:
        todo.extend(recipes[skill].requires)
```

- 从任务自己开始，所以任务自己算缺。只缺自己，就是课里说的“略高于当前能力”。
- 遇到库里已有的技能就停：会做 craft_planks 就不用再学 chop_wood。
- 没有配方的前置（collect_coal）也算缺，只是不再往下找。
- 用集合天然去重：craft_bucket 经两条路径都需要 craft_furnace，只算一次。

`short` 只看任务自己的配方：`need - inventory.get(item, 0)`，大于 0 才写进去。排序键是 `(缺的技能数, 有没有缺材料, -价值, 任务名)`。“有没有缺材料”是个布尔值：课里说课程要同时看环境状态和技能清单，材料已经齐的任务马上就能做。缺几件、缺几种都不是这个条件，测试数据专门让这两种写法排错。

## Part 4 迭代改进流

骨架是一个 async generator，主体是课里的五步循环：

```python
start = copy.deepcopy(world)
learned = False
try:
    for n in range(1, max_rounds + 1):
        draft = await writer(task, feedback)
        reset(world, start)                      # 每轮从同一个起点开始
        try:
            run = lib.execute(lib.draft(task.name, draft.code, draft.depends_on), world)
        except Exception:                        # 编译不过
            signal, detail = "error", traceback.format_exc()
        else:
            ...                                  # run.error，或者 task.verify(world)
        learned = signal == "success"
        feedback = {"round": n, "signal": signal, "version": version, "detail": detail}
        yield json.dumps(feedback) + "\n"
        if learned:
            return
finally:
    if not learned:
        reset(world, start)
```

- **三种信号**：编译不过和技能抛异常都是 error，detail 是完整堆栈，模型改代码时靠它定位到行；跑完但验证没过是 self_verification_failure，detail 是验证给的理由。第 3 轮的草稿返回 “skipped” 而不是抛异常，没有错误，但也没有造出镐。课里那份代码就把这种情况当成了成功，第三种信号就是为它准备的。
- **只有成功的入库**：先在 `lib.draft` 上试，成功了才 `register`。版本号由库分配，这里是 2。
- **每轮重置**：`reset` 是 `world.clear(); world.update(copy.deepcopy(start))`。每次都要重新深拷贝，否则下一轮会直接改到快照里的嵌套 dict。不重置的话，第 3 轮留下的木棍会让第 4 轮漏了 gather_sticks 的草稿“成功”，入库的技能拿到新世界就跑不起来。`clear` 也不能省：第 3 轮的草稿往世界里写了 `waiting_for`，只 `update` 的话它会一直留到成功之后。
- **finally**：消费方读完一行就 `aclose()` 时，生成器在 yield 处收到 GeneratorExit，循环后面的代码不会执行。复原放在 finally 里，成功时不复原。`learned` 在 yield 之前就设好：消费方读到成功那一行就关闭时，GeneratorExit 也是在那个 yield 处抛出的，这时世界要留着成功的结果。
- **流式**：每轮先 yield 再问下一份草稿，所以探针读到第一行时写手只被调用了一次。`json.dumps` 会把堆栈里的换行转义掉，保证一个事件一行。

## Part 5 版本锁定

两遍：

1. 按字面走整棵树：`name@v` 指向 v，裸名字指向最新版，按（名字，版本）记已访问。每遇到一个钉就记下版本和第一次出现的路径；同一个技能出现两个不同的钉，就用两条路径报 VersionConflict。
2. 每个技能锁定为它的钉，没有钉就取最新版；再按锁定的版本做一次深度优先遍历，依赖按书写顺序、每个技能一次，后序输出。

第一遍不能按名字记已访问：craft_rails 先经 mine_iron 走到裸名字的 craft_stone_pickaxe（v2），后面才遇到 `craft_stone_pickaxe@1`，v1 里面的两个钉也要收集到。第二遍要按锁定版本的依赖往下走：craft_sticks 锁在 v1 时没有 strip_bark，mine_stone 锁在 v1 时没有 place_torch。

这个语义的边界在 docstring 里写明了：钉是从“字面的树”里读的，一个只出现在最后没被选中的版本下面的钉也算数，测试没有覆盖这种情况。要做到“只算最终闭包里的钉”，可以按名字的拓扑序先定父技能、再定子技能，或者反复迭代到钉不再变化。这已经是一般的依赖求解问题，npm、pip 的解析器都为此做了取舍。

## 这套题证明了什么，没证明什么

通过了说明你能在一个技能库里顺着堆栈追到“版本被原地改写”这类组合漂移，能把失败的执行回滚干净，能在库变大以后用跟着版本走的标签索引先缩小范围、再检索；能设计一个逐字节还原、能自检的内容寻址存储；能把课程模块“还缺什么”的判断写成确定的算法；能写一个分清三种信号、不让伪成功入库、可以随时断开的流式改进循环；也能在依赖树上做带冲突报告的版本锁定。它不涉及真正让模型写代码，也不涉及嵌入向量检索（课里练习 3）、在真实环境里运行生成代码要的沙箱，以及 Claude Agent SDK 技能的打包格式（练习 5）。这些需要接上真实模型和运行环境另外去做。
