# M5 eval

状态: draft r1 | 2026-09-06

## 1. 对外接口
```python
# backend/scripts/eval_memory.py(新文件; golden set: backend/scripts/data/memory_golden.json)
命令行:
  python scripts/eval_memory.py --label before|after [--topk 3] [--user 99]
  # --user 评测专用 user_id(默认99, 与日常 user 1 隔离, 跑前清空该 user)
golden set 条目:
  {"id": "g01", "category": "person", "setup": ["用户叫张三", ...],   # 先经 API 写入的记忆
   "query": "我叫什么", "expect_memory_ids_match": ["张三"],  # 内容包含判定词
   "forbid_in_topk": ["股价"]}  # 可选: 注入这些视为噪声
输出(stdout JSON + 写 data/eval_report_<label>.json):
  {"label":..., "n":30, "hit@1":0.53, "hit@3":0.80,
   "irrelevant_injection_rate":0.07, "per_case":[...], "model":"bge-m3"}
```

## 2. 能力说明
- 提供:可复现的相对指标对比(改造前 git 工作区基线跑一次 before,改造后跑 after)。
- 不提供:CI 集成(依赖实机 Ollama)、绝对达标线判定(R-6:只作相对对比)。

## 3. 内部关键逻辑
- 写入 setup 记忆走 HTTP `POST /api/v1/memories`(真实双写路径),轮询 Chroma count 稳定后再查(`--wait-embed 3s`)。
- hit@k:query 走 `POST /api/v1/memories/search`,top-k 结果 content 含期望词记 hit;`hit@1` 单列。
- 无关节注入率 = 有 forbid 命中的 case / 含 forbid 的 case。
- 评测 user 隔离:user=99 避免污染真实检索与统计;`--cleanup` 结束删该 user 全部记忆(DELETE API 直连 DB by user)。
- 6 类(person/preference/event/knowledge/relationship/habit)各 ≥4 条,共 ≥30;含 3 条"专有名词/数字"用例验证 FTS 通道、2 条"时间新旧优先"用例验证衰减。

## 4. 依赖
- M3(经 HTTP search 接口间接);`app.api.v1.routes.memories` CRUD(现有)
- 实机:Ollama + bge-m3(已装,模型经用户确认 D-001)
