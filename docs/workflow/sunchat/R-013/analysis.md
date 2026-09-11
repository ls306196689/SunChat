需求: R-013 | 代码分析(需求前置)

## A-1 现有日志体系体检 — 2026-09-11
- 状态: confirmed | 用途:支撑 R-013 日志系统设计(环节覆盖/降噪/关联追踪)
- 问题: 现有日志能否支撑"关键环节成败可查+问题排查关联+高频不淹没有效信息"?
- 检索范围: utils/logger.py 全文、grep logger 调用分布(core/services/app)、logs/ 实物、R-012 事故复盘、logs/uvicorn_r010.log 与 sunchat_*.log 对比

### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [CODE] | utils/logger.py:44-69 | get_logger:RotatingFileHandler 10MB×7 + 控制台INFO,**无 trace/请求关联字段** |
| 2 | [CODE] | utils/logger.py:134-223 | 4 个业务 Logger(Chat/Memory/Knowledge/Search),但**图片上传/视频抽帧/语音转写/ASR/agent 无对应事件记录** |
| 3 | [CODE] | routes/chat.py 上传端点 / speech.py / chat.py 500分支 | 上传成功/失败**零业务日志**;`except Exception: logger.error(f"...{e}")` 丢 traceback(排查断链) |
| 4 | [RUN] | logs/uvicorn_r010.log vs logs/sunchat_20260911.log(本次 R-012 排查实况) | 两套日志分离(access 在 stdout 重定向文件,业务在 sunchat_*.log),无关联 ID 可串;R-012 定位依赖人工时间戳对齐 |
| 5 | [RUN] | sunchat_20260911.log 样本 | 高频重复:同错"[STORAGE] ensure_vector 失败"×2、"seek 采样降级"×4、启动期 FTS 两遍;健康检查轮询将混入 access |
| 6 | [REQ] | 用户 2026-09-11 指令 | "每个关键环节都要有日志检测,不管成功失败;针对高频场景特别设计,避免无效日志淹没有用信息;当前项目也需要补充完整日志体系" |

### 结论
| # | 结论 | 依赖证据# |
|---|---|---|
| C1 | 缺"请求级关联":一次用户操作跨 route→service→llm→存储 的日志无法串查(单用户多标签页/并发即断链) | 1,4 |
| C2 | 关键环节空窗:多模态上传三端点(图/帧/音)成功失败零业务日志;部分失败路径丢堆栈 | 2,3 |
| C3 | 噪声源确定:外部探活(access)、重复性降级/失败告警、启动期批量日志 | 4,5 |

### 假设
- 无
