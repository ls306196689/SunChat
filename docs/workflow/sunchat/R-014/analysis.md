需求: R-014 | 分析 A-1 | 日期: 2026-09-13

# A-1 局域网移动接入现状取证

| # | 结论 | 证据 |
|---|---|---|
| 1 | `qrcode.vue` 已在 package.json dependencies,无任何源码使用——现成可零成本用于配对码渲染 | [CODE] frontend/package.json deps 含 qrcode.vue;grep -rn qrcode frontend/src 仅 package.json 命中 |
| 2 | 多模态收发链路已齐全(chat 图片/视频抽帧/语音转写/流式 SSE),移动端只需 UI+入口,无需新业务能力 | [REQ/DESIGN] R-008/R-009/R-010 归档;[CODE] ChatView MediaRecorder×3 |
| 3 | 后端监听 0.0.0.0:8000,天然可达局域网;未挂载任何静态资源 | [CODE] config APP_HOST=0.0.0.0;main.py 无 StaticFiles/mount |
| 4 | CORS 白名单仅 localhost/127.0.0.1:3000/5173——手机经 http://<LAN-IP>:5173 dev 直连会被拦 | [CODE] config CORS_ORIGINS |
| 5 | index.html 已有 viewport meta,naive-ui 组件响应式基础存在;桌面 ChatView 含侧边栏,移动体验需简化版 | [CODE] frontend/index.html:6 |
| 6 | 安全上下文约束:浏览器 getUserMedia(麦克风)在非 localhost 的 http 源被禁用——LAN IP 直访时"录音发消息"受限,相册文件上传不受影响 | [CODE] W3C/MDN secure-contexts 规范(平台事实,非本仓假设) |
