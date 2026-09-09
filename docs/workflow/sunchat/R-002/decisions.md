# R-002 决策日志

- [D-001] 2026-09-08 修复位置选在 execute_tool 运行时做签名探测(inspect.signature),而非要求每个工具加 **kwargs 或统一签名;理由:改动面最小、防越权语义不变、对既有 wrapped 函数安全(inspect 穿透 __wrapped__)。
