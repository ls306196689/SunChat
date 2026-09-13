# R-016 分析:手机照片上传失败多维取证

范围:backend 日志(13日全程)+frontend 上传链代码+服务端活体复测+axios 版本行为。

## A-1 失败形态=请求未达服务器(非后端拒绝)

- [RUN] backend/logs/sunchat_20260913.log — 手机 12:43:56 后仅有资源 GET,
  无任何 POST /chat/images(用户报障时段服务器零接触上传)。
- [RUN] 服务端活体复测:真实 PNG 200/0.8ms、4×并发 200、4MB JPG 200/9~12ms
  (直连,noproxy)。
- [RUN] 对照桌面 9/12 全天 chat.image.upload ok 数十条+bad_magic 拒绝可见 —
  说明该端点日志覆盖成功/失败两态,手机"失败"若达服务端必留痕。
- [CODE] request.js:10 axios timeout 300000 — 请求悬挂时 5 分钟内静默"上传中",
  与用户"缩略图永远上传中,最后说网络问题"症状吻合(网络错误文案=request.js:64)。

结论 C-1:上传在移动端发出阶段丢失(XHR 悬挂或未发出),后端与网络服务端侧无关
[假设标注]手机侧具体触发点(缓存旧 bundle 执行异常/浏览器内核差异/系统层)因
drop_console(生产剥离 console)+ 无客户端日志无法判定 → 这正是本需求诊断通道的立题。

## A-2 旧 bundle 复活+SPA 回退毒缓存(并发事实)

- [RUN] 12:43:56 同一秒手机拉 `index-CCHbxd7G.js`(10:41 旧产物)与
  `index-Bu_i6R7d.js`(12:15 新产物);13:02:26 又拉取已不存在的 CCHbxd7G。
- [RUN] `GET /assets/index-STALE123.js → 200 text/html 465B` — SPA catch-all 把
  index.html 伪装成任意不存在的 /assets/*(main.py:171 无条件回退)。
- [CODE] main.py:127-171 无 Cache-Control;index.html 可被启发式缓存/
  bfcache 复活旧引用。

结论 C-2:旧 HTML 引用旧 JS + 回退投毒(HTML 冒充 JS)构成页面半损坏环境,
足以解释"页面看着能用但部分模块行为异常";必须同时治理缓存与回退策略。

## A-3 三处上传显式 `Content-Type: multipart/form-data`(不带 boundary)

- [CODE] request.js:77/91/105 — 显式写死无 boundary 的 multipart 头。
- [CODE] axios@1.6.7 transformRequest 对 FormData 会 delete 该头由浏览器自动生成
  带 boundary 版本 → 现代浏览器下侥幸正确;显式头属脆弱写法,老内核行为不做保证。
- [RUN] 本会话 node 复测:拦截器时点头值原样(未及 transform),不能据此断言发出值,
  故仅登记"隐患",不作为 C-1 根因结论(OPIT-012 精神:不拿拦截器时点当发出时点)。

结论 C-3:清理为不显式设置(交浏览器)——零风险规范化,排除老内核差异面;真机
根因仍以诊断通道一手数据为准。

## A-4 可观测盲区

- [CODE] vite.config.js drop_console:true — 生产包 console 全剥,用户与我均无现场日志。
- [REQ] R-013/observability — 服务端 evt= 体系完备,唯缺客户端事件汇入。
- [用户] 会话原话:"建议把手机端的交互日志都上传到服务,这样更方便查问题"。

结论 C-4:建轻量诊断通道(环形缓冲+批量回传→evt=mobile.diag),使本类问题一查即明。
