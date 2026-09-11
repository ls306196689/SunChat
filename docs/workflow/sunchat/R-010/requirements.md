需求: R-010 | 类型: iteration | 状态: v1 已授权 | 日期: 2026-09-11 | 版本: v1

# R-010 视频输入(多模态 V3:视频抽帧问答)

## 1. 背景与历史
全模态三期第 3 期(R-008 图片/R-009 语音已交付)。本机无系统 ffmpeg,但 PyAV
(随 faster-whisper 安装)自带编解码,抽帧可行(analysis A-1/C1)。方案:
**视频→均匀抽帧→帧图复用 R-008 图片通道→vision 模型看图回答**——不引入
视频专用理解模型,Ollama vision 对关键帧的回答覆盖"视频里发生了什么"类问题。

## 2. 与历史需求的关系
- 完全复用 R-008 chat-image 基线(image_id 存储、Message.images、窗口注入、
  回显端点、vision 探测):后端仅新增"视频→帧"转换,前端仅新增一个 🎬 入口;
- 语音(R-009)可选组合:同一条消息图+音,LLM 看帧、语音转文字进文本,天然并行。

## 3. 核心场景
1. 用户点 🎬 选一段 mp4 → 后端均匀抽 ≤4 关键帧 → 缩略图进待发送区(与图片同区)→
   发送 → AI 基于关键帧回答("这视频里有什么/发生了什么")。
2. 历史消息回显:帧图与手工图片完全一致(R-008 回显链路)。
3. 超时限大视频 → 413;非视频文件 → 400;解码失败(损坏/DRM)→ 400。

## 4. 功能点
- FR-1 `core/video.py`:`extract_frames(bytes, max_frames=VIDEO_MAX_FRAMES) ->
  List[(jpeg_bytes, ts)]`;av 容器探测→时长→均匀取点→解码最近帧→JPEG(q=82);
  时长不可得时取前 N 个可解码帧;失败 raise ValueError。
- FR-2 `POST /api/v1/chat/video/frames`(multipart):魔数白名单(mp4 ftyp/avi
  RIFF.AVI/webm EBML/flv FLV/mov 亦 ftyp)+ ≤VIDEO_MAX_MB(50)→ 抽帧 →
  逐帧存 CHAT_IMAGE_DIR(uuid,扩展名 .jpg)→ `{frame_ids,count,duration}`;
  0 帧→400。落盘复用 R-008 目录→回显/窗口零改动。
- FR-3 config:`VIDEO_MAX_MB:int=50`、`VIDEO_MAX_FRAMES:int=4`。
- FR-4 前端 🎬:选视频(accept video/*)→POST frames→帧缩略图 push 进
  pendingImages(与 R-008 同区同删除逻辑,计入每消息 ≤4 图上限)。

## 5. 边界与非目标
- 不做音轨提取(音频→R-009 端点;组合=用户先视频后语音,或后续需求做容器内音轨)、
  不做逐帧 OCR/视频专用模型、不做实时流(RTSP/摄像头)、不转码存储原视频;
- 音频轨丢弃(本期范围纪律)。

## 6. 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | `extract_frames`(合成 avi 3s):返回 ≤4 帧 jpeg(b'\xff\xd8\xff'),时间戳递增 | 单测 |
| AC-2 | `POST /chat/video/frames`:真实/合成视频 → frame_ids 可经
  GET /chat/images/{id} 回显(200 image/jpeg);真实手机录屏 mp4 实机 E2E | TestClient+RUN |
| AC-3 | 0 帧/损坏/非视频 → 400;>50MB → 413 | TestClient |
| AC-4 | 帧入消息:frame_ids 当 images 发送,payload/落库/回显 = R-008 行为(复用回归) | 既有 test_chat_image 回归全绿 |
| AC-5 | 全量回归 `pytest tests/` 全绿 + vite build 通过 | 命令 |

## 7. 风险
| id | 风险 | prob | impact | 缓解 |
|---|---|---|---|---|
| R-1 | 均匀抽帧错过关键内容 | 中 | 低 | N=4 上限是 token 权衡(frame_ids 全部给模型);用户可补发截图 |
| R-2 | 长视频解码慢/内存 | 中 | 低 | seek 到目标时间只解目标帧(av seek)+50MB 上限;超时由代理层 300s 容忍 |
| R-3 | 浏览器/手机编码格式覆盖不全 | 低 | 中 | 白名单 ftyp(安卓/iPhone mp4)+avi+webm;av 覆盖主流;失败 400 明示 |
