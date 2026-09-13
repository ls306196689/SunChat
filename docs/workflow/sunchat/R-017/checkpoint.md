# R-017 checkpoint(v2 重构执行中)
更新: 2026-09-13 23:40 | 上下文快照,新会话优先读本文件+state.json

## 需求主线
- R-017 跑步姿态分析,phase=execute,requirements v2,change_count=1(已确认)
- 端点 POST /api/v1/chat/video/pose;模块 P1 core/pose.py,P2 pose_skeleton.py,
  P3 pose_report.py,P4 routes/chat.py,P5 前端两页(均已 v1 完成并上线过)
- git 远端 https://github.com/ls306196689/SunChat.git master,最后推送=变更v2入档commit

## 已完成(git log --grep R-017 可查)
1. v1 全链已上线:抽帧分析/骨架帧/VL双路报告/extra列/前端双端按钮+r017_check
2. step-2:mediapipe==0.10.35 锁版(禁升1.x,强numpy2破chromadb);模型已预置
   backend/data/pose-models/pose_landmarker_lite.task(gitignore内);
   脚本 backend/scripts/fetch_pose_model.py 幂等可重跑
3. D-cadence 修复已上线(commit 1635e885):竖直踝y振荡+自相关主频法,机位无关性
   双测试永久护栏(test_pose_core 12/12,全量 318+1skip)
4. v2 变更已确认入档:requirements.md v2 + design-change.md r2 + analysis.md
   (A-1死段稀释实验/A-2帧率元数据不可信实验/A-3配速原型19%误差/A-4采样账)
   + risks R-7~R-10 + 用户确认"确认变更,开工"(v2) + steps3/6已重置

## v2 未完成的实现(新会话从这里干)
工作区已有未提交改动:backend/app/config.py 已加 POSE_COARSE_FPS=5/POSE_DENSE_FPS=25/
POSE_MAX_SAMPLE_FRAMES=400→600/POSE_MAX_SEGMENT_SEC=8/POSE_ACTIVITY_MIN_SEC=1.5/
POSE_RUN_MIN_CAD=125/POSE_USER_HEIGHT_CM=0/POSE_SLO_RESTORE=True(先 commit 起步)

### step-3v2 pose-core(重做,当前 in_progress)→ tests/test_pose_core.py 追加
- probe_frames(data):只 demux 不解码;全量 packet PTS→f_eff=1/中位diff,
  名义fps=stream.average_rate,N=round(名义/f_eff)∈{2,4,8}且名义>=240才算slo;
  PTS diff CV>0.35→vfr=True([A-2]:slo容器里average_rate会谎报30.2,实测法为准;
  PyAV 无 container.time_base!duration 用 pts_range/float(time_base))
- locate_activity(lms粗扫, ts):窗口1s滑窗 score=踝y振荡能量×自相关周期峰
  (周期窗0.25~1.25s,复用 _dominant_lag)×人体占比;判跑阈值:score达标+窗口内
  cad估计=2×_dominant_lag频率×60≥POSE_RUN_MIN_CAD(走路≈100-120被滤);
  合并<0.3s邻段,按energy×时长排序取前2累计≤8s
- 粗扫采样:min(POSE_COARSE_FPS, f_eff),decode resize 256px(推理提速)
- 密采:段首 av seek,段内 min(POSE_DENSE_FPS, f_eff),上限 600
- cadence/ssr/asym 分母=跑动段时长(修 A-1 稀释;span 变量来自 _metrics 现全片首末)
- slo 还原:quality.slo_factor=N;cadence=测量值×N(仅当 POSE_SLO_RESTORE)
- pace(metrics+段内钉地落点):见 design-change FR-11;前置=固定机位(段内踝x跨度归一化
  ≥0.8×身高px 且 髋连线倾角<15°)+POSE_USER_HEIGHT_CM>0;腿长px=median(|髋-膝|+|膝-踝|)
  双腿取中,m_per_px=(0.53*height_m)/腿长px;落点=左右踝(低速x∩低y)区间中点合并排序,
  相邻距中值×m_per_px=步长;v=步长×cad/60;pace dict{v_ms,kmh,min_per_km,stride_m,
  height_cm};否则 metrics['pace']=null+metrics['pace_reason']
- AC-7 夹具:前3s站立(双腿分立y不动)+后3s跑 → cad 差≤5%
- AC-8 夹具:ts 间隔×4(伪slo)→ cadence 还原±10%,slo_factor=4
- AC-9 夹具:原型v5几何(v5教训:事件轴 land=(2j+side_off)*GAP 同脚跨2步距;
  屏幕y向下为正,踝 y=hip_y+L*(0.985-0.62*lift);v5实测 scale+4%/步距-4%/端到端19%)
- ⚠R-7:粗扫5fps<髋2f奈奎斯特临界,若夹具漏检跑动段→POSE_COARSE_FPS升8
- _detect_landmarks 保持 monkeypatch 注入面;新增粗扫描同样走它(注入面按帧数感知)

### step-4v2 union_crop+draw_skeleton(crop_bbox 可选参);step-5v2 透明度行
(格式参考 fps≈f_eff/分析段 x~y s/慢动作×N/配速来源身高)
### step-6v2 端点:no_activity 400 映射、quality 透传、落盘裁剪帧、caplog 断言加
  fields;重启后端(必须 setsid --fork bash -c 'cd backend && exec python -m uvicorn
  app.main:app --host 0.0.0.0 --port 8000 >> backend.log 2>&1 < /dev/null' 否则被shell杀)
### step-8v2 真人复测:等用户实拍对账(上次实测 cad=48.6 即稀释 bug,已确诊)

## 验证命令
- cd backend && python -m pytest tests -q(基线 318 passed 1 skipped)
- cd frontend && node scripts/r017_check.mjs(先 build)6/6
- 活体:curl -X POST localhost:8000/api/v1/chat/video/pose -F file=@v.mp4 -F session_id=1

## 关键陷阱备忘
- mediapipe 1.x 禁升;模型文件相对路径打不开必须绝对路径;
  test 夹具教训:v1 dwell夹具世界速度静止=镜像错误假设全绿而真机崩——新夹具必须
  "真实采集形态"(含死段/slo拉伸/VFR 可选加)
- log_event(log,domain,action,result,**fields):fields 里别再叫 result(main.py:65 既有撞名bug,非本需求)
- R-016 遗留 step-3 真机对账仍 in_progress(与本需求并行,不阻塞)
