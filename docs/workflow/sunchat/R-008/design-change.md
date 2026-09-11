需求: R-008 | 增量设计 | 状态: v1 | 日期: 2026-09-11

# design-change(相对基线新增:chat 图片通道)

基线 design/modules/ 无对话多模态模块;本需求新增"图片通道"能力面。归档时
回写 design/modules/chat-image.md 新基线条目(多模态 V1 基线能力)。

## 模块切分与改动点
### 1. 路由层 `app/api/v1/routes/chat.py`
- `class ChatRequest` / `StreamChatRequest` 增 `images: List[str] = []`。
- `POST /chat/images`(multipart UploadFile):读前 8 字节魔数+大小校验→
  uuid4+.ext 存 `Path(settings.UPLOAD_DIR)/"chat"`;返回 {image_id}。
- `GET /chat/images/{image_id}`:`_IMAGE_ID_RE = ^[0-9a-f-]{36}\.[a-z]{3,4}$`
  校验+扩展名白名单→FileResponse;非法→400,文件缺失→404。
- create_message/stream_chat:`_resolve_images(ids)`→存在性校验(缺失 400)→
  透传 service(非 vision 模型的 strip 在 service 层统一)。

### 2. LLM 层 `core/llm.py`
- `chat`/`chat_stream` 签名不变:messages 已是 dict 列表,`images` 键自然透传。
- 不改类型注解语义(List[Dict[str, str]] → List[Dict],避免 mypy 歧义,仅注释)。

### 3. 服务层 `services/chat_service.py`
- `save_user_message(session_id, content, images: List[str] = None)`;
  Message.images=JSON.dumps(images or [])。
- `to_chat_messages(ctx, content, images: List[str] = None)`:
  - 当前 user 消息:{"role":"user","content":content, "images":[b64...]}(仅当有图);
  - 历史窗口:ctx["history"] 中 user 消息带 `images`(get_messages 回传)时,
    仅最近 `_IMG_WINDOW_MESSAGES=3` 条带图历史消息注入,每条最多 `_IMG_PER_MSG=4`,
    总图数≤`_IMG_TOTAL=8`(超限从最旧丢弃);
  - 模型非 vision(model_manager.supports_vision(resolve_chat_model(requested)) False)
    → 全部 strip,logger.warning 一次/请求。
- base64 读取缓存:`_img_b64(iid)` TTL 60s(复用 stock 缓存语义)。
- `build_context` 签名不变(图片在生成段注入);`process_message`/`stream_reply`
  增关键字参数 `images: Optional[List[str]] = None` 透传。
- `get_messages` 响应项增 `"images": json.loads(m.images or "[]")`。

### 4. 模型管理 `core/model_manager.py`
- `supports_vision(model_name) -> bool`:POST /api/show {model} → capabilities
  含 "vision";缓存 TTL 300s(dict[name,(ts,bool)],仿 _avail_flag);不可达 False。
- `tests/fakes.py` dispatch 增 /api/show 桩(FAKE_VISION_MODELS 集合)。

### 5. 数据层 `models/sql_models.py`
- `Message.images = Column(Text, default="[]")`;
- `ensure_schema`:messages 缺列 → ALTER TABLE messages ADD COLUMN images TEXT
  DEFAULT '[]'(幂等,先例 storage_path)。

### 6. 配置 `app/config.py`
- `CHAT_IMAGE_MAX_MB: int = 8`;`CHAT_IMAGE_DIR` 派生 UPLOAD_DIR/chat。

### 7. 前端 `frontend/src`
- `utils/request.js` 增 uploadChatImage(file)(multipart)与 chatImageUrl(id)。
- `stores/chat.js`:sendMessage(content, ..., imageIds=[])→payload.images;
  消息对象带 images(发送时本地回显+历史接口回传)。
- `ChatView.vue`:输入区 📎(input file multiple)+ paste/drop 事件→上传→
  pendingImages 预览条(可删);handleSend 传 ids;MessageItem 增 imageUrls 渲染
  (img 标签 GET 端点,loading=lazy)。

## 测试设计
- `tests/test_chat_image.py`:上传合法三格式/伪造/超限/回显穿越/404、带图发消息
  payload images 断言(LAST_CHAT_PAYLOADS)、历史窗口截断、纯文字payload等价回归、
  非vision strip、supports_vision 三态+缓存计数、ensure_schema 幂等。

## 决策
- [D-401] base64 窗口注入而非全史:控 token/显存(K 上限),窗口外图只留文字。
- [D-402] 非 vision 模型自动 strip+warn(可用性优先,不报错阻断)。
- [D-403] 图片存储 uuid 命名+扩展名白名单,回显 id 严格正则,双保险防穿越。
- [D-404] 本期不引入 Pillow/新依赖;魔数校验标准库实现。
- [D-405] agent 端点不接图(范围纪律,R-009 候选)。
