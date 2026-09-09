# R-001 执行计划

需求: R-001 | 状态: draft | 日期: 2026-09-08
说明: 迁移遗留(代码先于流程,见 D-003),实现主体已在 commit 9166897e;
本计划 = 剩余改动(step-1)+ 逐 AC 校验(步骤 2–4,验证既有实现并补测试缺口)。

## 步骤表
| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | `_to_cities` 去除 IP 定位回退(D-004):未识别城市返回 `[]`;`get_weather_context` 空列表→None 不发请求;更新对应单测 | weather-core | R-001/requirements.md;R-001/modules/weather-core.md | `core/weather.py` 修改 + `tests/test_weather.py` 断言改 `== []`;验证: `pytest tests/test_weather.py -q` 全绿 | R-2,R-4 |
| 2 | AC-1/2 校验:天气识别与解析契约(含失败回退 None) | weather-core | requirements.md AC 节;modules/weather-core.md;step-1 产出 | 测试证据入 plan 总结;验证: `pytest tests/test_weather.py::TestWeatherDetect tests/test_weather.py::TestWeatherFetch -q` | R-2,R-3 |
| 3 | AC-3 校验:工具注册+execute_tool 执行(依赖 R-002 修复) | chat-direct-weather | modules/chat-direct-weather.md;R-001/decisions.md | 验证: `pytest tests/test_weather.py::TestAgentTool -q` | R-4 |
| 4 | AC-4 实机抽查 + AC-5 全量回归 | 集成 | plan.md;state.json | curl `/chat/stream` 天气问句:sources 含 wttr-in 引用实时数字;`pytest tests/ -q` 全绿;摘要入 plan 总结 | R-1,R-4 |

## 豁免声明
无豁免步骤(全部含可执行验证)。

## 自检
- 顺序 1→2→3→4 无环;清单无全仓浏览;高危 R-4 对应"逐 AC 校验+全量单测"步骤 2–4。
