# 模块: mobile-pair(局域网手机接入)

状态: v1 | 修订轮次: r1 | 日期: 2026-09-13

## 对外接口
- `GET /api/v1/pair/info` → `{code:200, data:{lan_ip:str, port:int, url:str}}`
  (lan_ip 探测失败=`""`,url 空串;无鉴权)。
- SPA 静态端点:dist 存在时 `GET /`、`GET /m`、`GET /assets/*`;未知非 api 路径回退
  index.html(history 路由);api 路径不劫持。
- `frontend/src/pages/MobileView.vue`(路由 `/m`):
  - **壳适配(R-015)**:`App.vue` `bare = route.path === '/m'` 时裸渲染 `<router-view/>`
    (无 Sidebar/HeaderBar/app-footer,`100dvh` 全屏);桌面路由走原壳零改动;
  - 会话:GET/POST /chat/sessions(共享列表)、GET /chat/sessions/{id}/messages(分页 20);
  - 发送:SSE POST /chat/stream(session_id/content/images,fetch ReadableStream 解析 `data:` 帧);
  - 附件:uploadChatImage(≤4/条)、uploadVideoFrames 复用 request.js 封装
    (响应解包用 R-012 双写防御:`d?.data?.image_id || d?.image_id`);
  - 语音:speechStatus() 探就绪;MediaRecorder 可用则录(webm→transcribeSpeech),
    否则 accept="audio/*" 文件→transcribeSpeech;文本回填输入框(确认式,同 R-009 交互)。
- SettingsView「手机接入」:`qrCodeUrl = data.url`;qrcode.vue 组件(既有依赖)。
- config:`PUBLIC_PORT: Optional[int]=None`(覆盖展示端口)。

## 能力说明
- 提供:扫码即用、同源单端口、移动收发消息全通道(文字/图/视频帧/语音转写)。
- 不提供:账户/配对绑定(单用户)、消息推送、知识库/记忆管理 UI、桌面端专属功能。

## 内部关键逻辑
- LAN IP 探测:`socket(AF_INET, SOCK_DGRAM).connect(("8.8.8.8", 80))` 取 `getsockname()`
  (无真实发包);异常→空串降级;不枚举全部网卡(默认出口即可达路径,多网卡场景手输)。
- SPA 回退与 api 共存:静态 mount 注册序在 api 路由之后;catch-all 显式排除 api 前缀
  (返回 404 JSON 与既有 api 404 一致)。
- MobileView 单组件内聚:不 import ChatView 内部件(避免 R-011 待发区状态机拖累
  轻量性;重试=整条重发)。
- SSE 解析:fetch POST + ReadableStream + TextDecoder 按 `\n\n` 切帧,JSON.parse 容错
  (半帧缓存);error 帧显示错误并保留输入。

## 依赖
| 模块 | 接口 | 文档 |
|---|---|---|
| 既有 chat/speech 通道 | /chat/stream /chat/images /chat/video/frames /speech/transcribe | design/modules/chat-image.md, speech-in.md |
| observability | RequestLogMiddleware/log_event(自动贯穿) | design/modules/observability.md |
