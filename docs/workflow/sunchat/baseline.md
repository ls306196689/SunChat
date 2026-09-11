# sunchat 设计基线

当前基线指针:`docs/workflow/sunchat/design/`(自 R-001 归档起自持;初始内容复制自
memory-retrieval-opt/design/,2026-09-06 产出,经用户确认迁移时沿用,2026-09-08)。
旧目录仅作历史归档,后续修订一律改本目录。

## 基线修订记录
| 日期 | 需求 | 修订 |
|---|---|---|
| 2026-09-08 | R-001 | 基线 → R-001(2026-09-08): 新增 weather-core 模块+chat-direct-weather 接入(weather 直查前置于 DDG);见 design/modules/ |
| 2026-09-08 | (迁移) | 创建 baseline.md,指向 memory-retrieval-opt/design/ |
| 2026-09-11 | R-005/R-006/R-007 | 无基线修订(session契约/缓存/索引均内部实现,不改在册接口) |
| 2026-09-11 | R-008 | 基线 → R-008(2026-09-11): 新增 chat-image 模块(对话图片通道:上传/回显/窗口注入/vision探测);见 design/modules/chat-image.md |
| 2026-09-11 | R-009 | 基线 → R-009(2026-09-11): 新增 speech-in 模块(本地faster-whisper语音转写,确认式交互,运行期离线);见 design/modules/speech-in.md |
