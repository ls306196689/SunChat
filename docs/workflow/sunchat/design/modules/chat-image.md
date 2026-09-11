需求: R-008 | 聊天图片通道(chat-image)

> 多模态 V1 基线能力(R-008 归档回写,2026-09-11)。对话图片输入/存储/回显。

## 对外接口
- `POST /api/v1/chat/images`(multipart file)→ `{data:{image_id}}`;
  png/jpg/gif/webp 魔数校验、≤CHAT_IMAGE_MAX_MB(8)、uuid 命名、扩展名派生自魔数。
- `GET /api/v1/chat/images/{image_id}` → FileResponse;id 严格 uuid 正则+扩展名白名单
  (非法 400/缺失 404)。
- `POST /api/v1/chat/messages`、`POST /api/v1/chat/stream`:请求体增
  `images: List[str] = []`(image_id;≤4/消息;非法/缺失 400 前置校验,流式在 SSE 前)。
- `GET /chat/sessions/{id}/messages` 响应项含 `images: [image_id]`。
- `ChatService.process_message/stream_reply/to_chat_messages` 增 `images` 参数;
  `ModelManager.supports_vision(model)`(TTL 300s)。

## 窗口注入规则(to_chat_messages)
- 当前消息:全部附图 → base64;
- 历史:最近 CHAT_IMAGE_WINDOW_MSGS(3)条带图 user 消息、每条 ≤4、
  总 ≤CHAT_IMAGE_TOTAL_MAX(8,含当前);base64 读取缓存 60s;
- 模型非 vision(`/api/show` capabilities)→ 全部 strip+WARNING;
- 时序:build_context 先于 save_user_message,history 不含当前消息(无去重需求)。

## 安全
- id 校验 `^[0-9a-f-]{36}\.[a-z]{3,4}$`+扩展名白名单双保险(D-403);
  URL traversal 由路由层规范化(400/404);
- 客户端 filename 不可信:扩展名/存储名源自魔数;
- 图片仅对话存储,不进向量库/记忆(边界)。

## 遗留(后续需求候选)
- 图片存储生命周期清理(R-2);agent 端点带图;(R-009 语音、R-010 视频为全模态分期)。
