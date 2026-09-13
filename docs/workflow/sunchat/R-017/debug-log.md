
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
