# R-017 checkpoint(v2 实现完毕,等真人实拍对账)
更新: 2026-09-14 02:10 | 上下文快照,新会话优先读本文件+state.json

## 需求主线
- R-017 跑步姿态分析,phase=execute,requirements v2,change_count=1(已确认)
- 端点 POST /api/v1/chat/video/pose;P1 core/pose.py,P2 pose_skeleton.py,P3 pose_report.py,
  P4 routes/chat.py,P5 前端(均已 v2 化并通过全量测试)
- git 远端 https://github.com/ls306196689/SunChat.git master;本地最新:
  5fd7e101(step-3v2)→1a251e6a(step-4,5v2)→8365b142(step-6v2);
  ⚠这些 commit 尚未 push(下次会话先 push)

## 本轮完成(step-3/4/5/6 v2,全量 pytest 340+1skip 零回归)
1. pose-core v2:probe_frames(PTS 实测 f_eff/slo∈{2,4,8}且名义≥240/VFR CV>0.35,永不抛)、
   locate_activity(1s 滑窗 raw-std/med_leg≥0.04 剔站立死段;freq 判跑**移到密采终判门**
   125~240spm——5fps 踝主频混叠 R-7 证实,debug-log D-4 待补记)、
   fast-seek 段密采(t0/t1+per_seg 预算均分)、_metrics 分母=IC 相邻差覆盖跨段(修 A-1)、
   slo 还原 cad×N、_pace(IC 钉地落点+stance 帧腿长自标定 0.53×身高/腿长px;三态:
   横移<0.8×身高px→跑步机null;tilt>15°null;身高=0null)、crop_bbox bbox+10%(短边<256 整帧)
2. skeleton:draw_skeleton(crop_bbox 归一化 xyxy,+裁剪+锚点重映射+越界钳制)
3. report:transparency_lines(fps/段/slo/VFR/裁剪/pace口径)+模板与 VL prompt 双注入;
   summary_text 增 pace 行
4. 端点:no_activity 400 映射(parametrize+1)、quality v2 键透传、evt 日志
   fps_eff/span/pace/crop fields、落盘帧=裁剪版(AC-10 断言 crop→24x24)
5. 测试:test_pose_core v2 全重写(时间相干夹具+钉落点事件轴 v5 教训);
   AC-7 稀释≤5%/AC-8 slo×4 还原(密采 f=min(25,f_eff) 自洽,187.5∈±10%)/AC-9 pace 三态

## 关键实现教训(新会话别重蹈)
- _smooth 偶数窗会变长 → 全部去趋势窗已 |1 钳奇数
- _segment 已加 slo 参(主周期 hi=1.25×N + min_lag=3 防去趋势窗边假峰)
- 粗扫频带判定在 5fps 下必翻车(跑带 2.08~4Hz 混叠);走路拒判靠密采终判门 cad∉[125,240]
- analyze 注入面=_detect_landmarks(frames, ts)+sample_frames(fps,t0,t1,width)+probe_frames
- mediapipe 禁升 1.x;模型绝对路径;real avi probe 夹具用 f.pts=i*stretch+f.time_base=Fraction(1,240)
- 重启后端:kill 旧 pid 后 `cd backend && setsid --fork bash -c 'exec python -m uvicorn
  app.main:app --host 0.0.0.0 --port 8000 >> backend.log 2>&1 < /dev/null'`(已做,health 200)

## step-8 v2 等用户(唯一剩余)
- 真人侧跑实拍(手机→/m 或 curl POST)对账:上次 cad=48.6 稀释 bug 已修,本次预期
  cad∈[140,220]+报告透明度行(分析段/裁剪fps/slo)+骨架帧裁剪版回显;身高若要求配速:
  POSE_USER_HEIGHT_CM=175 重启再测
- AC-3 渲染证据已有(v1 步骤 7 headless+桌面截图入 run-evidence);实拍后补 live 截图
- run-evidence/step8-live.md 勾掉剩余项 → 全量终测 → compliance archive → 归档

## 验证命令
- cd backend && python -m pytest tests -q(基线 340 passed 1 skipped)
- 活体:curl -X POST localhost:8000/api/v1/chat/video/pose -F file=@run.mp4 -F session_id=1
- 走路视频应 400 no_activity;慢动作素材报告应带"步频已按倍速还原"

## 并行事项
- R-016 真机对账仍 in_progress(不阻塞本需求)
