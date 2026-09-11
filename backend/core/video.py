"""
SunChat Backend - Video Frame Extraction (R-010 视频输入)
PyAV 均匀抽帧(自带编解码,无需系统 ffmpeg)→ JPEG,帧复用 R-008 图片通道。
"""
import io
from typing import List, Optional, Tuple

from utils.logger import logger


def _container_duration(container, stream) -> Optional[float]:
    try:
        if container.duration and container.duration > 0:
            return float(container.duration * container.time_base)
    except Exception:
        pass
    try:
        if stream.duration and stream.time_base:
            return float(stream.duration * stream.time_base)
        if stream.frames and stream.average_rate:
            return float(stream.frames / float(stream.average_rate))
    except Exception:
        pass
    return None


def extract_frames(data: bytes, max_frames: Optional[int] = None) -> Tuple[List[Tuple[bytes, float]], float]:
    """视频字节 → ([(jpeg_bytes, 时间戳秒), ...], 视频时长秒)。

    均匀采样(避开首尾),seek 后仅解码目标帧;失败/无可解帧 raise ValueError。
    """
    import av  # 懒 import(R-010)

    if max_frames is None:
        import app.config as _c
        max_frames = _c.settings.VIDEO_MAX_FRAMES
    max_frames = max(1, int(max_frames))

    try:
        container = av.open(io.BytesIO(data))
    except Exception as e:
        raise ValueError(f"视频容器无法打开: {e}") from e

    try:
        if not container.streams.video:
            raise ValueError("容器内无视频流")
        stream = container.streams.video[0]
        duration = _container_duration(container, stream)

        targets: List[float]
        if duration and duration > 0:
            targets = [duration * (i + 0.5) / max_frames for i in range(max_frames)]
        else:
            targets = []  # 时长未知:顺序取前 N 个可解码帧

        frames: List[Tuple[bytes, float]] = []

        if targets:
            try:
                # seek 以流为 keyframe 单位;time_base 秒 → stream 内部单位
                c_tb = float(container.time_base) if container.time_base else 0.0
                for t in targets:
                    try:
                        if c_tb:
                            container.seek(int(t / c_tb), stream=stream)
                        got = None
                        for f in container.decode(video=0):
                            got = f
                            break
                        if got is None:
                            continue
                        ts = float(got.pts * stream.time_base) if got.pts is not None else t
                        frames.append((_to_jpeg(got), max(ts, 0.0)))
                    except (StopIteration, EOFError):
                        continue
            except Exception as e:
                logger.debug(f"[VIDEO] seek 采样降级顺序解码: {e}")
                container.close()
                container = av.open(io.BytesIO(data))
                frames = []
                targets = []

        if not targets:
            # 顺序路径:前 max_frames 个可解码帧
            n = 0
            for f in container.decode(video=0):
                ts = float(f.pts * stream.time_base) if (f.pts is not None and stream.time_base) else 0.0
                frames.append((_to_jpeg(f), max(ts, 0.0)))
                n += 1
                if n >= max_frames:
                    break

        if not frames:
            raise ValueError("未解出任何视频帧(文件损坏/编码不支持)")
        return frames, (duration or 0.0)
    finally:
        try:
            container.close()
        except Exception:
            pass


def _to_jpeg(frame, quality: int = 82) -> bytes:
    img = frame.to_image()  # PIL
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
