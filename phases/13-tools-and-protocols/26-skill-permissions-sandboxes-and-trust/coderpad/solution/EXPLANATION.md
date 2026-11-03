# 参考解释：执行前权限策略

仅在计时结束后阅读。参考实现是满足本题简化合同的一种实现，不是生产 SDK。

授权条件是独立层，不让批准绕过 capability 或路径范围。argv 使用精确比较，代码从不执行候选动作。

## 复盘顺序

1. 将自己失败的 case 映射到 PROMPT 的具体规则，先判断是理解还是实现遗漏。
2. 查看 [main.py](main.py) 中对应函数，解释校验、外部调用和状态变化的顺序。
3. 关闭答案，自己修复 starter；补一个边界测试，再跑核心和全量测试。
4. 回答下面追问，明确本地 fake 测试的证据边界。

- 为什么有 approval 仍可能被 capability policy 拒绝？
- policy allow 与真实 sandbox containment 有何区别？

```bash
python3 run_tests.py --solution
```

这条命令在 `coderpad/` 目录运行，选择独立参考实现，不覆盖学员代码。
测试覆盖只针对 PROMPT 合同；协议、身份、网络、跨 host 或真实部署均需独立集成证据。
