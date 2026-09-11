"""
SunChat Backend - ASR Service (R-009 语音输入)
本地 faster-whisper 转写：懒加载单例（锁保护），运行期完全离线（模型需预置,禁下载）。
"""
import io
import threading
from typing import Dict, Optional

from utils.logger import logger


class ASRService:
    """faster-whisper 懒加载封装:status 探测 + transcribe。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._loading = False
        self._model = None
        self._load_error: Optional[str] = None

    def _cfg(self):
        import app.config as _c  # 运行时读取(reload 兼容)
        return _c.settings

    @property
    def status(self) -> str:
        """ready | loading | unavailable(从未加载时 pending→ready 触发懒加载语义见 transcribe)。"""
        if self._model is not None:
            return "ready"
        if self._loading:
            return "loading"
        return "pending"

    def _ensure_model(self):
        """加载模型（double-check）。失败缓存错误不再重试,除非 clear_error。"""
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            if self._load_error:
                raise RuntimeError(f"ASR 模型加载失败: {self._load_error}")
            self._loading = True
            try:
                from faster_whisper import WhisperModel
                cfg = self._cfg()
                logger.info(f"[ASR] 加载模型 {cfg.WHISPER_MODEL_SIZE} (int8/cpu) @ {cfg.WHISPER_MODEL_DIR}")
                self._model = WhisperModel(
                    cfg.WHISPER_MODEL_SIZE,
                    device="cpu",
                    compute_type="int8",
                    download_root=cfg.WHISPER_MODEL_DIR,
                    local_files_only=True,  # 运行期禁下载(D-502):模型必须预置
                )
                logger.info("[ASR] 模型加载完成")
            except Exception as e:
                self._load_error = str(e)
                raise
            finally:
                self._loading = False
            return self._model

    def clear_error(self) -> None:
        """测试/修复用:清除加载失败缓存,允许重试。"""
        with self._lock:
            self._load_error = None

    def transcribe(self, audio: bytes) -> Dict:
        """音频字节 → {text, language, duration}。解码失败 raise ValueError。"""
        model = self._ensure_model()
        try:
            segments, info = model.transcribe(io.BytesIO(audio),
                                              language=None, vad_filter=True)
            text = "".join(s.text for s in segments).strip()
            return {"text": text,
                    "language": getattr(info, "language", None),
                    "duration": round(float(getattr(info, "duration", 0.0)), 2)}
        except ValueError:
            raise
        except Exception as e:
            # av/ctranslate2 对坏文件的报错统一转 ValueError(路由层 400)
            raise ValueError(f"音频解码/转写失败: {e}") from e


asr_service = ASRService()
