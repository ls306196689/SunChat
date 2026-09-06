"""
SunChat - 数据备份脚本(轻量)
用法: python scripts/backup_data.py [--keep 10]
- SQLite 在线快照(sqlite3 backup API, 安全一致)
- Chroma 目录打包 tar.gz
- 产物: data/backups/sunchat_<ts>.db / chroma_<ts>.tar.gz, 保留最近 N 份
"""
import argparse
import os
import sqlite3
import sys
import tarfile
from datetime import datetime

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, default=10)
    args = ap.parse_args()

    from app.config import settings
    db_src = str(settings.DATABASE_URL).replace("sqlite:///", "")
    chroma_dir = str(settings.CHROMA_PERSIST_DIR)
    out_dir = os.path.join(BACKEND_DIR, "data", "backups")
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if os.path.exists(db_src):
        dst = os.path.join(out_dir, f"sunchat_{ts}.db")
        with sqlite3.connect(db_src) as src, sqlite3.connect(dst) as dstc:
            src.backup(dstc)
        print(f"[backup] {dst} ({os.path.getsize(dst)} bytes)")
    else:
        print(f"[backup] skip: {db_src} 不存在")

    if os.path.isdir(chroma_dir):
        dst = os.path.join(out_dir, f"chroma_{ts}.tar.gz")
        with tarfile.open(dst, "w:gz") as tar:
            tar.add(chroma_dir, arcname="chroma")
        print(f"[backup] {dst} ({os.path.getsize(dst)} bytes)")
    else:
        print(f"[backup] skip: chroma {chroma_dir} 不存在")

    # 保留最近 keep 份(按时间戳分组清理)
    import re, glob
    groups = {}
    for p in sorted(glob.glob(os.path.join(out_dir, "*"))):
        m = re.search(r"_(\d{8}_\d{6})", os.path.basename(p))
        if m:
            groups.setdefault(m.group(1), []).append(p)
    for stamp in sorted(groups.keys())[:-args.keep] if len(groups) > args.keep else []:
        for p in groups[stamp]:
            os.remove(p)
            print(f"[backup] pruned {p}")
    print("[backup] done")


if __name__ == "__main__":
    main()
