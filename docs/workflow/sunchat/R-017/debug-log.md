
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
