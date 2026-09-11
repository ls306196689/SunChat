需求: R-010 | 增量设计 | 状态: v1 | 日期: 2026-09-11

# design-change(相对基线:视频→帧转换;归档回写 design/modules/chat-image.md 附录)

## `core/video.py`(新增,复用 av+Pillow,无系统 ffmpeg 依赖)
- `extract_frames(data: bytes, max_frames: int = None) -> List[Tuple[bytes, float]]`:
  - `av.open(BytesIO)` 容器探测;取 `streams.video[0]`;
  - 时长优先 `container.duration*time_base`,退化用 `stream.frames/time_base`;
  - 目标时间戳 `ts_i = duration*(i+0.5)/N`(均匀,避开首尾黑帧);
  - 每目标 `container.seek(int(ts/time_base))` 后解码最近帧(仅解 N 帧,控耗时);
  - `frame.to_image()` → JPEG q=82 → bytes;(jpeg_bytes, ts) 收集;
  - 任何环节 0 帧/异常 → `ValueError`(路由 400)。
- av 懒 import(仿 asr),避免影响无视频场景启动。

## 路由 `app/api/v1/routes/chat.py`(挂既有 chat 前缀,复用图片域)
- `POST /chat/video/frames`:multipart file;魔数白名单
  (RIFF+AVI / ftyp@4 / EBML \x1aE\xdf\xa3 / FLV);≤VIDEO_MAX_MB(50)
  → run_in_threadpool(extract_frames) → 逐帧 uuid+".jpg" 存 CHAT_IMAGE_DIR
  (与 R-008 同目录,回显/窗口/清理零改动)→ `{frame_ids, count, duration}`;
  0 帧→400。

## config
- `VIDEO_MAX_MB: int = 50`、`VIDEO_MAX_FRAMES: int = 4`。

## 前端 `ChatView.vue`
- 🎬 按钮:input accept="video/*" → 大小说明 50MB →
  `uploadVideoFrames(file)`(request.js 新增,POST multipart)→
  对每个 frame_id `pendingImages.push({id, url: chatImageUrl(id), name:'帧'+ts})`;
  帧计入 ≤4 张上限(已满则提示);错误 toast 同 R-008 模式。

## 测试
- `tests/test_video.py`:extract_frames 合成 avi(帧数/jpeg魔数/时间戳递增/损坏
  ValueError);端点矩阵(200 frame_ids 可回显、非视频 400、超限 413、0帧 400,
  mock extract 分支+真实管线各覆盖);既有 test_chat_image 全回归(AC-4)。

## 决策
- [D-601] 视频不建第二存储域:抽出的帧即普通 chat image(uuid.jpg),
  发送/历史/vision 零新代码;原视频不保存(边界)。
- [D-602] 均匀采样 N=4:vision 窗口上限(token/显存,与 CHAT_IMAGE_MAX_PER_MSG 对齐);
  seek 定位只解目标帧,规避长视频全量解码。
- [D-603] 音轨丢弃:音频理解走 R-009 用户自发语音(范围纪律)。
