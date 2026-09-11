需求: R-009 | 语音输入(speech-in)

> 多模态 V2 基线能力(R-009 归档回写,2026-09-11)。本地 ASR:录音→转写→输入框确认。

## 对外接口
- `POST /api/v1/speech/transcribe`(multipart file)→ `{data:{text, language, duration}}`;
  魔数白名单 wav/mp3/m4a/ogg/webm、≤SPEECH_MAX_MB(20)、run_in_threadpool(不阻塞事件循环)。
- `GET /api/v1/speech/status` → `{data:{status: pending|loading|ready|unavailable, model_size}}`。

## ASR 引擎(core/asr.py)
- faster-whisper 懒加载单例:锁双检(并发仅加载一次)、加载失败缓存(显式 clear_error 才重试);
- `local_files_only=True`:模型必须预置于 WHISPER_MODEL_DIR(data/whisper-models),
  运行期零网络(D-502);size 经 WHISPER_MODEL_SIZE 环境变量(base 默认,int8/cpu);
- 依赖 requirements:faster-whisper(av 自带音频解码,无需系统 ffmpeg)。

## 交互(确认式,D-501)
- 🎤 MediaRecorder(用户授权麦克风)→ 停止 → 自动 POST 转写 → 文本追加进输入框
  (可编辑)→ 用户发送;不支持 MediaRecorder 则隐藏;空识别 warning。
- 转写文本即普通消息文本进入既有对话链路(零 LLM 侧改动)。

## 部署注记
- 模型一次性预置(HF_ENDPOINT=hf-mirror.com 下载 Systran/faster-whisper-base 至
  WHISPER_MODEL_DIR);缺失时 /speech/transcribe 503、status unavailable。
- 隐私:录音纯本地处理,零外传。

## 遗留
- 真人语音识别率评估(交互层,前端实机);流式 VAD/TTS 语音回复(后续需求候选)。
