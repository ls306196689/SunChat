"""
SunChat Backend - Weather Service
天气直查：DDG 摘要拿不到可靠实时天气，天气类问题直接调 wttr.in 拿结构化数据喂给 LLM。

数据源：wttr.in（免 Key、免费，JSON 接口 j1）。识别不到城市或请求失败 → 返回 None，
调用方回退普通搜索。
"""
import re
from typing import Dict, List, Optional
from urllib.parse import quote

import requests

from utils.logger import logger

_HEADERS = {"User-Agent": "curl/8.0"}
_TIMEOUT = 10

_WEATHER_KEYWORDS = ["天气", "气温", "温度", "下雨", "下雪", "要带伞", "降温",
                     "供暖", "空气质量", "weather"]

# 中文城市 → 英文（wttr.in 对英文名解析更准；未命中直接原样传，中文亦可解析）
CITY_MAP = {
    "北京": "Beijing", "上海": "Shanghai", "广州": "Guangzhou",
    "深圳": "Shenzhen", "杭州": "Hangzhou", "南京": "Nanjing",
    "成都": "Chengdu", "重庆": "Chongqing", "武汉": "Wuhan",
    "西安": "Xi'an", "天津": "Tianjin", "苏州": "Suzhou",
    "长沙": "Changsha", "郑州": "Zhengzhou", "青岛": "Qingdao",
    "大连": "Dalian", "厦门": "Xiamen", "福州": "Fuzhou",
    "哈尔滨": "Harbin", "沈阳": "Shenyang", "济南": "Jinan",
    "合肥": "Hefei", "昆明": "Kunming", "贵阳": "Guiyang",
    "兰州": "Lanzhou", "乌鲁木齐": "Urumqi", "拉萨": "Lhasa",
    "西宁": "Xining", "银川": "Yinchuan", "呼和浩特": "Hohhot",
    "海口": "Haikou", "南宁": "Nanning", "石家庄": "Shijiazhuang",
    "太原": "Taiyuan", "长春": "Changchun", "南昌": "Nanchang",
    "香港": "Hong Kong", "澳门": "Macau", "台北": "Taipei",
}

_DESC_ZH = {
    "Sunny": "晴", "Clear": "晴", "Partly cloudy": "多云",
    "Cloudy": "阴", "Overcast": "阴", "Mist": "薄雾", "Fog": "雾",
    "Patchy rain possible": "可能有雨", "Patchy snow possible": "可能有雪",
    "Thundery outbreaks possible": "可能有雷暴",
    "Smoky haze": "烟霾", "Haze": "霾", "Moderate or heavy rain shower": "阵雨",
}


def is_weather_query(query: str) -> bool:
    return any(k in query for k in _WEATHER_KEYWORDS)


def _to_cities(query: str) -> List[str]:
    """从问题提取城市（英文名或中文映射），去重保序。"""
    cities: List[str] = []
    hits = []
    for zh, en in CITY_MAP.items():
        pos = query.find(zh)
        if pos >= 0:
            hits.append((pos, en))
    rest = query
    for zh in CITY_MAP:
        rest = rest.replace(zh, "")
    for _, en in sorted(hits):
        cities.append(en)
    for word in re.findall(r"(?<![A-Za-z])([A-Z][a-z]{2,})(?![a-z])", rest):
        if word not in {"Today", "Tomorrow", "Weather"}:
            cities.append(word)
    if not cities:
        # 未识别到城市：可能是"今天天气怎么样"，用 IP 定位（wttr.in 空路径）
        cities.append("")
    return list(dict.fromkeys(cities))[:3]


def _desc_en(text: str) -> str:
    return _DESC_ZH.get(text.strip(), text.strip())


def _format_city(city: str, data: Dict) -> Optional[str]:
    try:
        cur = data["current_condition"][0]
        area = data.get("nearest_area", [{}])[0]
        name = (area.get("areaName") or [{}])[0].get("value", city or "当前位置")
        region = (area.get("region") or [{}])[0].get("value", "")
        if region and region != name:
            name = f"{name}({region})"
        today = data.get("weather", [{}])[0]
        lines = [
            f"【{name} 当前天气】",
            f"天气: {_desc_en(cur['weatherDesc'][0]['value'])}",
            f"气温: {cur['temp_C']}°C（体感 {cur['FeelsLikeC']}°C）",
            f"湿度: {cur['humidity']}%，风速: {cur['windspeedKmph']} km/h",
            f"能见度: {cur['visibility']} km，紫外线指数: {cur['uvIndex']}",
        ]
        if today:
            lines.append(
                f"今日: 最高 {today.get('maxtempC')}°C / 最低 {today.get('mintempC')}°C")
        return "\n".join(lines)
    except (KeyError, IndexError, TypeError) as e:
        logger.debug(f"[WEATHER] 字段解析失败 {city}: {e}")
        return None


def get_weather_context(query: str) -> Optional[str]:
    """天气类问题 → 给 LLM 的天气上下文文本；非天气/取不到 → None。"""
    if not is_weather_query(query):
        return None
    parts: List[str] = []
    for city in _to_cities(query):
        try:
            resp = requests.get(f"https://wttr.in/{quote(city)}?format=j1",
                                headers=_HEADERS, timeout=_TIMEOUT)
            if resp.status_code != 200:
                logger.warning(f"[WEATHER] wttr.in HTTP {resp.status_code} city={city}")
                continue
            text = _format_city(city, resp.json())
            if text:
                parts.append(text)
        except Exception as e:
            logger.warning(f"[WEATHER] wttr.in 请求失败 city={city}: {e}")
    return "\n\n".join(parts) if parts else None
