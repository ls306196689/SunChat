需求: R-008 | plan | 标准 iteration(总授权直通)

| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | 后端图片通道:model列+schema补列、model_manager.supports_vision、chat路由上传/回显、service透传+窗口、config、fakes桩 | backend(models/sql_models.py, core/model_manager.py, app/{config.py,api/v1/routes/chat.py}, services/chat_service.py, tests/fakes.py) | R-008/{requirements,design-change,analysis}.md | 代码;验证:`pytest tests/test_chat_image.py -q` | R-1,R-3,R-4,R-5 |
| 2 | 前端接入+全量回归+归档 | frontend(src/utils/request.js, src/stores/chat.js, src/pages/ChatView.vue, components MessageItem) | 步骤1产出文件路径 + R-008/design-change.md §7 | 前端改动;验证:`pytest tests/` 全绿 + `npm run build`(或 vite build)退出码0 | R-2,R-4 |

自检:两步拓扑有序(前端依赖后端契约);每步验证可独立执行;高危 R-1 由窗口上限+AC-4 覆盖,
R-5 由 AC-2 覆盖,AC-5 覆盖 R-3。测试硬门禁:两步均含单测/构建校验。

## 总结节(验收归档 2026-09-11)
| AC | 结果 | 证据 |
|---|---|---|
| AC-1 | 通过 | test_upload_png_jpg_gif_webp/test_webp_magic/test_extension_lie_rejected(服务端按魔数存)/test_oversize_413;实机伪造上传→400 |
| AC-2 | 通过 | test_path_traversal_400(URL规范化404+handler守卫400)/test_missing_404;实机回显200 image/png 字节一致 |
| AC-3 | 通过 | test_payload_has_base64_and_persist:LAST_CHAT_PAYLOADS 末条 user images[0] b64==源文件;DB+get_messages 回传 image_id |
| AC-4 | 通过 | test_history_window_injection:3条带图历史注入、总图≤8、最旧排除出窗口 |
| AC-5 | 通过 | test_pure_text_payload_equivalent(无images键);test_non_vision_model_strips(strip断言) |
| AC-6 | 通过 | test_three_states_and_cache(True/False/TTL命中,post计数=2);test_unreachable_false |
| AC-7 | 通过 | test_idempotent_backfill(重复ensure_schema无错+列存在) |
| AC-8 | 通过 | `pytest tests/` → **218 passed, 1 skipped**(基线200+18);`npx vite build` 退出码0(6.3s);实机E2E:上传→真实vision模型正确答"上绿下蓝"→历史回显 images 字段→回显字节一致 |

风险终态:R-1 mitigated(窗口硬上限+AC-4);R-2 open→**登记遗留**:图片生命周期清理留后续需求;
R-3 closed(vision探测+strip实测);R-4 closed(images默认[] 回归等价);
R-5 closed(魔数派生+uuid双校验,400/404拦截实测)。
执行偏差记录(R7.2):E2E 首跑 503 系环境代理劫持 localhost(非代码缺陷),no_proxy 后通过;
服务重启用 setsid 脱离会话防误杀。
基线回写:design/modules/chat-image.md 新增,INDEX/baseline 记录修订。
全模态后续:R-009(语音输入,需 whisper/ffmpeg)、R-010(视频抽帧)分期。
