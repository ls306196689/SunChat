"""
R-009: 语音输入(ASR) - 契约与懒加载并发单测
真实模型转写(AC-2)标记 skipif:需预置模型+真实语音样本,由 R-009 实机 E2E 记录。
"""
import io
import os
import sys
import threading
import wave

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _wav_bytes(seconds=0.2, freq=0):
    """合成 wav(纯静音/正弦,仅走管线)。"""
    import math
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        frames = bytearray()
        for i in range(int(16000 * seconds)):
            v = int(3000 * math.sin(2 * math.pi * freq * i / 16000)) if freq else 0
            frames += v.to_bytes(2, "little", signed=True)
        w.writeframes(bytes(frames))
    return buf.getvalue()


class _FakeASR:
    def __init__(self, result=None, err=None, status="ready"):
        self._result = result
        self._err = err
        self.status = status
        self.calls = []

    def transcribe(self, audio):
        self.calls.append(len(audio))
        if self._err:
            raise self._err
        return self._result


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _up(client, data: bytes):
    return client.post("/api/v1/speech/transcribe",
                       files={"file": ("a.wav", data, "application/octet-stream")})


class TestTranscribeContract:
    """R-009/AC-1,AC-4: 端点契约矩阵(mock ASR)"""

    def test_ok_200(self, client, monkeypatch):
        fake = _FakeASR(result={"text": "你好世界", "language": "zh", "duration": 1.2})
        monkeypatch.setattr("core.asr.asr_service", fake)
        r = _up(client, _wav_bytes())
        assert r.status_code == 200
        assert r.json()["data"]["text"] == "你好世界"
        assert fake.calls == [len(_wav_bytes())]

    def test_empty_text_200(self, client, monkeypatch):
        monkeypatch.setattr("core.asr.asr_service",
                            _FakeASR(result={"text": "", "language": None,
                                             "duration": 0.2}))
        r = _up(client, _wav_bytes())
        assert r.status_code == 200
        assert r.json()["data"]["text"] == ""

    def test_not_ready_503(self, client, monkeypatch):
        monkeypatch.setattr("core.asr.asr_service",
                            _FakeASR(err=RuntimeError("模型加载失败: no model")))
        r = _up(client, _wav_bytes())
        assert r.status_code == 503

    def test_decode_fail_400(self, client, monkeypatch):
        monkeypatch.setattr("core.asr.asr_service",
                            _FakeASR(err=ValueError("音频解码/转写失败: bad")))
        r = _up(client, _wav_bytes())
        assert r.status_code == 400

    def test_bad_magic_400(self, client, monkeypatch):
        fake = _FakeASR(result={"text": "x", "language": "zh", "duration": 0})
        monkeypatch.setattr("core.asr.asr_service", fake)
        r = _up(client, b"this is not audio at all.....")
        assert r.status_code == 400
        assert not fake.calls, "魔数不匹配不应触达ASR"

    def test_oversize_413(self, client, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "SPEECH_MAX_MB", 0)
        r = _up(client, b"x" * 64)
        assert r.status_code == 413


class TestAudioSniff:
    """R-009/AC-4: 魔数白名单"""

    def test_whitelist(self):
        from app.api.v1.routes.speech import _sniff_audio
        assert _sniff_audio(b"RIFF\x00\x00\x00\x00WAVEfmt ")
        assert _sniff_audio(b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
        assert _sniff_audio(b"\x00\x00\x00 ftypM4A ")
        assert _sniff_audio(b"\x1a\x45\xdf\xa3\x01\x00\x00\x00\x00\x00\x00\x1f")
        assert _sniff_audio(b"ID3\x04\x00\x00\x00\x00\x00\x00")
        assert _sniff_audio(b"\xff\xfb\x90\x64\x00\x00")
        assert not _sniff_audio(b"%PDF-1.4.....")
        assert not _sniff_audio(b"\x89PNG\r\n\x1a\n....")


class TestLazyLoading:
    """R-009/AC-3: 懒加载并发安全(锁双检,仅加载一次)+失败缓存"""

    def test_concurrent_load_once(self, monkeypatch):
        import core.asr as asr_mod

        load_count = []
        gate = threading.Event()

        class FakeModel:
            def __init__(self, *a, **kw):
                load_count.append(1)
                gate.wait(timeout=2)  # 拉长加载窗口暴露竞争

        monkeypatch.setattr("faster_whisper.WhisperModel", FakeModel)
        svc = asr_mod.ASRService()
        threads = [threading.Thread(target=svc._ensure_model) for _ in range(6)]
        for t in threads:
            t.start()
        gate.set()
        for t in threads:
            t.join(timeout=5)
        assert len(load_count) == 1, f"并发应仅加载一次,实际 {len(load_count)}"
        assert svc.status == "ready"

    def test_load_error_cached_and_cleared(self, monkeypatch):
        import core.asr as asr_mod
        n = []

        class BadModel:
            def __init__(self, *a, **kw):
                n.append(1)
                raise OSError("no such model dir")

        monkeypatch.setattr("faster_whisper.WhisperModel", BadModel)
        svc = asr_mod.ASRService()
        with pytest.raises(Exception):
            svc._ensure_model()
        with pytest.raises(Exception):
            svc._ensure_model()
        assert len(n) == 1, "失败应缓存不再重试"
        svc.clear_error()
        with pytest.raises(Exception):
            svc._ensure_model()
        assert len(n) == 2, "clear_error 后允许重试"

    def test_status_property(self):
        import core.asr as asr_mod
        svc = asr_mod.ASRService()
        assert svc.status == "pending"


class TestRealModelE2E:
    """R-009/AC-2: 真实 base 模型管线(skipif 模型未预置)。
    语义准确率需真实人声样本,由前端实机E2E记录;此处验证 wav/合成解码管线。"""

    MODEL_READY = os.path.isdir(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data/whisper-models"))

    @pytest.mark.skipif(not MODEL_READY, reason="需预置 whisper base 模型")
    def test_pipeline_real_model(self):
        from core.asr import ASRService
        svc = ASRService()
        out = svc.transcribe(_wav_bytes(seconds=0.5))
        assert "text" in out and "language" in out
