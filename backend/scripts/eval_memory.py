"""
SunChat Eval - 记忆检索评测脚本 (M5)
golden set: scripts/data/memory_golden.json
指标: hit@1 / hit@3 / 无关节注入率(irrelevant_injection_rate)

用法(backend/ 目录下):
  python scripts/eval_memory.py --label after [--report-dir scripts/data]

说明:
- 进程内直调 memory_service(而非 HTTP), 以便 before(旧代码树 worktree)/after 各自测本树代码路径;
  写入/检索仍走真实 service+Chroma+FTS 链路。
- user_id=--user(默认99) 与日常用户隔离; --cleanup 删除该用户全部记忆(SQLite+Chroma+FTS)。
- 时间对比用例 setup 内容带 "|old"/"|new" 后缀: old 行 created_at 回拨 180 天。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

GOLDEN = os.path.join(BACKEND_DIR, "scripts", "data", "memory_golden.json")


def load_golden():
    with open(GOLDEN, "r", encoding="utf-8") as f:
        return json.load(f)


def cleanup_user(user_id: int) -> int:
    from sqlalchemy import text
    from models.sql_models import get_engine, get_thread_session, Memory
    db = get_thread_session()
    mems = db.query(Memory).filter(Memory.user_id == user_id).all()
    ids = [m.id for m in mems]
    vids = [m.vector_id for m in mems if m.vector_id]
    db.query(Memory).filter(Memory.user_id == user_id).delete()
    db.commit()
    if vids:
        try:
            from services.memory_service import memory_service
            memory_service.chroma_client.delete(vids)
        except Exception as e:
            print(f"[eval] chroma 清理失败(忽略): {e}", file=sys.stderr)
    for mid in ids:
        try:
            with get_engine().begin() as conn:
                conn.exec_driver_sql("DELETE FROM memory_fts WHERE memory_id = ?", (mid,))
        except Exception:
            pass
    return len(ids)


def setup_case(user_id: int, case: dict) -> None:
    from models.sql_models import get_thread_session, Memory
    from services.memory_service import memory_service
    db = get_thread_session()
    for entry in case["setup"]:
        content, backdate = entry, 0
        if entry.endswith("|old"):
            content, backdate = entry[:-4], 180
        elif entry.endswith("|new"):
            content = entry[:-4]
        r = memory_service.create_memory(
            user_id=user_id, content=content,
            category=case.get("category", "general"),
            importance=7, confidence=0.9)
        if backdate:
            row = db.query(Memory).filter_by(id=r["id"]).first()
            row.created_at = datetime.now() - timedelta(days=backdate)
            db.commit()


def run_eval(user_id: int, topk: int, quiet: bool = False):
    from services.memory_service import memory_service
    cases = load_golden()
    n = len(cases)
    hit1 = hitk = 0
    forbid_cases = forbid_hits = 0
    per_case = []

    for case in cases:
        setup_case(user_id, case)

    # setup 后统一检索(避免边写边影响排名)
    for case in cases:
        results = memory_service.search_memories(
            user_id=user_id, query=case["query"], top_k=topk)
        topk_contents = [r.get("content", "") for r in results]
        any_hit = any(any(w in c for w in case["expect_any"]) for c in topk_contents)
        hit_at1 = bool(topk_contents) and any(w in topk_contents[0] for w in case["expect_any"])
        hit1 += hit_at1
        hitk += any_hit
        fb = case.get("forbid_in_topk")
        irrelevant = False
        if fb:
            forbid_cases += 1
            irrelevant = any(any(w in c for w in fb) for c in topk_contents)
            forbid_hits += irrelevant
        per_case.append({"id": case["id"], "query": case["query"],
                         "hit": any_hit, "hit@1": hit_at1,
                         "irrelevant": irrelevant,
                         "topk": topk_contents})
        if not quiet:
            mark = "HIT " if any_hit else "MISS"
            print(f"[eval] {mark} {case['id']} q={case['query']} -> {topk_contents[:2]}")

    if not quiet:
        print(f"[eval] 清理评测用户 {user_id} ...")
    cleanup_user(user_id)

    return {
        "run_at": datetime.now().isoformat(),
        "n": n,
        "hit@1": round(hit1 / n, 4),
        f"hit@{topk}": round(hitk / n, 4),
        "irrelevant_injection_rate": (round(forbid_hits / forbid_cases, 4)
                                      if forbid_cases else 0.0),
        "topk": topk,
        "per_case": per_case,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run")
    ap.add_argument("--user", type=int, default=99)
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--cleanup", action="store_true", help="仅清理评测用户后退出")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.cleanup:
        print(f"[eval] removed {cleanup_user(args.user)} memories of user {args.user}")
        return

    # 评测前就绪 FTS(after 树) / 忽略不可用(before 树无此模块)
    try:
        from core import fts_index
        if fts_index.init_fts():
            fts_index.fts_bootstrap_from_sqlite()
    except Exception:
        pass

    cleanup_user(args.user)  # 干净起点
    report = run_eval(args.user, args.topk, quiet=args.quiet)

    out = os.path.join(BACKEND_DIR, "scripts", "data",
                       f"eval_report_{args.label}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[eval] {args.label}: n={report['n']} hit@1={report['hit@1']} "
          f"hit@{args.topk}={report[f'hit@{args.topk}']} "
          f"irrelevant={report['irrelevant_injection_rate']} -> {out}")


if __name__ == "__main__":
    main()
