"""
SunChat Backend - Ranking (M3)
RRF 融合 + 业务重排: final = α·相似度 + β·importance/10 + γ·时间衰减 + δ·访问反馈。
"""
import math
from typing import Dict, List, Tuple

from app.config import settings


def parse_weights(raw: str = None) -> Dict[str, float]:
    """解析 config 权重串 "0.7,0.15,0.1,0.05" → {alpha,beta,gamma,delta}。"""
    raw = settings.MEMORY_RANK_WEIGHTS if raw is None else raw
    try:
        a, b, g, d = (float(x) for x in raw.split(","))
        return {"alpha": a, "beta": b, "gamma": g, "delta": d}
    except (ValueError, AttributeError):
        return {"alpha": 0.7, "beta": 0.15, "gamma": 0.1, "delta": 0.05}


def rrf_merge(lists: List[List[str]], k: int = 60) -> List[Tuple[str, float]]:
    """Reciprocal Rank Fusion: 各通道 id 列表 → [(id, rrf_score)] 降序。"""
    scores: Dict[str, float] = {}
    for lst in lists:
        for rank, item in enumerate(lst):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def time_decay(age_days: float, tau: float = 90.0) -> float:
    """指数衰减 exp(-age_days/tau);从未访问过也不额外惩罚(R-4)。"""
    if age_days <= 0:
        return 1.0
    return math.exp(-age_days / max(tau, 1e-6))


def final_score(sim: float, importance: int, age_days: float,
                access_count: int, w: Dict[str, float] = None) -> float:
    w = parse_weights() if w is None else w
    acc = min(max(access_count, 0), 10) / 10.0
    return (w["alpha"] * max(sim, 0.0)
            + w["beta"] * min(max(importance, 0), 10) / 10.0
            + w["gamma"] * time_decay(age_days)
            + w["delta"] * acc)
