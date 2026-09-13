
## 步骤1 基线核对 (非缺陷记录,计划内核对清单)
- [OK] R-010 端点现状=chat.py:161 frames 零改动可行 (_sniff_video/VIDEO_MAX_MB 复用面确认)
- [OK] save_assistant_message 现签名 (session_id,content,tokens_used=0) [CODE :438] → 默认参扩展向后兼容成立
- [OK] ensure_schema() 已有 messages.images 幂等补列先例 [CODE sql_models.py:372] → extra 列同款落点(修正:设计文档写"_ensure_extra_column()"实际并入 ensure_schema,归档时基线以实际为准)
- [OK] model_manager.supports_vision [CODE :150]、llm.chat messages 内嵌 images [CODE chat_service.py:418] 消费面与设计一致

## D-1 step-3 _metrics NameError 't'(已 resolved)
- 复现:pytest test_7_metric_keys → core/pose.py:225 NameError
- 假设/证据:list 推导 `[t for s,_ in ic_r]` 误引用循环外变量 t;改 `[s for ...]`
- 修复后:该测试通过

## D-2 step-3 采样欠采+夹具几何(已 resolved)
- 复现:sample_frames(30fps avi, fps=20) 只得 15 帧;夹具 body_ratio 恒 0.22;膝角 132° 与断言不符
- 证据定位:整数 stride=round(30/20)=2 → 0.5×rate 欠采(非时间轴);测试夹具静态点 y=0.5
  混入 bbox、膝踝 y 不随 body_scale 缩放。采样改时间网格+漂移追赶;夹具全身联动
- 结果:9→10 全绿,全量 292 零回归

## D-cadence step-8 用户实测:步频不准(真实视频 cadence=54.4)已 resolved
- 复现:2026-09-13 17:18 真实侧跑视频 cadence=54.4(物理不可能,人在跑);
  合成"固定机位横穿跑者"夹具喂旧算法 → 141 vs 期望 312,复现失真(×2 类偏差)。
- 假设/证据链:
  H1 阈值问题 → 查算法定义,非阈值;否
  H2 世界速度法前提错误 → core/pose.py:157 `_stance_intervals` 假设"踝世界坐标低速=触地",
     仅相机跟随成立;固定机位侧拍踝全程移动 → 低速区间皆噪声 [CODE+RUN]。
     旧 test 夹具 dwell 段世界坐标同样静止,恰好不触发该缺陷(夹具镜像了错误假设)。
- 修复(D-3 设计微调,接口签名不变):
  ① _dominant_lag 髋竖直去趋势自相关估主周期;② _stance_intervals 改踝竖直信号
  y>μ+kσ 区间切 stance/IC/TO + 半步伪分合并;③ _segment 以多数侧 IC 为周期界。
  竖直法对机位横移/倾斜天然鲁棒(去趋势消倾斜)。
- 验证:新 fixture 双机位(固定横穿/跟随)cadence 恒 181.3≈180(±0.7%);
  机位无关性 test×2 入档为永久护栏;test_pose_core 12/12;全量 318+1skip 零回归。

## D-3 step-3v2 slo 主周期假阳性(已 resolved)
- 复现:AC-8 slo×4 夹具 dense 6.25fps → 髋y 自相关 lag 命中去趋势窗边(lag=3),
  半步伪分不合并,n_ic 虚增 → display cad 46.9×4=187 但 cycles 少、ssr 差。
- 证据:打印 ics 序列 gap=[0.48(假),1.44,1.28...];l0=lo*fps=1.56→2 允许窗边 lag;
  _dominant_lag 加 min_lag=3 + _segment 主周期窗 hi×slo → lag 找到真周期(≈25帧)。
- 验证:AC-8 cad=187.5(真180,rel 4.2%)∈±10%;全量绿。

## D-4 step-3v2 粗扫频带判定在 5fps 混叠死区(已 resolved,R-7 成真→按预案对策)
- 复现:走路/短跑/站立各类粗扫 lms,FFT 判跑门恒误杀或恒泄漏(run_ratio 带通 irfft
  掩码 13 点仅边缘 2 帧命中——混叠后频带不可辨识)。
- 证据:[RUN] debug 打印:跑 1.5Hz 在 5fps 下主频 bin 1.45Hz 可辨,走路 0.85Hz 混叠
  至同带;2.2s 窗 pk/md 比值受窗长截断支配(0.86~2.36 抖动),阈不可定。
- 处置(⚠R-7 预案"漏则升8fps"修正为更优路径):频带判定**移出粗扫**,粗扫只以
  raw-std 能量剔站立死段;走路等误检由密采后**终判门** cad∉[POSE_RUN_MIN_CAD,240]
  拒之 no_activity(密采 ≥20fps 带内可靠)。粗扫 5fps 保留(提速目标达成,漏检风险
  由能量门覆盖——死段判据是"无振荡"而非"频率")。
- 验证:AC-7 mixed=pure±<5%、走路 no_activity、全量 340+1skip 零回归。
