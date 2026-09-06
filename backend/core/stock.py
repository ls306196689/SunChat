"""
SunChat Backend - Stock Quote Service
股票行情直查：DDG 摘要不含实时价格，股价类问题直接调行情 API 拿具体数字喂给 LLM。

数据源：腾讯行情 http://qt.gtimg.cn（纯 HTTP 轻量接口，免 Key，支持美/港/A 股）；
东方财富 push2 作备源。识别不到代码或全部失败 → 返回 None，调用方回退普通搜索。
"""
import re
import time
from typing import Dict, List, Optional

import requests

from utils.logger import logger

_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
_TIMEOUT = 8

_STOCK_SUFFIXES = ["股价", "股票", "行情", "收盘价", "开盘价", "涨了", "跌了", "市值",
                   "走势", "多少钱", "什么价"]

# 常见中文名 → 腾讯代码（中文问法不带代码时的兜底映射）
NAME_SYMBOLS = {
    "阿里巴巴": ["usBABA", "hk09988"],
    "腾讯": ["hk00700", "usTCEHY"],
    "英伟达": ["usNVDA"],
    "特斯拉": ["usTSLA"],
    "苹果": ["usAAPL"],
    "微软": ["usMSFT"],
    "谷歌": ["usGOOGL"],
    "亚马逊": ["usAMZN"],
    "Meta": ["usMETA"],
    "facebook": ["usMETA"],
    "台积电": ["usTSM"],
    "AMD": ["usAMD"],
    "贵州茅台": ["sh600519"],
    "茅台": ["sh600519"],
    "宁德时代": ["sz300750"],
    "比亚迪": ["sz002594", "hk01211"],
    "小米": ["hk01810"],
    "美团": ["hk03690"],
    "京东": ["usJD", "hk09618"],
    "百度": ["usBIDU", "hk09888"],
    "网易": ["usNTES", "hk09999"],
    "拼多多": ["usPDD"],
    "顺丰": ["sz002352"],
    "工商银行": ["sh601398"],
    "建设银行": ["sh601939"],
    "中国石油": ["sh601857"],
    "中国移动": ["sh600941", "hk00941"],
    "中芯国际": ["sh688981", "hk00981"],
    "寒武纪": ["sh688256"],
}


def is_stock_query(query: str) -> bool:
    return any(s in query for s in _STOCK_SUFFIXES)


def _to_symbols(query: str) -> List[str]:
    """从问题提取腾讯格式代码：BABA→usBABA，09988→hk09988，600519→sh600519。

    优先匹配知名公司中文名；再用正则提取裸代码/数字。
    注意：汉字也是 \w，不能用 \b 做英文边界；用"相邻不是同类字符"的显式断言。
    """
    symbols: List[str] = []
    rest = query
    for name, codes in NAME_SYMBOLS.items():
        if name and name in rest:
            symbols.extend(codes)
            rest = rest.replace(name, "")
    for code in re.findall(r"(?<![A-Za-z])([A-Za-z]{1,5})(?![A-Za-z])", rest):
        up = code.upper()
        if up in {"API", "AI", "IPO", "CEO", "CFO", "ETF", "USD", "RMB", "APP",
                  "THE", "A", "B"}:
            continue
        symbols.append(f"us{up}")
    for code in re.findall(r"(?<!\d)(\d{5,6})(?!\d)", query):
        if len(code) == 5:
            symbols.append(f"hk{code}")
        elif code[0] == "6":
            symbols.append(f"sh{code}")
        else:
            symbols.append(f"sz{code}")
    ordered = list(dict.fromkeys(symbols))
    return ordered[:4]


def _fetch_tencent(symbols: List[str]) -> List[Dict]:
    url = "http://qt.gtimg.cn/q=" + ",".join(symbols)
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.encoding = "gbk"
    quotes = []
    for line in resp.text.split(";"):
        line = line.strip()
        m = re.match(r'v_(\S+)="(.*)"', line)
        if not m or not m.group(2):
            continue
        f = m.group(2).split("~")
        if len(f) < 45 or not f[3]:
            continue
        try:
            quotes.append({
                "name": f[1], "code": f[2], "price": float(f[3]),
                "prev_close": float(f[4]) if f[4] else None,
                "open": float(f[5]) if f[5] else None,
                "time": f[30],
                "change": float(f[31]) if f[31] else 0.0,
                "pct": float(f[32]) if f[32] else 0.0,
                "high": float(f[33]) if f[33] else None,
                "low": float(f[34]) if f[34] else None,
                "market": {"us": "美股", "hk": "港股", "sh": "A股沪市",
                           "sz": "A股深市"}.get(m.group(1)[:2], "?"),
            })
        except (ValueError, IndexError) as e:
            logger.debug(f"[STOCK] 腾讯字段解析失败 {m.group(1)}: {e}")
    for q in quotes:
        q["currency"] = {"美股": "USD", "港股": "HKD",
                         "A股沪市": "CNY", "A股深市": "CNY"}.get(q["market"], "")
    return quotes


def get_stock_context(query: str) -> Optional[str]:
    """股价类问题 → 给 LLM 的行情上下文文本；非股价/识别不到/取不到 → None。"""
    if not is_stock_query(query):
        return None
    symbols = _to_symbols(query)
    if not symbols:
        return None
    try:
        quotes = _fetch_tencent(symbols)
    except Exception as e:
        logger.warning(f"[STOCK] 行情获取失败: {e}")
        return None
    if not quotes:
        return None
    lines = []
    for q in quotes:
        lines.append(
            f"{q['name']}({q['code']}, {q['market']}, {q['currency'] or ''}) "
            f"最新价 {q['price']:g}，涨跌 {q['change']:+g}（{q['pct']:+.2f}%），"
            f"今开 {q['open'] or '?'} 昨收 {q['prev_close'] or '?'} "
            f"最高 {q['high'] or '?'} 最低 {q['low'] or '?'}（行情时间 {q['time']}）"
        )
    header = "实时行情数据（腾讯行情，可直接引用给用户，这就是具体价格）："
    return header + "\n" + "\n".join(lines)
