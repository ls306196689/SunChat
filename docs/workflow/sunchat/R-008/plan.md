需求: R-008 | plan | 标准 iteration(总授权直通)

| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | 后端图片通道:model列+schema补列、model_manager.supports_vision、chat路由上传/回显、service透传+窗口、config、fakes桩 | backend(models/sql_models.py, core/model_manager.py, app/{config.py,api/v1/routes/chat.py}, services/chat_service.py, tests/fakes.py) | R-008/{requirements,design-change,analysis}.md | 代码;验证:`pytest tests/test_chat_image.py -q` | R-1,R-3,R-4,R-5 |
| 2 | 前端接入+全量回归+归档 | frontend(src/utils/request.js, src/stores/chat.js, src/pages/ChatView.vue, components MessageItem) | 步骤1产出文件路径 + R-008/design-change.md §7 | 前端改动;验证:`pytest tests/` 全绿 + `npm run build`(或 vite build)退出码0 | R-2,R-4 |

自检:两步拓扑有序(前端依赖后端契约);每步验证可独立执行;高危 R-1 由窗口上限+AC-4 覆盖,
R-5 由 AC-2 覆盖,AC-5 覆盖 R-3。测试硬门禁:两步均含单测/构建校验。
