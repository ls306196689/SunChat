# R-015 手机扫码端缺陷修复(/m 裸渲染脱离桌面壳 + dev 端口提示)

需求: R-015 | 类型: bugfix(micro) | 状态: draft | 日期: 2026-09-13

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| v1 | 2026-09-13 | 初稿 | R-014 归档后用户报障"检查手机扫码端问题" |

## 一、需求
### 现象 / 动机
手机扫码(192.168.1.47:8000/m)打开移动页后:①左侧出现 64px 深色桌面侧栏;
②双头部(MobileView 自带 mv-bar + 桌面 64px HeaderBar,标题兜底显示"聊天");
③底部出现桌面页脚"SunChat v1.0.0 本地运行中";④`.mv{height:100dvh}` 处于高约
100vh−128px 的 `overflow:hidden` 容器内 → 底部输入区被顶出/裁切,发消息困难。
接口链路(pair/info、/chat/sessions、SSE、上传、转写)全部正常 [RUN R-014 run-evidence
+ 本次复核:pair/info 200、/m 200、SSE meta/delta/done 通、sessions/messages 契约 ok]。

### 根因(缺陷类必填,MUST 引用 analysis.md#A-n)
- 壳包裹:`App.vue:44-60` 无条件渲染 Sidebar/HeaderBar/footer,无 `/m` 路由分支 →
  `/m` 被桌面壳包裹且高度溢出裁切 — 依据: `analysis.md#A-1`(C-1);
- 验收盲区(成因说明,非本次改动):R-014 RUN 证据止于 HTTP/接口层,无渲染层检查 —
  依据: `analysis.md#A-2`(C-2);
- 次要:开发态(vite 5173)手机误导无法打开;pair/info 固定生产口 8000 正确,仅缺提示 —
  依据: `analysis.md#A-3`(C-3)。

### 期望行为
- `/m` 整屏裸渲染 MobileView:无桌面侧栏、无桌面 HeaderBar、无页脚;`height:100dvh`
  占满手机视口,输入区可见可点击;桌面路由 `/` `/memories` `/knowledge` `/settings`
  渲染与现状逐像素等价(壳零变化)。
- SettingsView"手机接入"卡片补一行开发态提示(vite 5173 手机不可达,请经 8000 访问)。

### 影响范围
- 文件: `frontend/src/App.vue`、`frontend/src/pages/SettingsView.vue`(≤3)
- 对外接口: 不变(MUST)——不改任何 API 签名/路由 path/store 接口
- 新依赖: 无(MUST)

### 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | dist 构建产物含路由分支:`/m` 裸渲染、桌面路由含 Sidebar | `node frontend/scripts/r015_check.mjs` 断言(新增静态断言,等效单测;仓无 vitest 沿 R-014 plan 豁免) |
| AC-2 | vite build 通过 | `npm run build` |
| AC-3 | 后端 pytest 全量零回归(后端零改动) | `pytest tests/ -q`(基线 275+1skip) |
| AC-4 | 手机实机:打开 192.168.1.47:8000/m 单头无侧栏无页脚、输入区可见,发消息流式上屏 | 用户实拍/实机确认 |

## 二、方案设计
### 改动点定位(附证据)
| 位置 | 证据 | 现行为 → 目标行为 |
|---|---|---|
| frontend/src/App.vue:44-60 | `[CODE] <n-layout has-sider>…<Sidebar/><HeaderBar/>…<app-footer>` 无分支 | 桌面壳包裹 /m → `v-if="route.path==='/m'"` 时仅 `<router-view/>`,否则原壳不动 |
| frontend/src/pages/SettingsView.vue:202-214 | `[CODE] 手机接入卡片` 无 dev 提示 | 补一行文案:开发模式(vite 5173)请用手机访问 8000(pair.url 已展示生产口) |

### 修改思路
`useRoute()` 取 `route.path === '/m'` 作为唯一分支条件(计算属性 `bare`)。`bare` 时
模板只渲染 `<router-view/>`(不带 n-config-provider 之外新增包裹;主题 provider 保留以
防 MobileView 未来引用 naive 主题,MV 现用裸 CSS,零影响)。壳样式全 scoped,
`.mv` 已在自身 scoped 内 100dvh,脱离 `#app` 的 `height:100vh` 冲突域即自然铺满
(MobileView 自身根元素即视口,`#app` 高度由内容撑起,body 滚动关闭不变)。
不删改 Sidebar/HeaderBar 既有适配逻辑(isMobile 检测供桌面窄窗用,保留)。

### 日志设计(R-003 必填)
纯前端渲染分支与文案,无新增运行时环节;既有 RequestLogMiddleware 自动贯穿 /m。

### 回归测试设计
- 新增 `frontend/scripts/r015_check.mjs`(node 静态断言,零依赖,范式同 r014_check.mjs):
  断言 App.vue 含 `=== '/m'` 分支与裸 router-view;dist 构建产物含该分支(MobileView
  chunk 仍在);SettingsView 含 5173 提示文案。
- AC-2 vite build 成功即产物语法完整性回归(R-012/014 既有实践)。
- AC-3 pytest 全量=后端零改动回归;AC-4 用户实机(渲染层证据补 R-014 A-2 盲区)。

### 与历史需求的关系
- 修改 R-014/impl 缺陷壳适配(非 FR 文本变更);R-014/AC-3 渲染语义由本需求补齐;
  继承 R-014/design modules/mobile-pair.md(验收后回写壳适配一句)。

## 执行步骤(≤2)
| id | 目标 | 产出 + 验证方式 |
|---|---|---|
| 1 | App.vue 裸渲染分支 + SettingsView 提示行 | 两文件改动;验证: `node frontend/scripts/r015_check.mjs` + `npm run build` + `pytest tests/ -q` |
| 2 | 实机确认 + 基线回写 | 用户实拍/复述 AC-4;design/modules/mobile-pair.md 回写"+ /m 裸渲染"与 baseline 修订 |

## 越界自检(执行中每轮核对)
- [ ] 仍 ≤3 文件? [ ] 未改对外接口? [ ] 无新架构决策? [ ] 修复失败 <2 次?
> 任一失守 → 立即停止,escalated,state.escalated_from_micro=true,phase→expand。

## 验收对照(micro 简化,归档时填)
| AC | 结果 | 证据 |
|---|---|---|
| AC-1 | ✅ | `node frontend/scripts/r015_check.mjs` PASS=5 FAIL=0(重 build 后复跑;dist 含 bare 编译签名 `"/m"===`,负对照:旧产物上该签名缺失) |
| AC-2 | ✅ | `npm run build` 通过,新产物 index-Bu_i6R7d.js 已挂载生效(服务返回同哈希) |
| AC-3 | ✅ | `pytest tests/ -q` → 274 passed + 1 skipped(收集 275 与 R-014 基线一致,后端零改动) |
| AC-4 | ✅ | 用户实机确认"验证通过,归档 R-015"(question,2026-09-13;渲染层证据补 R-014 A-2 盲区) |

全量单测摘要:pytest 274+1skip/275;r015_check 5/5;r014_check 8/8;vite build 绿。
风险终态:R-1(壳误伤桌面)→ closed(build+实机桌面路由正常);R-2(老内核白屏假设)→ closed(实机打开无白屏,假设排除)。

## 自我复盘清单
- OPT-011(proposed→promoted):移动/UI 验收 RUN 须含渲染层证据;本需求 A-2 教训。
- OPT-012(proposed→promoted):产物静态断言三原则(首跑 5/5 实为旧产物假绿+正则嵌斜杠 SyntaxError,同类三见)。
- 两条已晋升落地:plan-execute-phase.md 两条 MUST + registry T-RENDER-EVIDENCE/T-DIST-ASSERT-SIGNATURE(skill 仓 commit 见 R-015 归档引用,HiEarth 2c5ccbe+晋升 commit)。
