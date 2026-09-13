# R-017 执行计划

需求: R-017 | 设计基线: R-017/design-change.md r1 + modules/P1~P5 | 日期: 2026-09-13

## 步骤表
| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | 基线核对(迭代需求首步) | - | design-change.md, requirements.md | 核对 R-010 端点/chat_service.save_* /Message 表现状与设计引用一致,差异登记 debug-log;验证:核对清单勾选入档(纯文档豁免单测) | R-5 |
| 2 | 依赖与模型预置 | config | design-change.md§技术选型 | requirements.txt+mediapipe==0.10.35;pip install 后全量 pytest 基线不劣化;config.py 增 POSE_* 组;脚本下载 pose_landmarker_lite.task→backend/data/pose-models/;验证:`pytest -q` 全量绿+`python -c "import mediapipe"` | R-1,R-6 |
| 3 | pose-core 实现+单测 | P1 | modules/pose-core.md | core/pose.py;tests/test_pose_core.py:合成正弦踝轨迹(known cadence 180)断言切分数与步频±5%、关节角已知几何断言、质量三门槛各一 fail、max_frames 降步距;**AC-1(离线面)→test_metrics_sine_cadence**;mp 推理 monkeypatch 注入关键点(AC 真实视频=step 7) | R-2,R-3 |
| 4 | pose-skeleton 实现+单测 | P2 | modules/pose-skeleton.md, P1产出 | core/pose_skeleton.py;tests/test_pose_skeleton.py:相位选帧去重/互异、draw 输出帧差异>0、k 不足补足路径 | - |
| 5 | pose-report 实现+单测 | P3 | modules/pose-report.md, P1产出 | core/pose_report.py;tests/test_pose_report.py:mock supports_vision=False→template;(vl)llm 注入成功/超时异常→'vl'/'template' 标记、模板规则触发文案;**AC-4→test_template_fallback_on_vl_fail+test_no_vision_direct_template** | R-4 |
| 6 | 端点+迁移+单测 | P4 | modules/pose-api.md | routes/chat.py 新端点;chat_service.save_assistant_message 默认参扩展;Message.extra 列+_ensure_extra_column 幂等;tests/test_pose_api.py:monkeypatch analyze_video——正常200(body 键全+消息落库 extra 可解)/bad_magic400/PoseQualityError 各 reason→400 文案含指引/no_model 503/报告异常仍 200 template;**AC-2→test_reject_*;AC-6→caplog 断言 evt=pose.analyze ok/fail 各1;AC-5→全量 pytest 零回归(含 test_video 全绿)** | R-5 |
| 7 | 前端双端+构建断言 | P5 | modules/pose-front.md | request.js analyzeVideoPose;MobileView/ChatView 按钮+引导+态;frontend/scripts/r017_check.mjs(先 build 后断言,dist 签名唯一+旧产物负对照登记);**AC-3(前端面)→r017_check 渲染断言(dist HTML 含 pose 按钮串+analyzeVideoPose 编译签名)+真机实拍见 step 8**;验证:r017_check 全绿+r016/14/15_check 零回归 | - |
| 8 | 真机活体验收 | 全部 | plan.md, requirements.md AC表 | 真人侧跑视频实拍(用户手机→/m)+合成视频(API 活体)双路:cadence∈140~220、骨架帧回显 200、report_source 记录、截图/DOM 渲染证据存 R-017/run-evidence/;**AC-1→test_cadence_range(离弦夹具)+实拍对账;AC-3→实拍对账+回显200+截图**;AC-4 活体补测:临时切非 VL 模型跑一发;验证:全量 pytest + 检查单入档(真实视频豁免单测声明)| R-3 |

## AC→用例映射汇总
AC-1:{3:test_metrics_sine_cadence(离线), 8:实拍对账} ; AC-2:{6:test_reject_bad_magic/low_conf/no_cycles/body_too_small} ;
AC-3:{7:r017_check dist 断言, 8:实拍+回显200+渲染证据(OPT-011:截图入 run-evidence)} ;
AC-4:{5:2 用例, 8:活体切模型} ; AC-5:{3~7 各步全量 pytest, 8:终态全量} ; AC-6:{6:caplog}。

## 豁免声明
- 步骤 1:纯文档核对;步骤 8 真实跑步视频依赖真人实拍,无法进 CI,豁免单测、以
  检查单+run-evidence 承担。其余步骤均含 pytest。

## 总结节(执行后回填)
(待执行)
