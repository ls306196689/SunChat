"""
R-016 diag/client 单测
AC-1→test_diag_ingest/test_diag_over_limit/test_diag_bad_payload_400/test_diag_evt_line
"""
import logging

import pytest


BASE = {"page": "/m", "events": [
    {"ts": 1, "lvl": "info", "step": "upload.pick", "msg": "picked",
     "extra": {"reqId": "ab12cd34", "name": "a.png", "size": 123, "type": "image/png"}},
    {"ts": 2, "lvl": "err", "step": "upload.fail",
     "msg": "Network Error", "extra": {"reqId": "ab12cd34"}},
]}


class TestDiagIngest:
    """AC-1→ 端点形状/截断/净化/事件行落日志"""

    def test_diag_ingest(self, client):
        r = client.post("/api/v1/diag/client", json=BASE)
        assert r.status_code == 200
        assert r.json()["data"] == {"ok": True, "n": 2}

    def test_diag_over_limit(self, client):
        evs = [{"ts": i, "lvl": "info", "step": "x", "msg": "m"} for i in range(60)]
        r = client.post("/api/v1/diag/client", json={"page": "/m", "events": evs})
        assert r.status_code == 200 and r.json()["data"]["n"] == 50

    def test_diag_bad_payload_400(self, client):
        assert client.post("/api/v1/diag/client", json={"page": "/m"}).status_code == 400
        assert client.post("/api/v1/diag/client",
                           json={"page": "/m", "events": []}).status_code == 400

    def test_diag_evt_line(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="sunchat"):
            client.post("/api/v1/diag/client", json=BASE)
        text = caplog.text
        assert "evt=mobile.diag" in text
        assert "page=/m" in text and "step=upload.pick" in text
        assert "reqId" in text.replace("'", "")  # extra JSON 落行
        assert "step=upload.fail" in text  # err 行同样落

    def test_diag_message_truncated(self, client, caplog):
        big = {"page": "/m", "events": [
            {"ts": 1, "lvl": "info", "step": "x", "msg": "A" * 900}]}
        with caplog.at_level(logging.INFO, logger="sunchat"):
            r = client.post("/api/v1/diag/client", json=big)
        assert r.status_code == 200
        for line in caplog.text.splitlines():
            if "evt=mobile.diag" in line:
                assert "AAAA" in line
                assert line.count("A") <= 500
