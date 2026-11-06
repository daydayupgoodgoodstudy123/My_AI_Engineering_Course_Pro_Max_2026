# 参考答案讲解：Outcomes（14/47）

计时后再看。参考实现在 `outcomes/`，`python3 -m pytest --solution --all-parts` 应显示 5 passed。

## Part 1 结果框架

decision 的结论漏掉解决方案，是 _names_output 没采用提供的有限 aliases，经过 validate 两层后才看到。修好后拒绝空白边界项，再把技术理由与该技术绑定；别处有一个理由不代表所有技术都固定了。

兼容表是不可变快照，在创建时建立名称索引，每个 constraint 查自己的 reason。慢版每条扫整表，6000×18000 规模约 0.438–0.449 秒；参考约 0.892–0.962 毫秒，0.05 秒限值留足余量。固定技术可以写进 constraints；只有 desired_outcome 接受 proposed-output 扫描。

## Part 2 修订史

保存 parent 与完整 frame 的 JSON，以整份 UTF-8 bytes 的 sha256 为对象名。父链接也是内容，同样 frame 但父不同就是不同修订。load 重建 Frame/Constraint，history 从所指版本沿 parent 回走。未知 parent 先报错；每次 load 从存下的字节重建独立对象。

## Part 3 泄漏词典

tokens 已给出有限归一词与原文 offsets。每个位置找最长的完整 token 模式，同长按 id，然后从原 token 的开始/结束取 span。不是 substring；一处长模式也不能被前面的短模式抢先。有限 plural map 不外推通用英语词形学，原字符位置包括连字符和非 ASCII 前缀。

## Part 4 编辑流

私有深拷贝 frame，初始校验只作 baseline。每消费一个 Edit 都加序号，按字段更新并重新校验，交给正确 _delta 得到删除/新增，再一次 yield 完整块；没有变化不发但序号仍占用。不读取未来编辑来凑批次，也不修改调用者对象。

## Part 5 结果分解

沿先序携带最近 user、allowed-value 约束和 ancestor non-goals。每层复制约束集合，子层允许新增或收窄，禁止扩大。排除项按稳定 id 判定；孩子继承不污染兄弟，输出为独立排序的 tuple 表示。

## 这套题证明了什么，没证明什么

通过说明能把本课结果框架、固定约束和非目标写成服务，保留可追溯修订，做有界词典检测与在线修订视图，以及显式边界继承。它不证明理解任意需求、不证明技术理由真实充分，也不进行通用自然语言因果或约束推理。真实产品问题、兼容性证据和是否选择某个输出仍需调查与判断。
