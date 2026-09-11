需求: R-010 | 代码分析(需求前置)

## A-1 视频输入抽帧管线可行性 — 2026-09-11
- 状态: confirmed | 用途:支撑 R-010 选型(抽帧复用 R-008 图片通道)
- 问题: 无系统 ffmpeg 下视频解析/抽帧是否可行?与既有图片通道衔接成本?
- 检索范围: av(PyAV)能力实测、R-008 design/modules/chat-image.md、ChatView 上传模式

### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [RUN] | av 17.1.0 合成3s/30帧 avi 编码→解码→30帧全遍历 | 无系统 ffmpeg(av 自带编解码),管线通 |
| 2 | [RUN] | `frame.to_image().save('JPEG')` | 693B jpeg b'\xff\xd8\xff',Pillow 12.2 可用 |
| 3 | [DESIGN] R-008/chat-image | 图片通道:POST /chat/images→image_id→Message.images→窗口注入/vision/回显 完整闭环 | 抽帧结果可直接复用 |
| 4 | [CODE] ChatView.vue uploadChatImage/pendingImages | 上传→预览→发送携带 ids 模式已建立 | 视频→帧ids 前端零新链路(复用 pendingImages)|
| 5 | [RUN] av 探测 vs 视频元数据 | vs.frames=30, duration=time_base 可用 | 均匀抽帧定位可行 |

### 结论
| # | 结论 | 依赖证据# |
|---|---|---|
| C1 | av 纯 Python 抽帧可行(无需 ffmpeg 安装);帧→JPEG→复用 R-008 通道,后端改动=1个抽帧函数+1个上传端点 | 1,2,3 |
| C2 | 前端复用 pendingImages(🎬选择视频→上传→帧入 pending 图),发送/回显/窗口零新代码 | 3,4 |

### 假设
- 无(R-010 全链证据闭环;真实手机 mp4 样本 E2E 由 AC-2 实测)
