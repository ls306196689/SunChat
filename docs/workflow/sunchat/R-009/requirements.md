需求: R-009 | 类型: iteration | 状态: v1 已授权 | 日期: 2026-09-11 | 版本: v1

# R-009 语音输入(多模态 V2:语音转文字)

## 1. 背景与历史
全模态三期第 2 期(R-008 图片已交付)。本机 Ollama 无 ASR 能力(analysis A-1),
选型本地 faster-whisper(base/int8/cpu,免 ffmpeg,A-1/C1),模型经 hf-mirror 一次性
下载至 backend/data/whisper-models(运行期完全离线)。

## 2. 与历史需求的关系
- 不改变对话链路:语音在前端/后端转写为文本,LLM 侧零感知(A-1/C2);
- 复用 R-008 的 multipart 上传模式与安全面扩展(音频同样魔数+大小限制)。

## 3. 核心场景
1. 用户点 🎤 → 录音 → 再点停止 → 自动转写文本填入输入框 → 可编辑 → 发送。
2. ASR 转写正确(中文普通话,base 模型;误识别由用户编辑兜底)。
3. 首次调用模型加载中 → 503 loading 提示,前端显示"语音模型加载中…"。
4. 浏览器不支持 MediaRecorder → 🎤 隐藏/禁用。

## 4. 功能点
- FR-1 `core/asr.py`:WhisperModel 懒加载单例(锁保护,double-check),
  模型目录 settings.WHISPER_MODEL_DIR(默认 data/whisper-models,
  环境变量 WHISPER_MODEL_SIZE=base 可调);transcribe(bytes) → {text, language}。
- FR-2 `POST /api/v1/speech/transcribe`(multipart):魔数白名单
  (RIFF..WAVE / OggS / ftyp MP4/M4A(webm 容器走 av,魔数 "1A 45 DF A3" EBML))
  + ≤20MB → ASR 文本;未就绪 503;解码失败/空音频 400/空 text。
- FR-3 `GET /api/v1/speech/status`:ready/loading/unavailable + model size。
- FR-4 前端 🎤(MediaRecorder):录音状态、计时、停止→POST 转写→
  文本追加进输入框;loading 期间提示;错误 toast。
- FR-5 依赖:faster-whisper 已安装并写入 requirements.txt(av 随带解码,
  无需系统 ffmpeg)。

## 5. 边界与非目标
- 不做流式 ASR/VAD 断句、不做说话人分离;不做 TTS 语音回复(候选后续);
- 不做视频(R-010);模型仅 base(int8,cpu;大模型留 config 切换);
- 语音不经图片同款"窗口"逻辑(转写即文本,天然入历史)。

## 6. 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | 合法 wav 转写返回 text 字段;桩掉 ASR 时端点契约测试(200/400/503 分支) | TestClient(mock asr) |
| AC-2 | 真实 base 模型:合成/真实音频转写中文可用(实机 E2E) | RUN 记录 |
| AC-3 | 模型未就绪 → 503(不崩溃);懒加载并发安全(双线程仅加载一次) | mock 单测 |
| AC-4 | 非音频魔数 400;>20MB 413 | TestClient |
| AC-5 | 浏览器 MediaRecorder webm(opus)经 av 可解码;否则前端转 wav 兜底(实现期 RUN 判定) | RUN |
| AC-6 | 全量回归绿 | pytest |

## 7. 风险
| id | 风险 | prob | impact | 缓解 |
|---|---|---|---|---|
| R-1 | base 模型中文准确率不足 | 中 | 中 | 用户编辑兜底(确认式交互);WHISPER_MODEL_SIZE 可升 small |
| R-2 | 首次加载~数秒阻塞请求 | 中 | 低 | 懒加载+loading 状态+503;进程预热可选 |
| R-3 | opus/webm 解码不可用 | 低 | 中 | 前端 WebAudio 转 wav 16k 兜底(AC-5 判定) |
| R-4 | 录音隐私 | 低 | 中 | 纯本地处理,不上传外部;README 注记 |
| R-5 | 内存占用(ctranslate2+模型 int8 ~ 数百MB) | 低 | 低 | 本地单机可接受;int8 已最小化 |
