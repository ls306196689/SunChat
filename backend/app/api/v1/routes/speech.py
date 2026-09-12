"""
SunChat Backend - Speech Route (R-009 语音输入)
上传录音 → 本地 faster-whisper 转写文本。纯本地处理,零外传。
"""
from fastapi import APIRouter, HTTPException, UploadFile, File

from utils.logger import logger, log_event

router = APIRouter()


def _cfg():
    import app.config as _c  # 运行时读取(reload 兼容)
    return _c.settings


def _sniff_audio(header: bytes) -> bool:
    """音频魔数白名单:wav(RIFF..WAVE)/ogg(OggS)/mp4-m4a(ftyp@4)/webm-ebml/mp3(ID3或帧头)。"""
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return True
    if header.startswith(b"OggS"):
        return True
    if header[4:8] == b"ftyp":
        return True
    if header.startswith(b"\x1a\x45\xdf\xa3"):  # EBML (webm)
        return True
    if header.startswith(b"ID3") or header[:2] == b"\xff\xfb" or header[:2] == b"\xff\xf3":
        return True
    return False


@router.get("/speech/status")
def speech_status():
    """R-009: ASR 就绪状态(前端 🎤 可用性/加载提示)。"""
    from core.asr import asr_service
    cfg = _cfg()
    return {"code": 200, "message": "success",
            "data": {"status": asr_service.status,
                     "model_size": cfg.WHISPER_MODEL_SIZE}}


@router.post("/speech/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """R-009: 录音文件转写。魔数白名单+大小限制;模型未就绪 503;解码失败 400。"""
    cfg = _cfg()
    max_bytes = cfg.SPEECH_MAX_MB * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        log_event(logger, "speech", "transcribe", "fail", reason="oversize",
                  size_mb=round(len(data) / 1048576, 1))
        raise HTTPException(status_code=413,
                            detail=f"音频超过 {cfg.SPEECH_MAX_MB}MB 限制")
    if not _sniff_audio(data[:16]):
        log_event(logger, "speech", "transcribe", "fail", reason="bad_magic")
        raise HTTPException(status_code=400,
                            detail="不支持的音频格式(wav/mp3/m4a/ogg/webm)")

    from core.asr import asr_service
    from starlette.concurrency import run_in_threadpool  # 转写为长时CPU任务,勿阻塞事件循环
    try:
        result = await run_in_threadpool(asr_service.transcribe, data)
    except RuntimeError as e:
        # 模型缺失/加载失败 → 服务未就绪
        log_event(logger, "speech", "transcribe", "fail", reason="not_ready",
                  error=str(e)[:120])
        raise HTTPException(status_code=503, detail=f"语音模型未就绪: {e}")
    except ValueError as e:
        log_event(logger, "speech", "transcribe", "fail", reason="decode",
                  error=str(e)[:120])
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_event(logger, "speech", "transcribe", "fail", reason="internal",
                  error=str(e)[:120], exc=True)
        raise HTTPException(status_code=500, detail="转写失败")
    log_event(logger, "speech", "transcribe", "ok",
              dur=result.get("duration"), text_len=len(result.get("text", "")))
    return {"code": 200, "message": "success", "data": result}
