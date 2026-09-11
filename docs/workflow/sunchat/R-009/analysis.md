需求: R-009 | 代码分析(需求前置)

## A-1 语音输入(ASR)可行性与接入面 — 2026-09-11
- 状态: confirmed | 用途:支撑 R-009 方案选型与改动定位
- 问题: 本地语音转文字能力是否存在/可装?接入对话链路的形态?
- 检索范围: pip 源、huggingface 直连/镜像连通性、faster-whisper 试用、前端输入区(见 R-008 取证)

### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [RUN] | `pip index versions faster-whisper` | 1.2.1 可装;已安装 ctranslate2-4.8.2/faster-whisper-1.2.1/av-17.1.0(av 免 ffmpeg 解码音频) |
| 2 | [RUN] | huggingface.co 直连 /api/models | SSLEOFError 阻断(环境代理对 HF 域名失效) |
| 3 | [RUN] | hf-mirror.com 走代理 308 / 直连 200 | 镜像可用,模型 Systran/faster-whisper-base 经 HF_ENDPOINT=镜像后台下载至 backend/data/whisper-models |
| 4 | [CODE] | ChatView.vue 输入区(R-008 改造后) | 📎/textarea/发送按钮,pendingImages 模式可类推 pendingAudio→转写文本入输入框 |
| 5 | [REQ] | 用户澄清(2026-09-11)| "全模态大计划"三期拆分:R-008 图片(done)/R-009 语音/R-010 视频 |

### 结论
| # | 结论 | 依赖证据# |
|---|---|---|
| C1 | 本地 ASR 采用 faster-whisper(base/int8/cpu):免 ffmpeg、懒加载单例(首次~70MB 模型已在下载路径 data/whisper-models);无需 Ollama(其无 ASR) | 1,2 |
| C2 | 交互形态:语音→转写文本填入输入框供用户确认/编辑后发送(LLM 链路零改动,误识别可控) | 4 |
| C3 | 网络依赖一次性(模型下载),运行期完全离线 | 3 |

### 假设(实现期以 RUN 验证)
- ⚠假设 base 模型中文准确率可用 — 验证: R-009/AC 用真实语音样本
