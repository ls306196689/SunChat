"""
SunChat R-018 step-5 —— 真人实拍朝向对账取证脚本(AC-6)

把手机实拍的侧跑视频打 `/api/v1/chat/video/pose`,按 AC-6 逐项判定,
打印可读摘要 + JSON,并把人可读证据片段直接打到 stdout(便于重定向成
run-evidence/live-reconcile.md 的素材)。本脚本**只读取与上报,不写文件**,
入档由会话侧完成(保持 skill 的 run-evidence 编写纪律)。

判定项(全部来自 R-018/requirements.md AC-6 与 plan.md step-5):
  A orient 非 undetermined(横屏素材应为 90cw/270cw/180;竖屏预转正素材应为 0)
  B cadence_spm ∈ [140, 220]
  C 报告含朝向透明度行(仅当 orient 为需转正档位时强制)
  D 骨架帧已产出(≥1)——"人正立"需人眼核验脚本落盘帧,脚本只报数量与提示
  E 身高>0 时配速已输出(±20% 与自感配速的对账为人 work,脚本只报有无)

用法(backend/ 目录下,服务端已启动):
  python scripts/pose_live_capture.py --file ~/Videos/landscape.mp4 --label 横屏 \
      --session-id 82 --base-url http://localhost:8000
  # 两段各跑一次;--strict 时任一判定 FAIL → 退出码 1(便于脚本化)

素材要求: 侧跑(相机外侧 5~8m 跑过正面 / 跑步机侧面平行),横屏与竖屏各一段,
拍摄者身高与 .env 的 POSE_USER_HEIGHT_CM 一致(当前 173)。
"""
from __future__ import annotations

import argparse
import json
import sys

import requests

CAD_LO, CAD_HI = 140.0, 220.0
ROTATED_ORIENTS = ("90cw", "270cw", "180")


def post_video(base_url: str, path: str, session_id: str, timeout: int) -> tuple[int, dict]:
    with open(path, "rb") as fh:
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/v1/chat/video/pose",
            files={"file": (path.rsplit("/", 1)[-1], fh, "video/mp4")},
            data={"session_id": session_id},
            timeout=timeout,
        )
    try:
        body = resp.json()
    except ValueError:
        body = {"_raw": resp.text[:500]}
    return resp.status_code, body


def judge(status: int, body: dict) -> dict:
    """返回 {verdict_key: (ok, note)};HTTP 非 200 时只给 A 一条 FAIL 说明。"""
    res: dict[str, tuple[bool, str]] = {}
    if status != 200:
        res["A_orient"] = (False, f"HTTP {status}: "
                                  f"{str(body.get('detail') or body)[:200]}")
        return res

    data = body.get("data") or {}
    q = data.get("quality") or {}
    m = data.get("metrics") or {}
    report = data.get("report") or ""

    orient = q.get("orient")
    res["A_orient"] = (
        bool(orient) and orient != "undetermined",
        f"orient={orient} conf={q.get('orient_conf')} "
        f"samples={q.get('orient_samples')} "
        "(注:响应 quality 目前只带 orient/orient_conf,投票样本数走服务端 evt 日志)",
    )

    cad = m.get("cadence_spm")
    res["B_cadence"] = (
        isinstance(cad, (int, float)) and CAD_LO <= cad <= CAD_HI,
        f"cadence_spm={cad}(期望 {CAD_LO:.0f}~{CAD_HI:.0f})",
    )

    if orient in ROTATED_ORIENTS:
        res["C_transparency"] = (
            "画面已按人体朝向转正" in report,
            "报告应含「画面已按人体朝向转正(头朝上,原为 {0})」".format(orient),
        )
    else:
        res["C_transparency"] = (True, f"orient={orient} 无需转正行(正立/不可定文案另判)")

    frames = data.get("frame_ids") or []
    res["D_skeleton_frames"] = (len(frames) >= 1,
                                f"骨架帧 {len(frames)} 张 id={frames}(目视核验人正立)")

    pace = m.get("pace")
    res["E_pace"] = (bool(pace), f"pace={pace}(与自感配速 ±20% 人工对账)")

    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="R-018 step-5 真人实拍朝向对账")
    ap.add_argument("--file", required=True, help="实拍视频路径(mp4/mov/…)")
    ap.add_argument("--label", default="", help="素材标记,如「横屏」「竖屏」")
    ap.add_argument("--session-id", default="82",
                    help="落库会话(默认 82 = 跑姿调试会话,与日常会话隔离)")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--timeout", type=int, default=420,
                    help="单次请求上限(首请求含模型加载,放宽到默认 420s)")
    ap.add_argument("--strict", action="store_true", help="任一 FAIL → 退出码 1")
    args = ap.parse_args()

    status, body = post_video(args.base_url, args.file, args.session_id, args.timeout)
    verdicts = judge(status, body)
    all_ok = all(ok for ok, _ in verdicts.values())
    data = (body.get("data") or {}) if status == 200 else {}
    q = data.get("quality") or {}
    m = data.get("metrics") or {}

    title = f"## {args.label or args.file}"
    print(title)
    print(f"- HTTP: {status}  report_source={data.get('report_source')}  "
          f"message_id={data.get('message_id')}")
    print(f"- orient: `{json.dumps(q.get('orient'), ensure_ascii=False)}` "
          f"conf={q.get('orient_conf')} θ={q.get('orient_theta')} "
          f"samples={q.get('orient_samples')}")
    print(f"- 关键指标: cadence={m.get('cadence_spm')} pace={m.get('pace')} "
          f"body_ratio={q.get('body_ratio')} cycles={q.get('cycles')} "
          f"fps_eff={q.get('fps_eff')}")
    for k, (ok, note) in verdicts.items():
        print(f"- [{'PASS' if ok else 'FAIL'}] {k}: {note}")
    print("- 机读: " + json.dumps(
        {"label": args.label, "file": args.file, "http": status,
         "verdicts": {k: [ok, n] for k, (ok, n) in verdicts.items()},
         "orient": q.get("orient"), "orient_conf": q.get("orient_conf"),
         "cadence_spm": m.get("cadence_spm"), "pace": m.get("pace"),
         "frame_ids": data.get("frame_ids")},
        ensure_ascii=False))
    if status == 200:
        print("\n### 报告原文\n")
        print(data.get("report") or "(空)")
    print("\n总判定:", "PASS" if all_ok else "FAIL",
          file=sys.stderr)
    return 0 if (all_ok or not args.strict) else 1


if __name__ == "__main__":
    sys.exit(main())
