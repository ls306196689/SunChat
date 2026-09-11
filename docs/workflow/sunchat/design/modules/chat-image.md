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

## 附录:视频输入(R-010 追加)
- `POST /api/v1/chat/video/frames`(multipart)→ `{data:{frame_ids, count, duration}}`:
  魔数白名单 mp4/mov(ftyp)/avi(RIFF)/webm(EBML)/flv,≤VIDEO_MAX_MB(50);
  PyAV 均匀采样 ≤VIDEO_MAX_FRAMES(4)(seek 只解目标帧,时长缺失降级顺序解码),
  帧 JPEG q82 以 `{uuid}.jpg` 落 CHAT_IMAGE_DIR → **完全复用本模块回显/窗口/vision 链路**;
- 帧与普通图片在消息中无差别(D-601);音轨丢弃(D-603,音频走 speech-in);
- 前端 🎬 抽帧结果并入 pendingImages(同一 ≤4 额度)。

## 附录二:交互 UI(R-011 追加)
- 待发图状态机:uploading(本地 objectURL 乐观预览+spin)/done/error(重试原地重传);
  仅 done 计入发送,uploading 拦截发送,error 可忽略或重试;计数徽章 n/4。
- 拖拽:dragenter/leave 计数遮罩(Files 类型判定,防子元素抖动)。
- 历史/气泡图片:n-image-group 灯箱(懒加载、组内切换、缩放),不再跳新标签。
- objectURL 在 移除/发送成功/页面卸载 三路径 revoke。
