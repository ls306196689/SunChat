# R-016 设计变更:mobile-diagnostics(移动诊断通道)+ 静态托管缓存治理

状态: v1 | 修订轮次: r1 | 日期: 2026-09-13 | 归档后并入 design/modules/mobile-diagnostics.md
关联: R-013(evt= 体系继承)、R-014(mobile-pair 边界复用)、analysis A-1~A-4

## 模块划分(bugfix 局部,无架构影响)
| 模块 | 文件 | 变化 |
|---|---|---|
| diagnostics(新) | backend/app/api/v1/routes/diag.py | 新增端点 |
| static-host(改) | backend/app/main.py | no-cache + assets 404 止投毒 |
| mobileDiag(新前端) | frontend/src/utils/mobileDiag.js | 埋点/缓冲/flush |
| request 封装(改) | frontend/src/utils/request.js | CT 规范化+上传 timeout |
| MobileView(改) | frontend/src/pages/MobileView.vue | 阶段埋点+reqId+超时文案 |

## 对外接口

### POST /api/v1/diag/client
请求体:`{page: str(≤64), events: [{ts:int(ms), lvl:'info'|'warn'|'err', step:str(≤40),
msg:str(≤500), extra?: object}]}`;events 1..50 条,超 50 取前 50(body 非法/空 events
→ 400)。extra 仅接受 object,JSON 序列化后截 1KB;全字段净化(`|`换`/`、去换行,
log_event 既有规则)。无鉴权(内网边界,同 pair;R-1 缓解=批量上限)。
响应:`{code:200, message:"success", data:{ok:true, n:int}}`。
日志:每事件一行 `evt=mobile.diag page=<p> step=<s> lvl=<l> msg=<m> [extra=…]`
(log_event INFO;lvl=err→ERROR,不含堆栈 exc=False;R-2 前端节流兜底)。

### 静态托管(FR-3)
- `GET /`、`GET /m`、SPA 回退 index.html:响应头 `Cache-Control: no-cache`
  (FileResponse headers;每次校验协商,不阻断 ETag 之外的内容层);
- catch-all:`/assets/` 前缀且文件不存在 → **404 JSON**(不返回 HTML,杜绝
  HTML 冒充 JS 毒缓存,A-2);其余未知路径仍回退 index.html(history 路由)。

### 前端 mobileDiag.js(默认开启,C1)
- `diag(page)` 初始化(幂等)/ `diagStep(step, extra?, lvl='info')` /
  `diagError(step, err)`(err 序列化 replacer:message/name/stack 前 300 字+枚举
  own props,杜绝 `{}`);
- 环形缓冲≤200;flush 触发:①error 后合批立即(节流≥2s);②visibilitychange
  hidden/freeze → `fetch keepalive`;③5s 兜底(仅当有新事件);
- 失败批次入 localStorage `sunchat_diag_backlog`(≤100 条,超出丢最旧),
  下次 flush 头部拼接补发;diag 自身网络失败静默(绝不递归诊断);
- 页面访问即 `diagStep('page.enter',{ua,href})`(低频,一页面一次)。

### 埋点清单(阶段事件,step 值)
page.enter / upload.pick(reqId,name,size,type)/ upload.start / upload.ok(耗时ms)/
upload.fail(status,耗时,msg)/ send.start / send.stream.ok / send.err(recovered=true
回退成功标记)/ mic.grant|deny / transcribe.ok|fail。reqId=crypto.randomUUID 前 8 位,
随 pick/start/fail 贯穿,与服务器 http.post 行按 [时间窗+顺序] 对账(AC-3)。

### multipart 规范化(FR-4)
request.js 三处 `headers: {'Content-Type': 'multipart/form-data'}` 删除
(A-3:axios1.x transformRequest 自动带 boundary;显式头属老内核差异面)。

### 上传超时(FR-5,C2)
uploadChatImage/文件音频:axios `timeout: 20000`;uploadVideoFrames 维持 120000
(抽帧慢任务,R-010 既有约定);超时文案:`上传超时(20s):请检查Wi-Fi后重试(req <id>)`。

## 内部关键逻辑
- diag 端点 try 包裹全解析,任何异常→单行 `evt=diag.ingest result=fail` 不抛 500
  风暴(接收面自身可诊断);
- MobileView catch 处由 `item.error=err.response?.data?.detail||err.message`
  升级为同时 `diagError('upload.fail', err)`(保留原展示);
- 桌面端 ChatView 不埋点(本次范围=移动端;后续需求可复用 mobileDiag)。

## 依赖
| 模块 | 接口 | 文档 |
|---|---|---|
| observability | log_event/RequestLogMiddleware | design/modules/observability.md |
| mobile-pair | /m 页面/内网边界声明 | design/modules/mobile-pair.md |

## 测试约定
pytest test_diag.py(端点形状/截断/超限/400/evt 行落 caplog);test_mobile_pair 增
no-cache 头与 assets404 用例;前端 r016_check.mjs 静态断言(先 build 后断言,
新行为签名——OPT-012);AC-3 真机+日志 reqId 对账(渲染层证据——OPT-011)。
