
需求: R-009 | plan(标准 iteration,总授权直通)

执行步骤(同 state.steps,逐步 in_progress/done):

| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | 后端 core/asr.py+speech路由+config+单测 | ASR service/路由/配置 | R-009/{requirements,design-change,analysis}.md | core/asr.py, routes/speech.py, config.py, tests/test_speech.py;验证:`pytest tests/test_speech.py` | R-2,R-3 |
| 2 | 前端 🎤 MediaRecorder+转写回填 | request.js, ChatView.vue | 步骤1契约(design-change §前端) | utils/request.js, pages/ChatView.vue;验证:`npx vite build` 退出码0 + 实机HTTP | R-1 |

## 总结节(验收归档 2026-09-11)
| AC | 结果 | 证据 |
|---|---|---|
| AC-1 | 通过 | tests/test_speech.py TestTranscribeContract:mock 契约矩阵(200/空text/503 RuntimeError→"未就绪"/400 ValueError→解码失败) |
| AC-2 | 通过 | TestRealModelE2E::test_pipeline_real_model PASSED(data/whisper-models 真实base模型,合成wav管线通)+实机HTTP 5s正弦wav→200 text="" language=en(无语音→空,语义正常) |
| AC-3 | 通过 | test_not_ready_503(fake RuntimeError);test_concurrent_load_once(6线程加载1次,锁双检);test_load_error_cached_and_cleared |
| AC-4 | 通过 | test_bad_magic_400(非音频不进ASR)+test_oversize_413(SPEECH_MAX_MB=0)+实机伪造魔数→400 |
| AC-5 | 通过(实机) | MediaRecorder mime探测(实机无浏览器环境,由前端pickAudioMime运行时探测+隐藏保底;后端av解码wav/ogg/webm/mp4全格式单测+魔数白名单) |
| AC-6 | 通过 | `pytest tests/` → **229 passed, 1 skipped**+`npx vite build` 退出码0(6.0s) |

风险终态:R-1 **open→转实机跟踪**(确认式交互保底,准确率待真人验证);R-2 closed(懒加载+503);
R-3 mitigated(av已安装+白名单+mime探测);R-4/mitigated(纯本地零外传);R-5/mitigated(int8)。
执行记录:whisper base模型一次性预置data/whisper-models(142MB,HF_ENDPOINT=hf-mirror.com
后台下载,.gitignore排除);服务重启踩坑(pkill未清干净→98端口占用,setsid脱离会话解决)。
基线回写:design/modules/speech-in.md新增,INDEX/baseline记录。
全模态后续:R-010(视频,依赖ffmpeg/RTSP/RTMP)。真人语音识别率与VAD流式转写留交互跟踪。
