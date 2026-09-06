"""
Tests for FTS Index (M2)
真实 SQLite FTS5(本地引擎,非外部服务,不 mock)。
"""
import os
import sys
import shutil

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.fts_index as fts
from models.sql_models import init_db, get_thread_session, reset_engine, Memory

@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    """隔离测试库（覆盖 conftest autouse 后自己钉死环境变量与库, 避免打生产库）。"""
    from unittest import mock
    import importlib
    import app.config
    with mock.patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./data/test_sunchat_fts.db",
    }):
        importlib.reload(app.config)
        os.makedirs("./data", exist_ok=True)
        if os.path.exists("./data/test_sunchat_fts.db"):
            os.remove("./data/test_sunchat_fts.db")
        reset_engine()
        fts.FTS_AVAILABLE = True
        init_db()
        assert fts.init_fts() is True
        yield
    if os.path.exists("./data/test_sunchat_fts.db"):
        os.remove("./data/test_sunchat_fts.db")


@pytest.fixture
def fresh_db():
    db = get_thread_session()
    db.query(Memory).delete()
    db.commit()
    fts.fts_bootstrap_from_sqlite()
    yield db
    db.query(Memory).delete()
    db.commit()
    fts.fts_bootstrap_from_sqlite()


def _add(db, mid, user_id, content):
    m = Memory(id=mid, user_id=user_id, type="semantic", category="general",
               content=content, confidence=0.9, importance=7)
    db.add(m)
    db.commit()
    fts.fts_sync_upsert(mid, content)
    return m


class TestTokenize:
    def test_cjk_unigram_bigram(self):
        toks = fts.tokenize("用户叫张三").split()
        assert "用" in toks and "户叫" in toks and "张三" in toks

    def test_ascii_lower(self):
        assert "python" in fts.tokenize("User likes Python").split()

    def test_empty(self):
        assert fts.tokenize(None) == "" and fts.tokenize("") == ""


class TestSearch:
    def test_keyword_hit(self, fresh_db):
        _add(fresh_db, "u_f1", 11, "用户上周去了上海出差")
        _add(fresh_db, "u_f2", 11, "用户喜欢喝咖啡")
        hits = fts.fts_search("去上海出差", 11, n=5)
        assert hits and hits[0][0] == "u_f1"

    def test_user_isolation(self, fresh_db):
        _add(fresh_db, "u_f1", 11, "用户喜欢喝咖啡")
        _add(fresh_db, "u_f2", 22, "另一个用户喜欢喝咖啡")
        ids = [i for i, _ in fts.fts_search("喝咖啡", 11, n=5)]
        assert "u_f1" in ids and "u_f2" not in ids

    def test_soft_deleted_excluded(self, fresh_db):
        m = _add(fresh_db, "u_f1", 11, "用户习惯每晚11点睡觉")
        assert fts.fts_search("睡觉", 11)
        m.is_active = False
        fresh_db.commit()
        fts.fts_sync_delete("u_f1")
        assert fts.fts_search("睡觉", 11) == []

    def test_ascii_number(self, fresh_db):
        _add(fresh_db, "u_f1", 11, "用户查询过股票代码600519的股价")
        assert [i for i, _ in fts.fts_search("600519", 11)] == ["u_f1"]

    def test_empty_query(self, fresh_db):
        assert fts.fts_search("", 11) == []
        assert fts.fts_search("   ", 11) == []

    def test_quote_injection_safe(self, fresh_db):
        _add(fresh_db, "u_f1", 11, '用户 quotes 测试 特殊字符')
        fts.fts_search('引号"破坏', 11)  # 不抛异常即可


class TestSyncAndBootstrap:
    def test_upsert_twice_replaces(self, fresh_db):
        _add(fresh_db, "u_f1", 11, "用户喜欢篮球")
        mem = fresh_db.query(Memory).filter_by(id="u_f1").first()
        mem.content = "用户喜欢足球"
        fresh_db.commit()
        fts.fts_sync_upsert("u_f1", "用户喜欢足球")
        hit_foot = fts.fts_search("足球", 11)
        assert [i for i, _ in hit_foot] == ["u_f1"]
        # 单字索引: "篮球" 仅共享单字"球", 只可能以极低分出现, 不得高分召回
        hit_bask = fts.fts_search("篮球", 11)
        assert all(s < 0.1 for _, s in hit_bask)

    def test_bootstrap_from_sqlite(self, fresh_db):
        _add(fresh_db, "u_f1", 11, "用户养了一只猫")
        _add(fresh_db, "u_f2", 11, "用户会弹吉他")
        n = fts.fts_bootstrap_from_sqlite()
        assert n >= 2
        assert {i for i, _ in fts.fts_search("猫 吉他", 11)} == {"u_f1", "u_f2"}

    def test_fts_unavailable_returns_empty(self, fresh_db, monkeypatch):
        monkeypatch.setattr(fts, "FTS_AVAILABLE", False)
        assert fts.fts_search("猫", 11) == []
        assert fts.fts_sync_upsert("u_f1", "x") is False
        assert fts.fts_sync_delete("u_f1") is False
        assert fts.fts_bootstrap_from_sqlite() == 0
