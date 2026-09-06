"""
Tests for Hybrid Search (M3): ranking + search_memories 双通道融合
"""
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.fts_index as fts
import core.ranking as rk
from app.config import settings
from models.sql_models import init_db, get_thread_session, reset_engine, Memory


@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    os.makedirs("./data", exist_ok=True)
    for p in ("./data/test_sunchat.db", "./data/test_chroma"):
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.remove(p)
    reset_engine()
    init_db()
    fts.init_fts()
    yield


@pytest.fixture
def service():
    from services.memory_service import memory_service
    session = get_thread_session()
    session.query(Memory).delete()
    session.commit()
    memory_service.chroma_client.reset()
    yield memory_service


class TestRanking:
    def test_rrf_merge_basic(self):
        merged = rk.rrf_merge([["b", "a", "c"], ["b", "d", "a"]], k=60)
        scores = dict(merged)
        # b 双榜首; a(第2+第3) > c(仅第3)
        assert [m for m, _ in merged][0] == "b"
        assert scores["b"] > scores["a"] > scores["c"]

    def test_rrf_stable_for_empty(self):
        assert rk.rrf_merge([[], ["x"]]) == [("x", 1 / 61)]

    def test_final_score_ordering(self):
        w = {"alpha": 0.7, "beta": 0.15, "gamma": 0.1, "delta": 0.05}
        hi = rk.final_score(0.9, 8, 1, 5, w)
        lo = rk.final_score(0.5, 3, 200, 0, w)
        assert hi > lo

    def test_decay_bounds(self):
        assert rk.time_decay(0) == 1.0
        assert 0 < rk.time_decay(90) < 1
        assert rk.time_decay(90) > rk.time_decay(365)

    def test_access_capped(self):
        w = {"alpha": 0.0, "beta": 0.0, "gamma": 0.0, "delta": 1.0}
        assert rk.final_score(0, 0, 0, 50, w) == rk.final_score(0, 0, 0, 10, w) == 1.0

    def test_parse_weights_default_on_garbage(self):
        assert rk.parse_weights("bad") == {"alpha": 0.7, "beta": 0.15, "gamma": 0.1, "delta": 0.05}
        w = rk.parse_weights("0.5,0.2,0.2,0.1")
        assert w == {"alpha": 0.5, "beta": 0.2, "gamma": 0.2, "delta": 0.1}


class TestHybridSearch:
    def test_keyword_only_hit_via_fts(self, service):
        # 向量(哈希伪嵌入)召不回的内容, FTS 通道能找回
        service.create_memory(user_id=41, content="用户查询过股票代码600519贵州茅台",
                              importance=7, confidence=0.9)
        hits = service.search_memories(user_id=41, query="600519", top_k=5)
        assert any("600519" in h["content"] for h in hits)
        hit = next(h for h in hits if "600519" in h["content"])
        assert "fts" in hit["channels"]

    def test_vector_and_fts_channels_marked(self, service):
        m = service.create_memory(user_id=42, content="用户住在杭州西湖区",
                                  importance=6, confidence=0.9)
        hits = service.search_memories(user_id=42, query="用户住在杭州西湖区", top_k=5)
        assert hits
        assert hits[0]["memory_id"] == m["id"]
        assert "vector" in hits[0]["channels"]

    def test_user_isolation(self, service):
        service.create_memory(user_id=43, content="别人用户的秘密咖啡偏好", importance=6,
                              confidence=0.9)
        assert service.search_memories(user_id=44, query="咖啡", top_k=5) == []

    def test_soft_deleted_not_returned(self, service):
        m = service.create_memory(user_id=45, content="用户曾经喜欢柠檬茶", importance=6,
                                  confidence=0.9)
        assert service.search_memories(user_id=45, query="柠檬茶", top_k=5)
        service.delete_memory(m["id"])
        assert service.search_memories(user_id=45, query="柠檬茶", top_k=5) == []

    def test_access_feedback(self, service):
        service.create_memory(user_id=46, content="用户每天跑步五公里", importance=6,
                              confidence=0.9)
        service.search_memories(user_id=46, query="跑步", top_k=5)
        row = service.db.query(Memory).filter_by(user_id=46).first()
        assert row.access_count >= 1

    def test_feedback_disabled(self, service, monkeypatch):
        monkeypatch.setattr(settings, "MEMORY_ACCESS_FEEDBACK", False)
        service.create_memory(user_id=47, content="用户爱吃苹果派", importance=6,
                              confidence=0.9)
        service.search_memories(user_id=47, query="苹果派", top_k=5)
        row = service.db.query(Memory).filter_by(user_id=47).first()
        assert row.access_count == 0

    def test_vector_failure_falls_back_to_fts_sqlite(self, service, monkeypatch):
        service.create_memory(user_id=48, content="用户养了鹦鹉阿绿", importance=8,
                              confidence=0.9)
        from core import embedding as emb
        def boom(*a, **k):
            raise RuntimeError("vector down")
        monkeypatch.setattr(emb.embedding_service, "embed", boom)
        hits = service.search_memories(user_id=48, query="鹦鹉", top_k=5)
        # FTS 通道不依赖嵌入, 应能找回
        assert any("鹦鹉" in h["content"] for h in hits)

    def test_both_channels_down_sqlite_fallback(self, service, monkeypatch):
        service.create_memory(user_id=49, content="用户习惯早上六点半起床", importance=9,
                              confidence=0.9)
        from core import embedding as emb
        def boom(*a, **k):
            raise RuntimeError("vector down")
        monkeypatch.setattr(emb.embedding_service, "embed", boom)
        monkeypatch.setattr(fts, "FTS_AVAILABLE", False)
        hits = service.search_memories(user_id=49, query="zzz不存在词zzz", top_k=5)
        assert any("起床" in h["content"] for h in hits)  # importance 回退仍工作

    def test_by_analysis_uses_user_input(self, service, monkeypatch):
        # FR-4: 原文进查询, keywords 辅助
        captured = {}
        orig = service.search_memories
        def spy(**kw):
            captured.update(kw)
            return orig(**kw)
        monkeypatch.setattr(service, "search_memories", spy)
        service.create_memory(user_id=50, content="用户叫王大锤", importance=10,
                              confidence=0.9)
        analysis = {"user_input": "我叫什么名字", "query_keywords": ["名字"]}
        results = service.search_memories_by_analysis(50, analysis, top_k=3)
        assert captured.get("query") == "我叫什么名字"
        assert captured.get("keywords") == ["名字"]
