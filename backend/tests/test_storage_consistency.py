"""
Tests for Storage Consistency (M1): reconcile / ensure_vector / rebuild / write_allowed
"""
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.storage_service as ss
from app.config import settings
from models.sql_models import init_db, get_thread_session, reset_engine, Memory


@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    """DB/Chroma 由 conftest 模块级隔离 fixture 建立; 此处仅确保表存在。"""
    from models.sql_models import init_db
    init_db()
    yield

@pytest.fixture
def db():
    session = get_thread_session()
    session.query(Memory).delete()
    session.commit()
    memory_service.chroma_client.reset()
    if os.path.exists(ss.CKPT_PATH):
        os.remove(ss.CKPT_PATH)
    yield session
    if os.path.exists(ss.CKPT_PATH):
        os.remove(ss.CKPT_PATH)


from services.memory_service import memory_service  # noqa: E402


def _mk(db, mid, vector_id=None, active=True, user_id=31):
    m = Memory(id=mid, user_id=user_id, type="semantic", category="general",
               content=f"记忆内容{mid}", vector_id=vector_id,
               confidence=0.9, importance=7, is_active=active)
    db.add(m)
    db.commit()
    return m


class TestWriteAllowed:
    def test_accept_at_threshold(self):
        assert ss.write_allowed(0.6, 4, 0.6, 4) is True

    def test_reject_low_conf(self):
        assert ss.write_allowed(0.59, 10, 0.6, 4) is False

    def test_reject_low_importance(self):
        assert ss.write_allowed(0.9, 3, 0.6, 4) is False

    def test_bad_input_rejects(self):
        assert ss.write_allowed(None, None) is False

    def test_defaults_from_settings(self):
        assert ss.write_allowed(0.5, 3) is False
        assert ss.write_allowed(0.9, 9) is True


class TestReconcile:
    def test_missing_vectors_repaired(self, db):
        m_no = _mk(db, "c1")               # 无向量
        m_bad = _mk(db, "c2", vector_id="vec_ghost")  # 悬空
        r = ss.storage_service.reconcile()
        assert r["missing"] == 1 and r["dangling"] == 1
        assert r["repaired"] == 2 and r["failed"] == 0
        db.expire_all()
        assert db.query(Memory).filter_by(id="c1").first().vector_id
        # 悬空被替换为新向量(不是 ghost)
        c2v = db.query(Memory).filter_by(id="c2").first().vector_id
        assert c2v and c2v != "vec_ghost"
        # AC-1: 对账后活跃记忆全部有向量且 Chroma 中存在
        r2 = ss.storage_service.reconcile()
        assert r2["missing"] == 0 and r2["dangling"] == 0

    def test_dry_run_no_repair(self, db):
        _mk(db, "c1")
        r = ss.storage_service.reconcile(dry_run=True)
        assert r["missing"] == 1 and r["repaired"] == 0
        db.expire_all()
        assert db.query(Memory).filter_by(id="c1").first().vector_id is None

    def test_inactive_ignored(self, db):
        _mk(db, "c1", active=False)
        r = ss.storage_service.reconcile()
        assert r["checked"] == 0

    def test_model_drift_skips_repair(self, db, monkeypatch):
        _mk(db, "c1")
        monkeypatch.setattr(ss.memory_service_chroma, "collection_model",
                            lambda: "other-model")
        r = ss.storage_service.reconcile()
        assert r["drift"] is True and r.get("repaired", 0) == 0
        db.expire_all()
        assert db.query(Memory).filter_by(id="c1").first().vector_id is None


class TestEnsureVector:
    def test_success_returns_vid(self, db):
        vid = ss.storage_service.ensure_vector("m1", "内容", 1)
        assert vid and vid.startswith("vec_")

    def test_failure_returns_none(self, monkeypatch):
        from core import embedding as emb
        def boom(*a, **k):
            raise RuntimeError("embed down")
        monkeypatch.setattr(emb.embedding_service, "embed", boom)
        assert ss.storage_service.ensure_vector("m1", "内容", 1) is None


class TestRebuild:
    def test_rebuild_all(self, db):
        _mk(db, "r1")
        _mk(db, "r2", vector_id="vec_old")
        r = ss.storage_service.rebuild()
        assert r["success"] and r["total"] == 2 and r["rebuilt"] == 2
        db.expire_all()
        assert all(m.vector_id for m in db.query(Memory).all())
        assert not os.path.exists(ss.CKPT_PATH)  # 全成功后清理

    def test_rebuild_failure_keeps_checkpoint_and_resumes(self, db, monkeypatch):
        _mk(db, "r1")
        _mk(db, "r2")

        real_embed = memory_service  # noqa: F841  (keep import used)
        from core.embedding import embedding_service
        calls = {"n": 0}
        orig = embedding_service.embed
        def flaky(text, *a, **k):
            calls["n"] += 1
            if "r2" in text and calls["n"] <= 2:  # 首轮 r2 失败
                raise RuntimeError("flaky embed")
            return orig(text, *a, **k)
        monkeypatch.setattr(embedding_service, "embed", flaky)

        # 确保按 id 顺序 r1 成功 r2 失败
        r = ss.storage_service.rebuild()
        assert r["total"] == 2
        assert r["rebuilt"] == 1 and r["failed"] == 1
        assert os.path.exists(ss.CKPT_PATH)
        with open(ss.CKPT_PATH) as f:
            ckpt = json.load(f)
        assert "r1" in ckpt["done_ids"] and "r2" not in ckpt["done_ids"]

        # 二轮续跑(故障已愈): 只补 r2
        calls["n"] = 99
        r2res = ss.storage_service.rebuild()
        assert r2res["rebuilt"] == 1 and r2res["success"]
        db.expire_all()
        assert all(m.vector_id for m in db.query(Memory).all())
