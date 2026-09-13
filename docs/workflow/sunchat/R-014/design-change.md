需求: R-014 | 基线: sunchat design r-013(baseline.md) | 状态: v1 | 日期: 2026-09-13

# R-014 增量设计(新模块 mobile-pair)

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| r1 | 2026-09-13 | 初稿 | R-014 |

## 变更清单(相对基线)
| # | 动作 | 对象 | 内容 | 触发FR | 兼容性 |
|---|---|---|---|---|---|
| C1 | 新增 | `GET /api/v1/pair/info` | 返回 `{lan_ip, port, url:"http://{ip}:{port}/m"}`;UDP-connect 探测默认出口 IPv4,多网卡取默认、失败返回空串并提示手输 | FR-1/6 | 纯新增端点 |
| C2 | 新增 | StaticFiles 挂载 | `create_app` 末端:dist 存在才挂 `/assets`,SPA 回退 `GET /{path:path}`(静态文件>api 路由>index.html);不存在跳过=现状不变 | FR-1 | dist 缺失零影响 |
| C3 | 修改 | `frontend/src/utils/request.js:3` | baseURL 改**同源相对** `/api/v1`(硬编码 localhost 在 LAN 下必炸 [CODE A-1]);vite 开发代理已覆盖同源路径 | FR-1 | dev/prod 同源统一 |
| C4 | 新增 | `frontend/src/pages/MobileView.vue` + 路由 `/m` | 移动会话页:会话切换(共享列表)/SSE 文字流/相册图(accept image/*,≤4)/视频(frames)/语音双路;复用 request.js 既有封装(uploadChatImage/uploadVideoFrames/transcribeSpeech)与 R-012 拦截器解包教训(双写防御 resp?.data?.image_id) | FR-3/4/5 | 复用既有 API,零契约变更 |
| C5 | 新增 | SettingsView "手机接入"卡片 | pair/info 拉址→qrcode.vue 渲染;不可达排查文案(防火墙同网段提示) | FR-2 | 桌面流零改动 |
| C6 | 新增 | config `PUBLIC_PORT: Optional[int]=None` | 二维码端口显示(反代场景可覆盖);默认取 APP_PORT | FR-6 | 兼容 |

## 日志设计(承接 FR-7/observability 基线)
- 环节与事件: `evt=pair.info result=ok|fail`(端点返回/IP 探测失败 reason=no_lan);
  `evt=pair.qr_view result=ok`(前端不产日志——边界:后端日志域,前端 console 不在本期,R-013 §5);
- 既有环节(chat.stream/chat.image.upload/chat.video.frames/speech.transcribe/http 摘要)
  移动端零新增自动继承(trace 经中间件贯穿,AC 验证时核对 `[r=` 同码);
- 失败带堆栈沿用 500 分支 exc_info;无新增高频路径(二维码轮询不引入:仅进入页面拉一次)。

## 受影响模块新版设计
| 模块 | 新版文档 | 替换基线 |
|---|---|---|
| mobile-pair | R-014/modules/mobile-pair.md | 新增 design/modules/mobile-pair.md |
> C3 为既有 utils/request.js 接口面(仅常量值),不单设模块文档;C5 桌面组件级小改。

## 风险(同步 state.risks)
| id | 描述 | 概率 | 影响 | 缓解 | 状态 |
|---|---|---|---|---|---|
| R-1 | 手机浏览器兼容(Safari/微信) | 高 | 低 | SSE 用 fetch+ReadableStream(移动端 Safari 支持);build 后实机 E2E;微信内置浏览器验证 | open |
| R-2 | 非 HTTPS 禁麦 | 高 | 中 | D-142 文件兜底路径;页内提示引导(录音 App→上传) | open |
| R-3 | LAN 无鉴权 | 中 | 中 | 边界声明可信内网(现状一致);文档注记非公网暴露;不做穿透 | open |
| R-4 | 大视频抽帧超时 | 中 | 低 | 复用 50MB 限制+120s 超时已实装;上传前置大小提示 | open |
| R-5 | dist 挂载回归桌面/dev | 中 | 低 | dist 缺失跳过+pytest 双态用例;dev 走 vite 代理不碰 dist | open |
