需求: R-008 | 代码分析(需求前置)

## A-1 多模态(图片)接入面摸底 — 2026-09-11
- 状态: confirmed | 用途:支撑 R-008 全部分 FR 的可行性与改动点定位
- 问题: 系统现状是否有多模态能力?本地 Ollama vision 是否可用?图片进入对话链路需要动哪些面?
- 检索范围: core/llm.py, services/chat_service.py, app/api/v1/routes/chat.py, models/sql_models.py, core/model_manager.py, core/security.py, tests/fakes.py, frontend/src/pages/ChatView.vue, frontend/src/stores/chat.js;实机 /api/show、/api/chat

### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [CODE] | core/llm.py:61-71(chat)/:174-188(chat_stream) | payload={"model","messages",...},messages 直传,若消息含 `images` 字段则自然透传(Ollama 协议字段) |
| 2 | [CODE] | services/chat_service.py:340-345 | `to_chat_messages`:`{"role": m["role"], "content": m["content"]}` 仅 role/content,历史图片信息丢失点 |
| 3 | [RUN] | /api/show metalspork/qwen3.8-flash-next-ud | `Capabilities: tools/thinking/completion/vision` + Projector clip 448.93M;qwen3.8:27b-bf16 与 bge-m3 vision tensors=0 |
| 4 | [RUN] | /api/chat images=[红蓝双色带b64] | "上半部分是红色，下半部分是蓝色。"(4.3s) |
| 5 | [CODE] | app/api/v1/routes/chat.py:34-40 | ChatRequest 仅字符串字段,无图片入口 |
| 6 | [CODE] | models/sql_models.py:250-258 | Message 无图片列 |
| 7 | [CODE] | core/model_manager.py | 模型能力仅前缀启发(CHAT_MODEL_PREFIXES),无 vision 探测;TTL 缓存模式已有(_avail_flag,R-006) |
| 8 | [CODE] | tests/fakes.py:160-163 dispatch | 仅 /api/tags|/api/chat|/api/embed|/api/embeddings,无 /api/show(新端点需补桩) |
| 9 | [CODE] | frontend/src pages/ChatView.vue:250-272 stores/chat.js:140-146 | n-input textarea + payload{session_id,content,...},图片无 UI 入口 |
| 10 | [RUN] | ollama list + df | 主对话模型支持视觉、磁盘余量 2.7T;无 whisper/ffmpeg(语音/视频期需装依赖) |
| 11 | [CODE] | core/security.py:27-39 | sanitize_input 为文本注入/长度策略;二进制内容不适用,图片安全依赖类型校验+落盘隔离 |

### 结论
| # | 结论 | 依赖证据# |
|---|---|---|
| C1 | Ollama chat 协议原生支持 messages[].images[].base64,V1 零推理侧改造可行 | 1,4 |
| C2 | 需打通面:请求模型字段→落盘→Message.images 列→to_chat_messages 窗口透传→回显端点→前端 UI | 2,5,6,9 |
| C3 | vision 能力可按 /api/show capabilities 检测(非前缀启发),需 model_manager 扩展+fakes 补桩 | 3,7,8 |
| C4 | 语音/视频本地基建(ASR/ffmpeg)缺失,全模态 V1 范围锁图片,语音/视频分 R-009/R-010 | 3,10 |

### 假设
- 无
