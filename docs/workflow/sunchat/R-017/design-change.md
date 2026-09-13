# sunchat 设计变更(R-017 跑步姿态分析)

需求: R-017 | 类型: iteration(feature on 既有基线) | 日期: 2026-09-13
基线: design/overview.md(memory-retrieval-opt r1)+ modules/chat-image.md(R-008)+ R-010 附录

状态: **v2 draft(执行中方案级变更,change_count=1)** | 修订: r1→r2
- r1 2026-09-13 初版设计(冻结门禁后)
- r2 2026-09-13 变更:抽帧方案重做(真实帧率探测/关键段定位/段内密采/关键区域裁剪)
  + 条件性配速(FR-11);依据 analysis.md A-1/A-2/A-3(均有 RUN 证据),用户明示确认

## v2 变更摘要(为什么改)
1. 真人实测 cadence=48.6/54.4:步频分母是"检出跨度"而非"跑动段时长",手持视频
   前段站立/走位稀释全部指标 [A-1] → 必须先定位关键时间段。
2. 帧率元数据不可信(avg_rate 在 slo 容器下说谎、PyAV 无 container.time_base)
   [A-2] → 真实帧率逐帧 PTS 实测;慢动作 N 倍还原 cadence。
3. VLM 收到的是全身小图,细节糊 → 人体 bbox 并集固定裁剪框,躯干占画面 ≥60%。
4. 配速:脚钉地+腿长自标定原型端到端误差 19%(与需求 ±20% 一致)[A-3] → 条件性
   纳入,算不出显式 null。

## v2 增补需求
| 编号 | 描述 | 优先级 | 依据 |
|---|---|---|---|
| FR-8 | 探测:demux 全量 packet PTS→f_eff(中位间隔倒数)、名义fps、慢动作倍速 N=名义/f_eff∈{2,4,8}(或运动频率落[15,45]spm 物理不可能带反推)、PTS CV>0.35 标 VFR;全部进 quality 块与报告透明度行 | P1 | A-2 |
| FR-9 | 关键段定位:min(5fps,f_eff) 粗扫(256px)→踝y去趋势振荡能量×自相关周期峰×人体占比,1s滑窗→连续达标段,合并<0.3s邻段取最强≤8s;**cadence/ssr/asym 分母=跑动段**;有效段<1.5s→400 no_activity 拒析(附指引) | P1 | A-1 |
| FR-10 | 段内密采 min(25fps,f_eff),上限 POSE_MAX_SAMPLE_FRAMES=600,fast-seek 段首仅解码候选段 | P1 | A-4 |
| FR-11 | 条件性配速:固定机位检测(段内髋x跨度≥0.8×身高px)+POSE_USER_HEIGHT_CM>0 时:腿长px(髋-膝+膝-踝,帧中值)→米/像素;钉地落点(踝x低速∩y低位)相邻距中值→步长;v=步长×cad/60,km/h 与配速 min/km;慢动作未还原前不得计;任一前提不满足→pace=null+原因字符串 | P2 | A-3 |
| FR-12 | 关键区域:段内关键点 bbox 并集+10%margin→唯一裁剪框(短边<256px 则整帧),骨架帧画在裁剪图上报 VLM;落盘帧=裁剪版 | P1 | 用户会话 |

## v2 AC 增补
| 编号 | 标准 | 验证 |
|---|---|---|
| AC-7 | 夹具前段站立3s+跑3s 与纯跑段 cadence 差≤5%(稀释回归永久护栏) | pytest 夹具 |
| AC-8 | slo 形态夹具(PTS拉长4×)cadence 还原到真实值±10%,quality.slo_factor=4 | pytest 夹具 |
| AC-9 | pace 三态:固定机位夹具 v 误差≤25%;跟随机位=null+原因;身高未配=null | pytest 夹具 |
| AC-10 | 落盘骨架帧为裁剪版(bbox 内像素占该帧≥50%) | pytest |

## 模块变更定位
| 模块 | v2 改动 |
|---|---|
| P1 pose-core | 新增 probe_frames()(FR-8)、locate_activity()(FR-9)、pace()、analyze_video 内部改为 probe→locate→密采→段内事件(签名不变,返回加 quality.fps_eff/fps_nominal/slo_factor/activity_span/pace|None/pace_reason) |
| P2 pose-skeleton | draw_skeleton 增可选 crop_bbox 参数(默认 None=旧行为) |
| P3 pose-report | 报告透明度行(fps/段/裁剪/slo/配速);模板规则不变 |
| P4 pose-api | 帧源从"全片重解"改"按 activity 段 fast-seek 解码"(P1 已含);no_activity 拒析映射 |
| P5 pose-front | 无结构改动(报告文本自动携带透明度行) |
| config | +POSE_COARSE_FPS=5 POSE_DENSE_FPS=25 POSE_MAX_SAMPLE_FRAMES=600(改) POSE_ACTIVITY_MIN_SEC=1.5 POSE_USER_HEIGHT_CM=0 POSE_SLO_RESTORE=true |

## 步骤重置计划(门禁通过后)
- step-3 重置 pose-core v2(probe+locate+dense+pace,含 AC-7/8/9 夹具)→ step-4 小改
  (crop)→ step-5 小改(透明度行)→ step-6 端点 no_activity 映射+重跑全量 →
  step-8 重启+真人复测(用户实拍对账 48.6 修复)。
- 已 done 的 steps 1/2/7(依赖/骨架/前端)不重置;AC-5 全量回归并入重置后各步验证。

## 风险表 v2(增 R-7~R-10,同步 state)
| id | 描述 | 概率 | 影响 | 缓解 | 状态 |
|---|---|---|---|---|---|
| R-7 | 粗扫5fps 髋2f 奈奎斯特临界,高速碎步漏检 | 中 | 中 | 夹具断言不漏检;漏→8fps(代价+2s) | open |
| R-8 | 身高配错→配速线性失真 | 中 | 中 | 报告打印所用身高;未配置即 null | open |
| R-9 | 机位倾斜/俯拍→水平像素距失真 | 低 | 低 | 髋连线角>15° 判"非水平机位"→pace=null | open |
| R-10 | VFR 转码视频时基不匀 | 低 | 低 | PTS CV>0.35 quality 标 vfr 降级注记 | open |

(修订记录 r1 风险表 R-1~R-6 状态不变,R-6 关闭原因:段解码后初始化单例摊销进一步下降)
