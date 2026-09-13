"""
R-014 mobile-pair 后端单测
AC-1: SPA 静态挂载双态(dist存在/缺失)   AC-2: pair/info LAN 探测与形状
"""
import json
from pathlib import Path

import pytest

import app.main as main_mod


@pytest.fixture
def dist_tmp(tmp_path):
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<!doctype html><title>m</title>", encoding="utf-8")
    (d / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return d


class TestStaticHosting:
    """AC-1→test_serve_root_when_dist_exists/test_spa_fallback_m/test_api_not_hijacked/test_no_dist_graceful"""

    def test_serve_root_when_dist_exists(self, client, dist_tmp, monkeypatch):
        monkeypatch.setattr(main_mod, "FRONTEND_DIST", str(dist_tmp))
        r = client.get("/")
        assert r.status_code == 200 and "<!doctype html>" in r.text

    def test_spa_fallback_m(self, client, dist_tmp, monkeypatch):
        monkeypatch.setattr(main_mod, "FRONTEND_DIST", str(dist_tmp))
        r = client.get("/m")
        assert r.status_code == 200 and "doctype html" in r.text
        r2 = client.get("/some/unknown/route")
        assert r2.status_code == 200  # history 回退

    def test_real_asset_served(self, client, dist_tmp, monkeypatch):
        monkeypatch.setattr(main_mod, "FRONTEND_DIST", str(dist_tmp))
        r = client.get("/assets/app.js")
        assert r.status_code == 200 and "console.log" in r.text

    def test_api_not_hijacked(self, client, dist_tmp, monkeypatch):
        monkeypatch.setattr(main_mod, "FRONTEND_DIST", str(dist_tmp))
        r = client.get("/api/v1/definitely-not-a-route")
        assert r.status_code == 404

    def test_no_dist_graceful(self, client, monkeypatch):
        monkeypatch.setattr(main_mod, "FRONTEND_DIST", "/nonexistent/dist")
        r = client.get("/")
        assert r.status_code == 200 and "SunChat API" in r.text  # JSON 根,桌面/dev 原行为
        r2 = client.get("/m")
        assert r2.status_code == 404

    def test_traversal_guard(self, client, dist_tmp, monkeypatch):
        monkeypatch.setattr(main_mod, "FRONTEND_DIST", str(dist_tmp))
        r = client.get("/..%2f..%2fetc%2fpasswd")
        assert r.status_code in (404, 400)


class TestPairInfo:
    """AC-2→test_pair_info_shape/test_pair_info_lan_probe_mock/test_pair_info_no_lan"""

    def test_pair_info_shape(self, client):
        r = client.get("/api/v1/pair/info")
        assert r.status_code == 200
        data = r.json()["data"]
        assert set(data) >= {"lan_ip", "port", "url"}
        assert isinstance(data["lan_ip"], str)

    def test_pair_info_lan_probe_mock(self, client, monkeypatch):
        import app.api.v1.routes.pair as pr
        monkeypatch.setattr(pr, "detect_lan_ip", lambda: "192.168.1.50")
        monkeypatch.setattr(pr.settings, "APP_PORT", 8000, raising=False)
        d = client.get("/api/v1/pair/info").json()["data"]
        assert d["lan_ip"] == "192.168.1.50"
        assert d["url"] == "http://192.168.1.50:8000/m"

    def test_pair_info_public_port_override(self, client, monkeypatch):
        import app.api.v1.routes.pair as pr
        monkeypatch.setattr(pr, "detect_lan_ip", lambda: "10.0.0.9")
        monkeypatch.setattr(pr.settings, "PUBLIC_PORT", 9999, raising=False)
        d = client.get("/api/v1/pair/info").json()["data"]
        assert d["url"] == "http://10.0.0.9:9999/m"

    def test_pair_info_no_lan(self, client, monkeypatch):
        import app.api.v1.routes.pair as pr
        monkeypatch.setattr(pr, "detect_lan_ip", lambda: "")
        d = client.get("/api/v1/pair/info").json()["data"]
        assert d["lan_ip"] == "" and d["url"] == ""
        assert d["port"] >= 1

    def test_detect_lan_ip_real_no_crash(self):
        from app.api.v1.routes.pair import detect_lan_ip
        ip = detect_lan_ip()
        assert ip == "" or (ip and not ip.startswith("127.") and ":" not in ip)
