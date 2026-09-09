# sunchat 需求

需求: R-001 | 类型: feature | 基于: 无(预流程记忆检索优化为其上下文)
状态: confirmed v1 | 日期: 2026-09-08

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| v1 | 2026-09-08 | 初稿(补记已实现功能) | - |

## 背景
用户询问天气时走 DDG 网页搜索,摘要不含可靠实时数据且 DDG 常被限流
(日志 `search.brave.com` 请求失败),导致"查不到天气"。需引入免 Key 免费天气数据源,
让天气类问题直接返回结构化实时数据。[RUN: backend/logs/sunchat_20260908.log 搜索失败记录]

## 与历史需求的关系
- 无(初代需求;对话搜索接入为预流程 sunchat-opt/S4 的既有能力,本需求仅插入天气前置分支,
  不修改其接口)

## 目标用户
SunChat 个人助理用户(本地单用户/少量用户)

## 核心场景
- 作为用户,我问"今天北京天气怎么样",助手直接给出实时气温/湿度/风力/今日最高最低,
  并注明数据来源,且能结合记忆给出个性化建议。
- 作为 Agent 调用方,LLM 在 function-calling 中可自主选择 get_weather(city) 获取天气。
- 作为用户,当天气源不可用时,助手不应报错卡死,而是回退普通搜索。

## 功能点
| 编号 | 描述 | 优先级 |
|---|---|---|
| FR-1 | 天气意图识别:关键词表(天气/气温/温度/下雨/下雪/带伞/降温/空气质量/weather) | P1 |
| FR-2 | wttr.in 实时直查:中文城市映射(41 城)+英文城市透传;未识别到城市不做 IP 定位,视为未命中回退搜索(D-004);解析为中文结构化文本,未收录描述词透传英文原文(D-005) | P1 |
| FR-3 | 对话路径接入:命中天气且取到数据 → 注入 system_prompt + sources[0]=wttr-in,跳过 DDG | P1 |
| FR-4 | Agent 工具注册 get_weather(city),LLM 可 function-call | P1 |
| FR-5 | 失败优雅回退:识别不到城市/网络失败/HTTP 错误 → 返回 None,对话回退普通搜索不报错 | P1 |

## 边界与非目标
- 明确包含:当前天气+今日最高最低;免 Key 单数据源 wttr.in;超时 10s
- 明确不做:逐小时/多日预报、灾害推送、历史天气;不做需注册 Key 的付费源(和风/OpenWeather)
  — 用户已选"最便宜"(2026-09-08)

## 验收标准
| 编号 | 标准(可验证) | 验证方式 |
|---|---|---|
| AC-1 | is_weather_query 命中天气问法、不误命中普通问法 | `pytest tests/test_weather.py::TestWeatherDetect` |
| AC-2 | get_weather_context 返回含气温/湿度/今日高低的格式化文本;非天气不发网络请求;失败返回 None | `pytest tests/test_weather.py::TestWeatherFetch`(mock 网络) |
| AC-3 | get_weather 已注册进 Agent 注册表,execute_tool 可执行且 user_id 不泄漏进参数 | `pytest tests/test_weather.py::TestAgentTool` |
| AC-4 | 实机:`/chat/stream` 问"今天北京天气怎么样",响应 sources 含 wttr-in,回答引用实时数字 | curl SSE 抽查 |
| AC-5 | 全量回归不破坏既有功能 | `pytest tests/` 全绿 |

## 决策记录
- [D-001] 2026-09-08 数据源选 wttr.in 免费免 Key;理由:用户要求最便宜方案,个人用量免费额度内;放弃和风/OpenWeather(需 Key/注册)
- [D-002] 2026-09-08 对话路径天气直查命中后跳过 DDG;理由:更快更准,避免双通道浪费
- [D-003] 2026-09-08 未收录天气描述词透传英文原文,交 LLM 归纳翻译;放弃补全 ~50 词翻译表(维护成本高仍会漏)
- [D-004] 2026-09-08 未识别到城市不做 IP 定位(wttr.in 服务端定位会误报服务器城市),视为未命中回退 DDG,LLM 可依上下文反问城市;需同步修改 _to_cities 现状(返回 [""] 走 IP 定位)
- [D-005] 2026-09-08 直查失败回退 DDG 普通搜索(现状保留)
