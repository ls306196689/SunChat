# sunchat 需求

需求: R-014 | 类型: feature | 基于: R-008/R-009/R-010(多模态能力承接)
状态: 已确认(2026-09-13 question)| 版本: v1 | 日期: 2026-09-13

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| v1 | 2026-09-13 | 初稿 | 用户指令:手机扫码局域网聊天 |

## 背景
用户指令(2026-09-13):为助手增加手机扫码接入——同一局域网内手机扫二维码即可与
助手聊天,支持相册照片/视频上传、语音、文字。取证 analysis.md#A-1:多模态收发
链路与流式已齐全(R-008/009/010),后端已监听 0.0.0.0,`qrcode.vue` 依赖已在仓,
缺的是①统一可及入口(现无静态挂载、CORS 不含 LAN IP)②移动端会话页③扫码配对体验。

## 与历史需求的关系
- 复用 R-008 图片上传/回显、R-010 视频抽帧、R-009 语音转写 API(移动端直调,零后端能力改动);
- 复用 R-013 trace/evt 日志(移动端请求同经 RequestLogMiddleware,环节事件已覆盖);
- 新增 mobile-pair 模块(二维码配对+移动会话页+静态托管端点),不改动既有端点契约。

## 目标用户
本机用户及其局域网内任意手机浏览器(iOS Safari/Android Chrome/微信内置)。

## 核心场景
1. 配对:桌面设置页显示二维码内容 = `http://<LAN-IP>:<port>/m`;手机扫码打开移动
   会话页;页内明示所连主机地址,无需账户/口令(可信家内网边界,与现有单用户模式一致)。
2. 文字聊天:移动页输入→SSE 流式显示(复用 /chat/stream),与桌面同一会话体系。
3. 相册收发:选相册照片(≤4张/条)与视频(≤50MB)→ 走 R-008/R-010 通道,气泡回显,
   历史含图可回看。
4. 语音:按住/点击录音→上传 /speech/transcribe→转写文本回填确认后发送。
   非 HTTPS 安全上下文下浏览器禁 getUserMedia → 降级"相册/录音文件"上传兜底(澄清C2)。
5. 会话延续:移动端默认新建会话并可与桌面互见同一会话列表(单用户 LOCAL_USER_ID)。

## 功能点
| 编号 | 描述 | 优先级 |
|---|---|---|
| FR-1 | 统一入口:`create_app` 挂载 `frontend/dist` 为 StaticFiles(存在才挂,SPA history 回退),桌面+移动同源同源,免 CORS/免双端口;`GET /api/v1/pair/info` 返回本机 LAN IP 与 /m URL | P1 |
| FR-2 | 配对二维码:SettingsView 增"手机接入"区,用 qrcode.vue 渲染 pair URL,含 LAN IP 手输提示与不可达排查文案 | P1 |
| FR-3 | 移动会话页 `/m`(新 Vue 路由 MobileView):单栏聊天 UI(消息流+输入区),文字/SSE 流式/新会话/会话切换/历史 | P1 |
| FR-4 | 移动相册收发:file input(accept image/*,video/*)+ 预览待发 + 复用既有上传/抽帧 API + 气泡与历史图片回显 | P1 |
| FR-5 | 移动语音:MediaRecorder 录音上传转写回填;安全上下文不可用时自动切换文件上传(accept audio/*)兜底 | P1 |
| FR-6 | LAN IP 探测:pair/info 用 socket UDP 技巧枚举非回环 IPv4,多网卡取默认出口;探测失败返回空并提示手输 | P2 |
| FR-7 | 日志设计(必填节):环节清单= pair.info / http(中间件既有)/ chat.stream / chat.image.upload / chat.video.frames / speech.transcribe(mobile 复用同 evt,新增 pair 域);evt=`pair.qr_view`(桌面打开配对区 INFO)、`http.*` 既有;失败带堆栈;无新增高频路径,delta 保持零日志;级别策略沿用 observability.md | P2 |

## 边界与非目标
- 包含:局域网 HTTP;单用户无鉴权(与现有 /whoami 诚实模式一致);iOS Safari/Android Chrome;桌面流零回归。
- 不做:公网穿透/HTTPS 强制/账户口令体系(仅留文档注记)、微信分享SDK、消息推送(离开页即断,下次拉历史)、移动桌面端功能全量对齐(知识库管理/记忆编辑不在移动页,聊天为主)。

## 验收标准
| 编号 | 标准(可验证) | 验证方式 |
|---|---|---|
| AC-1 | dist 存在时 `GET /` 200 text/html、`GET /m` SPA 回退200、`/api/v1/*` 正常、未知路径回退 index;dist 缺失时 `GET /` 不报错(404 JSON)且 pytest 全绿 | 实机 curl + pytest 新增 test_mobile_pair.py(双态) |
| AC-2 | `GET /api/v1/pair/info` 返回 {lan_ip, url:"http://ip:port/m"};lan_ip 非回环或多网卡候选可解释 | 单测(mock socket)+ 实机 curl |
| AC-3 | Settings 显示 QR(可扫,内容为 pair URL);手机扫码打开 /m:发文字→SSE 流式回复上屏 | 实机手机 E2E |
| AC-4 | 手机相册选2图发送→助手可见(带图回复或确认)+ 气泡回显;视频≤50MB 走抽帧 ok | 实机 + test_mobile_pair 复用 R-008/010 断言 |
| AC-5 | 手机语音(或音频文件兜底)→转写→回填→发送成功;getUserMedia 不可用时兜底路径可用 | 实机(真机或 adb/模拟 UA + wav 上传统路径) |
| AC-6 | 全量 pytest 绿(现存 262 基线零回归 + 新增);移动页 vite build 通过 | `pytest tests/ -q` + `vite build` |

## 决策记录
- [D-140] 2026-09-13 移动能力=既有 API 的新客户端,后端零改业务逻辑(仅 pair/info+静态挂载);证据 A-1。
- [D-141] 2026-09-13 移动端=独立轻量 /m 路由页(聊天为核心,管理功能不上移动页)。
- [D-142] 2026-09-13 语音双路径:安全上下文用 MediaRecorder;禁麦环境自动切"音频文件上传→转写"兜底;零证书。
- [D-143] 2026-09-13 设置页常驻"手机接入"区:QR(qrcode.vue 既有依赖)+LAN 地址+排查文案。
- [D-144] 2026-09-13 会话体系共享(LOCAL_USER_ID 天然单用户):移动可切换/续写桌面会话。
- [D-145] 2026-09-13 后端 StaticFiles 挂 dist 单端口同源;dist 缺失跳过挂载,开发流零影响。
