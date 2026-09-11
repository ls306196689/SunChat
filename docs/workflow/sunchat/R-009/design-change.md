需求: R-009 | 增量设计 | 状态: v1 | 日期: 2026-09-11

# design-change(相对基线新增:speech-in 通道;归档回写 design/modules/speech-in.md)

## 后端
### `core/asr.py`(新增,仿 model_manager 惰性+锁模式)
- `ASRService`:`_lock` double-check 懒加载 WhisperModel(size=WISPER_MODEL_SIZE,
  device=cpu,int8,download_root=WHISPER_MODEL_DIR,local_files_only=True
  ——模型缺失不下载直接不可用,R-009 网络边界);
- `status() -> "ready"|"loading"|"unavailable"`;
- `transcribe(audio: bytes) -> {"text","language","duration"}`;
  内部 BytesIO + av 解码;异常向上抛(路由转 4xx/5xx);
- 全局单例 `asr_service`。

### `app/api/v1/routes/speech.py`(新增)
- `POST /speech/transcribe`:multipart;读 ≤ SPEECH_MAX_MB(20)+1;魔数白名单
  RIFF..WAVE / OggS / ftyp@4 / EBML(webm);不匹配 400;status loading→503;
  转写空→200 {text:""};
- `GET /speech/status`:{ready, model_size}。
- 注册进 main.py router。

### `app/config.py`
- `WHISPER_MODEL_SIZE: str = "base"`;`WHISPER_MODEL_DIR: str = str(DATA_DIR/"whisper-models")`;
  `SPEECH_MAX_MB: int = 20`。

### 测试
- `tests/test_speech.py`:mock ASRService.transcribe/status 契约矩阵(AC-1/3/4)+
  真实模型标记 skipif 模型缺失(AC-2 实机 E2E 手工记录)。

## 前端
- `utils/request.js`:`transcribeSpeech(blob)`(FormData "file")、`speechStatus()`。
- `ChatView.vue`:`useRecorder` 内联逻辑:🎤 按钮(录音计时/停止)、MediaRecorder
  (mimeType 优先 audio/webm;audio/mp4;探测不支持则隐藏)、停止→
  transcribeSpeech→输入框追加文本(前插空格保护已有文本)、状态(录音中/转写中/
  模型加载/错误 toast)。
- 探测 `window.MediaRecorder` 不可用 → 隐藏 🎤。

## 决策
- [D-501] 确认式交互(转写回填输入框,不自动发送):误识别可控、保留编辑权。
- [D-502] local_files_only=True:模型必须预置(部署文档),运行期禁下载(纯本地原则)。
- [D-503] base/int8/cpu 默认:内存与延迟平衡;size 走环境变量可升配。
- [D-504] webm 优先 MediaRecorder,av 解码;失败场景 wav 兜底(AC-5 实机定夺)。
