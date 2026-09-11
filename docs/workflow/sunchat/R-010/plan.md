
## 计划表
| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | 后端 core/video.py+抽帧端点+config+单测 | backend | R-010/{requirements,design-change,analysis}.md | core/video.py, routes/chat.py(+frames), config.py, tests/test_video.py;`pytest tests/test_video.py` | R-2,R-3 |
| 2 | 前端 🎬+全量回归 | frontend | 步骤1契约 | request.js uploadVideoFrames, ChatView.vue;`npx vite build` + 实机 | R-1 |

## 总结节(验收归档 2026-09-11)
| AC | 结果 | 证据 |
|---|---|---|
| AC-1 | 通过 | test_synthetic_avi_frames(4帧JPEG魔数/时间戳递增/dur>2.5)/test_max_frames_respected |
| AC-2 | 通过 | test_frames_200_and_echo(frame_ids 经 GET /chat/images 200 image/jpeg)+实机:4帧回显200+真实vision答"纯红色画面…"(合成帧确为红/蓝色块,回答合理)+历史images回显4个 |
| AC-3 | 通过 | test_bad_magic_400(PDF/PNG魔数拒)+test_corrupt_ftyp_400(真魔数垃圾→ValueError)+test_oversize_413;实机坏文件→400 |
| AC-4 | 通过 | test_send_frames_through_chat:frame_ids当images发送→payload base64==帧、落库回显=R-008行为(test_chat_image 18例全回归绿) |
| AC-5 | 通过 | `pytest tests/` → **237 passed, 1 skipped**+`npx vite build` 0 |

风险终态:R-1 mitigated(N=4全帧入模型;确认式发送);R-2 mitigated(seek采样+50MB);
R-3 mitigated(白名单+实机avi/合成mp4通过;真手机样机待用户实测,失败路径400明示)。
执行记录:服务重启踩坑(pkill/pgrep模式自匹配→`[u]vicorn`括号技巧+setsid --fork 脱离)。
基线回写:chat-image.md 追加视频附录。
全模态三期(R-008图片/R-009语音/R-010视频)交付完毕。遗留候选:视频音轨、真人语音识别率
评估、搜索归纳二次LLM合并(D-202)、search_history 30天清理(D-304)、图片生命周期清理(R-002/R-2)。
