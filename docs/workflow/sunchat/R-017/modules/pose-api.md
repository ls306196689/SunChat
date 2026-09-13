# 模块设计:pose-api(app/api/v1/routes/chat.py 内新端点)

需求: R-017 | 触发: FR-1,3,4,5;CH-1,CH-7 | 日期: 2026-09-13 | 状态: draft r1

## 对外接口
```
POST /api/v1/chat/video/pose   (multipart: file=视频, session_id: int 表单字段)
→ 200 {"code":200,"data":{"report":str,"report_source":"vl|template",
        "frame_ids":[...], "metrics":{...},"quality":{...},"message_id":int}}
→ 400 {"detail": 拒析文案(含拍摄指引)}  reason∈{bad_magic, oversize, low_conf,
        no_cycles, body_too_small}
→ 413 视频超 VIDEO_MAX_MB(复用 R-010 判定) → 503 模型文件缺失
```

## 能力说明
- 提供:HTTP 编排层——校验→P1(线程池)→门槛异常翻译→P2 帧落盘→P3 报告→
  assistant 消息落库(指标 JSON 入新 extra 列)→聚合日志。
- 不提供:算法(P1)、绘制(P2)、报告内容(P3);不新增回显端点(复用
  GET /chat/images/{id})。

## 内部关键逻辑
1. 接收校验复用 `_sniff_video` + VIDEO_MAX_MB 读取模式(R-010 同款 [CODE chat.py:161])。
2. `PoseQualityError` → 400,detail = reason 映射文案 + 拍摄指引(决策 D-001:文案
   含"路跑:侧方可视 5~8m 架机跑过正面/跑步机:侧面平行跑带"两句通用)。
3. 落盘帧:uuid+.jpg 写 CHAT_IMAGE_DIR(同 R-010 帧约定 [CODE chat.py:192])。
4. P3 入参:metrics + base64(读刚落盘帧)→ 报告文本;P3 任何未捕获异常兜底
   template_report(API 层再包一层 try——报告永不使请求 5xx)。
5. 落库:`chat_service.save_assistant_message` [CODE chat_service.py:438] **扩展**(追加
   关键字默认参 `images=None, extra=None`,既有调用方零改动,向后兼容),extra=
   json(metrics+quality+report_source);messages 表 `extra TEXT` 列:启动期
   `_ensure_extra_column()` 幂等 ALTER PRAGMA 检列(R-004 惯例,R-5 缓解)。
6. **日志**:单请求一条聚合 `evt=pose.analyze result=ok frames=N cycles=N cadence=...
   infer_ms=... skeleton=4 report=vl|template total_ms=...`;fail→ERROR+reason。
7. 线程池:`run_in_threadpool(P1.analyze_video)`,P2/P3 同函数顺序执行(请求内串行,
   总预算超时由前端 180s 兜底)。

## 依赖
- P1 `analyze_video`/`PoseQualityError`;P2 `select_key_frames`/`draw_skeleton`;
  P3 `build_report`;chat_service `save_assistant_message`(本需求新增接口)。
- 文档路径:R-017/modules/pose-{core,skeleton,report}.md。
