# R-016 手机上传失败诊断通道 + multipart CT 隐患 + 缓存毒化治理

需求: R-016 | 类型: bugfix(标准) | 状态: 待冻结 | 日期: 2026-09-13
关联: 修改 R-014(mobile-pair 收发链路观测面)/R-013(evt= 体系);取证 `analysis.md#A-1~A-4`

## 背景
手机扫码端照片上传报"网络问题/空对象错"。多维取证(analysis A-1):服务端活体复测
全绿、失败 POST 从未到达服务器、且手机在同一时段拉取了已删除的旧 bundle
(A-2 缓存毒化实证)——由于生产包 drop_console + 无客户端日志,根因无法二择判定,
用户明确要求"把手机端交互日志上传到服务"。

## 目标用户 / 核心场景
- 用户(排查者):手机上传失败后,无需连电脑调 remote debug,直接打开电脑端日志
  `tail backend/logs | grep mobile.diag` 即可看到手机侧阶段事件与错误详情;
- 手机用户:上传/语音/消息全链路阶段事件自动汇入,异常时点"发送"即触发日志回传;
- 未来需求:任何移动 UI 缺陷都自带客户端一手证据(补 R-014 AC-3 渲染层盲区)。

## 功能点
- FR-1 诊断通道后端:`POST /api/v1/diag/client` 接收 `{page,seq,events:[{ts,lvl,msg,extra}]}`
  (≤50 事件/批,单事件净化截断,无鉴权与 pair 同边界);每个事件落一行
  `evt=mobile.diag ...`(复用 R-013 log_event,trace/request 摘要自动贯穿)。
- FR-2 诊断通道前端(`utils/mobileDiag.js`):环形缓冲(≤200 条)+ 阶段埋点
  (diag step:page/load/pick/uploadStart/uploadDone/uploadErr/sendStart/sendErr/
  micStart/micErr/netErr 等,含 photo reqId/文件名/大小/状态码/错误对象完整序列化
  JSON.stringify 带 replacer 防 `{}` 空对象)+ 触发式 flush(错误即发、页面隐藏
  keepalive、5s 兜底)+ localStorage 暂存失败批次下次补发。
- FR-3 缓存治理:后端 index.html 响应 `Cache-Control: no-cache`(根路由+/m+回退);
  `/assets/*` 不存在 → JSON 404,**不再回退投毒 HTML**(A-2)。
- FR-4 multipart 规范化:request.js 三处上传删除显式 `Content-Type`
  (A-3,浏览器自动带 boundary,排除老内核差异面)。
- FR-5 上传可悬挂感知:"上传中"超 20s 前端主动判超时(显式 timeout=20s upload)+
  失败文案具体化(HTTP 状态/耗时/reqId)。

## 边界与非目标
- 不做:全量 console 搬运(仅阶段事件+错误)、服务端日志 UI 展示页、手机远程控制台;
- 不引入鉴权/新依赖;diag 端点仅内网边界(与 pair 一致,继承 R-014/R-3 声明)。
- 不承诺修复手机侧系统级问题(诊断通道提供判定依据;若指向老内核需另立需求)。

## 与历史需求的关系
- 修改 R-014:`/m` 收发链路增加 diag 埋点(不改任何既有接口契约);
- 继承 R-013:evt= 语义域新增 `mobile.*`;
- 落地 R-015/A-2 教训:本需求 AC 含渲染层证据(截图/DOM 断言或实拍)。

## 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | `POST /api/v1/diag/client` 返回 `{ok,n}`;事件行 `evt=mobile.diag` 落日志含 page/step/lvl/msg | pytest 新增 test_diag.py(AC-1 含截断/净化/超限拒绝) |
| AC-2 | `index.html` 响应头含 `Cache-Control: no-cache`;不存在的 `/assets/x.js` → 404 JSON 非 HTML | pytest(AC-2,含 main.py 双态) |
| AC-3 | 手机 `/m` 点相册上传:服务端日志见同 reqId 的 mobile.diag uploadStart/Err 与 http.post 行对账;错误对象非 `{}`(msg 含 message/name) | 真机实拍 + `grep reqId` 日志互串(渲染层证据,落地 OPT-011) |
| AC-4 | 三处上传不再显式设 Content-Type;发送走浏览器自动 boundary(抓包/回声断言) | node 静态断言 + build |
| AC-5 | 上传悬挂 20s 显示超时而非永久转圈 | 真机 或 桩断言(前端超时参数存在且=20000) |
| AC-6 | 全量 pytest 绿(现存 275 收集零回归)+ vite build + r014/15_check 绿 | `pytest tests/ -q` + `npm run build` + 两 check 脚本 |

## 日志设计(R-003)
新增环节:diag 接收(evt=mobile.diag per event,INFO;超限/非法 WARN 单行)与
mobile.send/upload 阶段事件;**降噪**:环形缓冲+批量 flush(≤50/批,正常无错误时
5s 兜底一次),fail 带 exc=False(错误已在 extra,堆栈不适用客户端);堆栈:
diag 内部异常记 ERROR exc_info。

## 待澄清清单
(见 state.clarifications,question 单包处理)
