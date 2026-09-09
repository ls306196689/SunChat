# 模块: weather-core

状态: draft r1 | 日期: 2026-09-08 | 触发: R-001/FR-1,2,5

## 对外接口
```python
def is_weather_query(query: str) -> bool
    # 命中天气关键词表返回 True(天气/气温/温度/下雨/下雪/要带伞/降温/供暖/空气质量/weather)

def get_weather_context(query: str) -> Optional[str]
    # 非天气问法 → None(不发网络请求)
    # 命中 → "【城市 当前天气】…" 多行文本(天气/气温体感/湿度风速/能见度紫外线/今日高低)
    # 城市识别不到、wttr.in 失败/超时/解析异常 → None(调用方自行回退)

# 内部(不对外,单测可及)
def _to_cities(query: str) -> List[str]   # 中文映射→英文名,按出现顺序;英文专有名词正则兜底;
                                          # 去重保序截 3;未识别 → [](不回退 IP 定位,D-004)
```
数据: wttr.in `GET https://wttr.in/<city>?format=j1`,Header `curl/8.0`(wttr 对浏览器
UA 返回 HTML 行为更常见),超时 10s。解析字段契约:
`current_condition[0]{temp_C,FeelsLikeC,humidity,windspeedKmph,visibility,uvIndex,weatherDesc[0].value}`,
`nearest_area[0]{areaName[0].value,region[0].value}`,`weather[0]{maxtempC,mintempC}`。

## 能力说明
- 提供: 天气意图识别、中英文城市识别(内置 41 中国城市映射)、实时天气象化为中文文本。
- 不提供: 逐小时/多日预报、地理坐标查询、缓存、IP 定位(D-004 明确不做:
  wttr.in 空路径按服务端出口 IP 定位,会误报服务器所在城市而非用户城市)。

## 内部关键逻辑
- 描述中文化:内置常见描述映射表(Sunny→晴等 ~10 条),未收录透传英文原文,
  交对话 LLM 归纳时翻译(C1/D-003)。
- 城市顺序:按中文城市在原句出现位置排序,保证"上海和北京"顺序稳定。
- 失败语义:任何异常(HTTP 非 200、网络、JSON、解析)捕获记日志后返回 None,
  绝不抛出——保证调用方回退路径无条件可达(FR-5)。

## 依赖
| 模块 | 使用的接口名 | 其文档 |
|---|---|---|
| utils.logger | logger | (既有基线) |
| requests | requests.get | 第三方 |
