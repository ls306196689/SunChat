需求: R-008 | 类型: iteration(新功能) | 状态: v1 已授权 | 日期: 2026-09-11 | 版本: v1

# R-008 对话图片输入(多模态 V1:图片问答/历史回显)

## 1. 背景与历史
多模态全模态三期规划的第 1 期(用户要求"全模态大计划",但语音/视频依赖
whisper/ffmpeg 未装,R-009/R-010 分期;本期纯打通图片链路,R-008 零新依赖——
PIL 校验亦不做,用标准库魔数,保持 requirements.txt 不变)。
本地主对话模型 metalspork/qwen3.8-flash-next-ud 原生 vision(clip projector,
实机验证 4.3s 正确识别双色带,analysis A-1/4)。

## 2. 核心场景
1. 前端粘贴/选择一张图片 → 发送"这张图里有什么" → AI 基于图像内容回答。
2. 历史会话中的图片消息可回显(点开/刷新后仍在)。
3. 多轮追问图片内容:当前请求带最近 K 张历史图片(窗口),避免重复 base64 爆 token。
4. 纯文字消息零影响:接口向后兼容,images 缺省时与现状逐字节等价。

## 3. 功能点
- FR-1 图片上传:`POST /api/v1/chat/images`(multipart)接收 png/jpg/jpeg/gif/webp,
  **标准库魔数校验**(PIL 不在 requirements.txt,不引入新依赖):
  png `\x89PNG` / jpeg `\xff\xd8\xff` / gif `GIF8` / webp `RIFF????WEBP`;
  限 MAX 8MB/张(uuid 命名,扩展名白名单,存 UPLOAD_DIR/chat/;仿 KB 上传安全面
  knowledge.py:44)。
- FR-2 `GET /api/v1/chat/images/{image_id}`:回显(按存储文件名白名单 uuid 校验,
  防路径穿越),FileResponse。
- FR-3 ChatRequest 增 `images: List[str] = []`(image_id 列表,≤4 张/请求):
  校验每个 id 合法(uuid正则+扩展名),文件必须存在否则 400。
- FR-4 `Message.images`:Text 列存 JSON 列表 `["<image_id>", ...]`;
  `ensure_schema` 补列(幂等 ALTER,migration 先例:storage_path);
  get_messages/list 响应回传 images 字段。
- FR-5 `to_chat_messages`:当前 user 消息带全部附图 base64;
  最近窗口(history 内 user 消息)各带最近 K 张图(K=4,窗口=该会话最近 3 条带图消息),
  base64 读取缓存 TTL 60s(同 stock 语义)。模型非 vision 时→自动 strip 图片并 warn。
- FR-6 `model_manager.supports_vision(model)`:Ollama /api/show capabilities
  检测,缓存 TTL 300s(仿 R-006 模式);fakes 补 /api/show 桩。
- FR-7 前端:ChatView 输入区增 📎 按钮/粘贴/拖拽上传,缩略图预览(可删),
  随消息发送 image_ids;消息气泡显示历史图片缩略图(GET 端点回显);SSE/非流式
  payload 带 images 字段。

## 4. 边界与非目标
- 语音/视频识别(R-009/R-010,需用户装 ffmpeg/whisper);vision 输出图不可行;
- 图片不入向量库/记忆(仅对话上下文);不做图片压缩(8MB 限制兜底);
- 不做多模态 Agent 工具(agent /chat/agent 暂不接图;下一期候选)。

## 5. 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | 上传 png/jpg/webp → 200+image_id;伪造扩展名(.txt)拒绝;>8MB 413;非图魔数 400 | TestClient |
| AC-2 | GET /chat/images/{id} 200+Content-Type 正确;非 uuid id → 400;不存在 → 404 | TestClient |
| AC-3 | 带图消息:LLM payload messages 末条 user 含 images[base64](长度与源文件 b64 一致);图片入库 JSON;get_messages 回传 images | TestClient + spy LAST_CHAT_PAYLOADS |
| AC-4 | 历史窗口:image 历史消息按窗口注入 base64,超限(>K)截断;窗口外不注入 | spy 单测 |
| AC-5 | 纯文字请求 payload 与改造前等价(无 images 键);非 vision 模型自动 strip 图片+warning | spy 单测 |
| AC-6 | supports_vision:vision 模型 True / 非 vision False / 不可达 False;TTL 内缓存(桩计数) | 单测(fakes /api/show) |
| AC-7 | ensure_schema 对存量缺列库幂等补列(建库→删列思路不可行,验证重复执行无害+新列生效) | 单测 |
| AC-8 | 全量回归 `pytest tests/` 全绿(含前端文件改动不破坏 build:如环境可,`npm run build` 校验) | 命令 |

## 6. 风险(概览,详 state.risks)
| id | 风险 | prob | impact | 缓解 |
|---|---|---|---|---|
| R-1 | base64 大窗爆 token/显存 | 中 | 中 | 窗口硬上限 K=4 张×≤3条消息;超限截断(AC-4) |
| R-2 | 图片落盘目录膨胀 | 中 | 低 | 本期仅记录问题不做清理(登记遗留);8MB/张限制 |
| R-3 | 非 vision 模型收到 images 字段报错 | 低 | 中 | supports_vision 探测+自动 strip(AC-5) |
| R-4 | 旧前端不传 images 字段 | 低 | 低 | pydantic 默认 `images: List[str]=[]` 向后兼容 |
| R-5 | 路径穿越/存储名伪造 | 低 | 高 | id 严格 uuid 正则 + 落盘文件扩展名白名单双校验(AC-2) |
