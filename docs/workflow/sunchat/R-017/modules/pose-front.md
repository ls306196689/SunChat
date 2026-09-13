# 模块设计:pose-front(request.js + MobileView.vue + ChatView.vue)

需求: R-017 | 触发: FR-6, FR-7 (决策 D-004) | 日期: 2026-09-13 | 状态: draft r1

## 对外接口
```js
// request.js 新增
export function analyzeVideoPose(file, sessionId) {
  const form = new FormData()
  form.append('file', file)
  form.append('session_id', String(sessionId))
  return request.post('/chat/video/pose', form,
    { headers: { 'Content-Type': undefined }, timeout: 180000 })
}
```

## 能力说明
- 提供:双端"跑步分析"按钮、拍摄引导弹层(once/session)、进行中态、结果渲染
  (报告文本+骨架帧图)、失败拒析展示+重试。
- 不提供:实时取景引导、指标图表(报告文本即终态)。

## 内部关键逻辑
1. MobileView:视频按钮后加"跑步分析";`poseMode` ref:false→选择文件即走
   analyzeVideoPose(独立 pending 态,不占图片额度);点击首次弹拍摄要点(决策 D-001
   文案两支,localStorage 记 `pose_guide_seen`,长按/再次点击按钮可复看)。
2. 渲染:成功后 `chatStore.fetchMessages/switchSession` 重取消息——assistant 消息
   带 images 自然走既有气泡图回显(R-008/011 通道);报告正文即 markdown-ish 文本,
   移动端纯文本渲染即可(不引入解析器)。
3. ChatView 同款按钮+el-dialog 引导;成功后刷新消息列表。
4. 状态机:`idle→guiding→uploading→(done|error)`;error 展示 detail(拒析文案)
   +重试按钮(同 R-016 重试不占额度模式);埋点 `diag('pose.pick/start/ok/fail')`
   接 mobileDiag(R-016 通道,reqId 贯穿)。
5. r017_check.mjs(新增静态断言,仿 r016):analyzeVideoPose 存在且 CT undefined、
   timeout 180000、pose 按钮与引导文案存在、dist 签名。

## 依赖
- request.js(本需求 CH-5);chatStore.fetchMessages(既有);mobileDiag(R-016 既有)。
