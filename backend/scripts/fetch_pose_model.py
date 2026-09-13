"""R-017 部署前置:预取 pose_landmarker_lite.task(运行期禁下载,同 R-009 whisper 约定)。

用法: python scripts/fetch_pose_model.py  (幂等,已存在且大小一致则跳过)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings  # noqa: E402

URLS = [
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
    "https://huggingface.co/mediapipe-models/pose_landmarker_lite/resolve/main/pose_landmarker_lite.task",
]
EXPECT_MIN_BYTES = 5_000_000


def main() -> int:
    dst = Path(settings.POSE_MODEL_PATH)
    if dst.is_file() and dst.stat().st_size > EXPECT_MIN_BYTES:
        print(f"already in place: {dst} ({dst.stat().st_size} bytes)")
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    import urllib.request
    for url in URLS:
        try:
            print(f"downloading: {url}")
            tmp = dst.with_suffix(".tmp")
            urllib.request.urlretrieve(url, tmp)
            if tmp.stat().st_size <= EXPECT_MIN_BYTES:
                raise IOError(f"too small: {tmp.stat().st_size}")
            tmp.rename(dst)
            print(f"ok: {dst} ({dst.stat().st_size} bytes)")
            return 0
        except Exception as e:
            print(f"fail: {url} -> {e}")
    print("all sources failed;手工下载放置到上述路径(见 R-017/design-change.md)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
